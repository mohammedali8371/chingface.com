# ================================================================
# ملف admin/handlers.py
# ----------------------
# هذا الملف مسؤول عن الجانب الإشرافي للبوت:
#
#   1. المراقبة الشفافة:
#      - تسجيل كل رسالة تصل للبوت في قاعدة البيانات.
#      - إرسال نسخة لكل رسالة/ملف إلى المطور (مع معلومات المستخدم
#        وأزرار رد/حظر/حذف).
#
#   2. رد المطور على المستخدمين:
#      - حالة ADMIN_REPLY لكتابة الرد.
#
#   3. إجراءات لوحة المطور (الحالات المتعددة):
#      - رسالة جماعية (ADMIN_BROADCAST).
#      - رسالة لمستخدم محدد (ADMIN_DIRECT_USER_ID / ADMIN_DIRECT_MESSAGE).
#      - حظر / فك حظر / حذف مستخدم.
#      - رفع قاعدة البيانات (ADMIN_UPLOAD_DB).
#      - استعادة نسخة احتياطية (ADMIN_RESTORE_BACKUP).
#
# ملاحظة: هذا الملف يحتوي على بناء محادثة المطور build_admin_conversation.
# ================================================================

import asyncio

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from callbacks import Callbacks, parse_user_id_from_callback
from config import settings
from database import db
from handlers.base import cancel_flow, ensure_user
from keyboards import cancel_keyboard, user_action_keyboard
from logger import get_logger
from services.backup_service import backup_service
from services.broadcast_service import broadcast_service
from states import ConversationState
from storage.manager import storage
from utils.helpers import build_user_info_text, html_escape, is_developer, utc_now_iso
from utils.validators import is_safe_document

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)


def _parse_id(text: str):
    """
    يوزع نصاً إلى معرف رقمي.
    :return: المعرف الرقمي أو None إذا لم يكن النص رقماً صحيحاً.
    """
    text = (text or "").strip()
    if not text.isdigit():
        return None
    return int(text)


# ----------------------------------------------------------------
# المراقبة الشفافة: إشعار المطور
# ----------------------------------------------------------------

async def notify_dev_message(bot, message, user) -> None:
    """
    يرسل نسخة من رسالة/ملف المستخدم إلى المطور (مراقبة شفافة).
    مع إظهار معلومات كاملة: الاسم، اليوزرنيم، المعرّف، الوقت، نوع الملف.
    ويضيف أزرار: رد / حظر / حذف المستخدم.

    :param bot: كائن البوت.
    :param message: رسالة المستخدم.
    :param user: كائن المستخدم المرسل.
    """
    # إذا كانت المراقبة معطلة نخرج فوراً
    if not settings.ENABLE_MONITORING:
        return

    # لا نراقب المطور نفسه
    if not user or is_developer(user.id):
        return

    try:
        # 1) إعادة توجيه الرسالة نفسها (نص أو صورة أو فيديو أو مستند)
        await bot.forward_message(
            chat_id=settings.DEVELOPER_ID,
            from_chat_id=message.chat_id,
            message_id=message.message_id,
        )

        # 2) تحديد نوع الملف لوصف دقيق
        message_type = "نص"
        if message.photo:
            message_type = "🖼️ صورة"
        elif message.video:
            message_type = "🎬 فيديو"
        elif message.document:
            message_type = f"📄 مستند: {message.document.file_name or ''}"
        elif message.voice:
            message_type = "🎙️ رسالة صوتية"
        elif message.audio:
            message_type = "🎵 صوت"
        elif message.sticker:
            message_type = "😀 ملصق"

        # 3) بناء معلومات المستخدم مع الأزرار
        info_text = build_user_info_text(user, message_type, utc_now_iso())
        await bot.send_message(
            chat_id=settings.DEVELOPER_ID,
            text=info_text,
            parse_mode="HTML",
            reply_markup=user_action_keyboard(user.id),
        )
    except Exception as exc:
        logger.warning(f"فشل إشعار المطور برسالة من {user.id}: {exc}")


# ----------------------------------------------------------------
# المعالج الشامل لتسجيل الرسائل
# ----------------------------------------------------------------

async def on_message_logging(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    المعالج الشامل (Catch-all) لأي رسالة تصل للبوت.
    (يُضاف أخيراً في البوت، بعد كل المحادثات)
    يقوم بـ:
      1. تسجيل المستخدم.
      2. التحقق من حالة البوت والحظر (مع رد تحذيري فقط).
      3. حفظ الرسالة في قاعدة البيانات.
      4. إرسال نسخة للمطور (المراقبة الشفافة).
    """
    # نعمل في المحادثات الخاصة فقط
    chat = update.effective_chat
    if not chat or chat.type != "private":
        return

    user = update.effective_user
    if user is None:
        return

    # تسجيل المستخدم وتحديث آخر ظهور
    await ensure_user(update, context)

    # المطور لا يُراقب ولا تُسجل رسائله كنشاط مستخدم
    if is_developer(user.id):
        return

    message = update.message
    if message is None:
        return

    # ---------- التحقق من حالة البوت ----------
    try:
        bot_enabled = await db.get_setting("bot_enabled", "true")
        if bot_enabled == "false":
            await message.reply_text("⏸️ البوت متوقف مؤقتاً، عُد لاحقاً من فضلك.")
            return
        if await db.is_user_banned(user.id):
            await message.reply_text("🚫 تم حظرك من استخدام هذا البوت.")
            return
    except Exception as exc:
        logger.warning(f"خطأ في فحص حالة البوت: {exc}")

    # ---------- حفظ الرسالة في قاعدة البيانات ----------
    try:
        message_type = "text"
        text = message.text
        file_id = None
        if message.photo:
            message_type = "photo"
            file_id = message.photo[-1].file_id
        elif message.video:
            message_type = "video"
            file_id = message.video.file_id
        elif message.document:
            message_type = "document"
            file_id = message.document.file_id
        elif message.voice:
            message_type = "voice"
            file_id = message.voice.file_id
        elif message.audio:
            message_type = "audio"
            file_id = message.audio.file_id
        elif message.sticker:
            message_type = "sticker"

        await db.add_message(
            {
                "user_id": user.id,
                "username": user.username,
                "name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                "message_type": message_type,
                "text": text,
                "file_id": file_id,
                "created_at": utc_now_iso(),
            }
        )
    except Exception as exc:
        logger.warning(f"فشل حفظ الرسالة في قاعدة البيانات: {exc}")

    # ---------- إرسال نسخة للمطور (المراقبة الشفافة) ----------
    await notify_dev_message(context.bot, message, user)


# ----------------------------------------------------------------
# أزرار فورية على الرسائل المحولة (رد / حظر / حذف)
# ----------------------------------------------------------------

async def admin_reply_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    بداية الرد على مستخدم (عند الضغط على زر "رد").
    يسأل المطور عن نص الرد ويدخل في حالة ADMIN_REPLY.
    """
    query = update.callback_query
    await query.answer()

    # التحقق من أن الضاغط هو المطور
    if not is_developer(query.from_user.id):
        await query.message.reply_text("⛔ هذا الإجراء للمطور فقط.")
        return ConversationHandler.END

    # استخراج معرف المستخدم من نص الزر
    target_id = parse_user_id_from_callback(query.data)
    context.user_data["reply_target_id"] = target_id

    await query.message.reply_text(
        f"✍️ اكتب ردك للمستخدم <code>{target_id}</code>:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    return ConversationState.ADMIN_REPLY


async def admin_reply_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استلام نص الرد من المطور وإرساله للمستخدم."""
    reply_text = update.message.text
    target_id = context.user_data.get("reply_target_id")
    if not target_id:
        await update.message.reply_text("لم يتم تحديد مستخدم. ابدأ العملية مجدداً.")
        return ConversationHandler.END

    try:
        # إرسال الرد للمستخدم مباشرة
        await context.bot.send_message(
            chat_id=target_id,
            text=f"💬 <b>رد من المطور:</b>\n\n{reply_text}",
            parse_mode="HTML",
        )
        await update.message.reply_text(
            f"✅ تم إرسال ردك إلى المستخدم <code>{target_id}</code>.",
            parse_mode="HTML",
        )

        # تعليم آخر رسالة للمستخدم كمرد عليها
        try:
            last_msg_id = await db.get_last_message_id(target_id)
            if last_msg_id:
                await db.mark_message_replied(last_msg_id, reply_text)
        except Exception:
            pass
    except Exception as exc:
        await update.message.reply_text(f"⚠️ فشل إرسال الرد: {exc}")

    return ConversationHandler.END


async def admin_ban_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """حظر مستخدم مباشرة من زر "حظر" على رسالة محولة."""
    query = update.callback_query
    await query.answer()
    if not is_developer(query.from_user.id):
        return

    user_id = parse_user_id_from_callback(query.data)
    await db.ban_user(user_id)
    await query.message.reply_text(
        f"🚫 تم حظر المستخدم <code>{user_id}</code>.",
        parse_mode="HTML",
    )


async def admin_delete_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """حذف مستخدم مباشرة من زر "حذف المستخدم" على رسالة محولة."""
    query = update.callback_query
    await query.answer()
    if not is_developer(query.from_user.id):
        return

    user_id = parse_user_id_from_callback(query.data)
    await db.delete_user(user_id)
    await query.message.reply_text(
        f"🗑️ تم حذف المستخدم <code>{user_id}</code> وبياناته نهائياً.",
        parse_mode="HTML",
    )


# ----------------------------------------------------------------
# الإرسال الجماعي
# ----------------------------------------------------------------

async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """بداية إرسال رسالة جماعية (يسأل عن النص)."""
    query = update.callback_query
    await query.answer()
    if not is_developer(query.from_user.id):
        return ConversationHandler.END

    await query.message.reply_text(
        "📣 اكتب نص الرسالة الجماعية التي ستُرسل لجميع المستخدمين:",
        reply_markup=cancel_keyboard(),
    )
    return ConversationState.ADMIN_BROADCAST


async def admin_broadcast_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استلام نص الرسالة الجماعية وبدء الإرسال في الخلفية."""
    broadcast_text = update.message.text
    await update.message.reply_text("📤 جارٍ إرسال الرسالة الجماعية...")

    # الإرسال في الخلفية حتى لا ننتظر انتهاء كل المستخدمين
    bot = context.application.bot
    dev_chat_id = update.effective_chat.id
    asyncio.create_task(_run_broadcast(bot, broadcast_text, dev_chat_id))
    return ConversationHandler.END


async def _run_broadcast(bot, text: str, dev_chat_id: int) -> None:
    """ينفذ الإرسال الجماعي ويخبر المطور بالنتيجة."""
    sent, failed = await broadcast_service.send_to_all(bot, text)
    try:
        await bot.send_message(
            chat_id=dev_chat_id,
            text=f"📣 <b>انتهى الإرسال الجماعي</b>\n"
                 f"✅ تم الإرسال بنجاح: <b>{sent}</b>\n"
                 f"❌ فشل الإرسال: <b>{failed}</b>",
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.error(f"فشل إبلاغ المطور بنتيجة الإرسال: {exc}")


# ----------------------------------------------------------------
# رسالة لمستخدم محدد
# ----------------------------------------------------------------

async def admin_direct_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """بداية إرسال رسالة لمستخدم محدد (يسأل عن المعرف)."""
    query = update.callback_query
    await query.answer()
    if not is_developer(query.from_user.id):
        return ConversationHandler.END

    await query.message.reply_text(
        "✉️ أرسل <b>معرف المستخدم</b> (User ID) الرقمي:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    return ConversationState.ADMIN_DIRECT_USER_ID


async def admin_direct_user_id_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استلام معرف المستخدم ثم طلب نص الرسالة."""
    user_id = _parse_id(update.message.text)
    if user_id is None:
        await update.message.reply_text(
            "⚠️ المعرف يجب أن يكون رقماً. أرسله مرة أخرى:",
            reply_markup=cancel_keyboard(),
        )
        return ConversationState.ADMIN_DIRECT_USER_ID

    context.user_data["direct_target_id"] = user_id
    await update.message.reply_text(
        f"✍️ الآن اكتب نص الرسالة للمستخدم <code>{user_id}</code>:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    return ConversationState.ADMIN_DIRECT_MESSAGE


async def admin_direct_message_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استلام نص الرسالة المباشرة وإرسالها للمستخدم."""
    user_id = context.user_data.get("direct_target_id")
    if not user_id:
        await update.message.reply_text("لم يتم تحديد مستخدم. ابدأ العملية مجدداً.")
        return ConversationHandler.END

    text = update.message.text
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"📩 <b>رسالة من المطور:</b>\n\n{text}",
            parse_mode="HTML",
        )
        await update.message.reply_text("✅ تم إرسال الرسالة بنجاح.")
    except Exception as exc:
        await update.message.reply_text(f"⚠️ فشل الإرسال: {exc}")

    return ConversationHandler.END


# ----------------------------------------------------------------
# حظر / فك حظر / حذف مستخدم
# ----------------------------------------------------------------

async def admin_ban_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """بداية حظر مستخدم."""
    query = update.callback_query
    await query.answer()
    if not is_developer(query.from_user.id):
        return ConversationHandler.END
    await query.message.reply_text(
        "🚫 أرسل معرف المستخدم الذي تريد حظره:",
        reply_markup=cancel_keyboard(),
    )
    return ConversationState.ADMIN_BAN_USER


async def admin_ban_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استلام معرف المستخدم وحظره."""
    user_id = _parse_id(update.message.text)
    if user_id is None:
        await update.message.reply_text(
            "⚠️ معرف غير صالح. حاول مجدداً:",
            reply_markup=cancel_keyboard(),
        )
        return ConversationState.ADMIN_BAN_USER

    await db.ban_user(user_id)
    await update.message.reply_text(
        f"🚫 تم حظر المستخدم <code>{user_id}</code>.",
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def admin_unban_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """بداية فك الحظر عن مستخدم."""
    query = update.callback_query
    await query.answer()
    if not is_developer(query.from_user.id):
        return ConversationHandler.END
    await query.message.reply_text(
        "✅ أرسل معرف المستخدم الذي تريد فك الحظر عنه:",
        reply_markup=cancel_keyboard(),
    )
    return ConversationState.ADMIN_UNBAN_USER


async def admin_unban_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استلام معرف المستخدم وفك الحظر عنه."""
    user_id = _parse_id(update.message.text)
    if user_id is None:
        await update.message.reply_text(
            "⚠️ معرف غير صالح. حاول مجدداً:",
            reply_markup=cancel_keyboard(),
        )
        return ConversationState.ADMIN_UNBAN_USER

    await db.unban_user(user_id)
    await update.message.reply_text(
        f"✅ تم فك الحظر عن المستخدم <code>{user_id}</code>.",
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def admin_delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """بداية حذف مستخدم نهائياً."""
    query = update.callback_query
    await query.answer()
    if not is_developer(query.from_user.id):
        return ConversationHandler.END
    await query.message.reply_text(
        "🗑️ أرسل معرف المستخدم الذي تريد <b>حذفه نهائياً</b> مع كل بياناته:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    return ConversationState.ADMIN_DELETE_USER


async def admin_delete_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استلام معرف المستخدم وحذفه نهائياً."""
    user_id = _parse_id(update.message.text)
    if user_id is None:
        await update.message.reply_text(
            "⚠️ معرف غير صالح. حاول مجدداً:",
            reply_markup=cancel_keyboard(),
        )
        return ConversationState.ADMIN_DELETE_USER

    await db.delete_user(user_id)
    await update.message.reply_text(
        f"🗑️ تم حذف المستخدم <code>{user_id}</code> وجميع بياناته.",
        parse_mode="HTML",
    )
    return ConversationHandler.END


# ----------------------------------------------------------------
# رفع قاعدة البيانات
# ----------------------------------------------------------------

async def admin_upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """بداية رفع قاعدة بيانات جديدة."""
    query = update.callback_query
    await query.answer()
    if not is_developer(query.from_user.id):
        return ConversationHandler.END
    await query.message.reply_text(
        "⬆️ أرسل ملف قاعدة البيانات الجديد (امتداد .db):\n\n"
        "⚠️ <b>تحذير:</b> سيتم استبدال القاعدة الحالية "
        "(تُنشأ نسخة احتياطية تلقائياً قبل الاستبدال).",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    return ConversationState.ADMIN_UPLOAD_DB


async def admin_upload_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استلام ملف قاعدة البيانات والتحقق منه واستبداله."""
    document = update.message.document
    if not document:
        await update.message.reply_text("أرسل ملفاً (Document) من فضلك.")
        return ConversationState.ADMIN_UPLOAD_DB

    # التحقق من امتداد الملف (الأمان)
    file_name = document.file_name or "database.db"
    if not is_safe_document(file_name):
        await update.message.reply_text(
            "⚠️ امتداد غير صالح. المطلوب: <code>.db</code>",
            parse_mode="HTML",
        )
        return ConversationState.ADMIN_UPLOAD_DB

    # تنزيل الملف
    dest = storage.new_temp_file(settings.DEVELOPER_ID, ".db")
    ok = await storage.download_telegram_file(context.bot, document.file_id, dest)
    if not ok:
        await update.message.reply_text("فشل تنزيل الملف، حاول مجدداً.")
        return ConversationState.ADMIN_UPLOAD_DB

    try:
        # قراءة البيانات واستبدال القاعدة
        data = dest.read_bytes()
        success = storage.replace_db(data)
        if success:
            # إعادة الاتصال بالقاعدة الجديدة
            await db.reconnect()
            await db.init_schema()
            await update.message.reply_text("✅ تم استبدال قاعدة البيانات بنجاح.")
        else:
            await update.message.reply_text("❌ فشل استبدال قاعدة البيانات.")
    except Exception as exc:
        logger.error(f"خطأ في رفع قاعدة البيانات: {exc}")
        await update.message.reply_text(f"❌ خطأ أثناء المعالجة: {str(exc)[:200]}")
    finally:
        # تنظيف الملف المؤقت
        storage.remove_file(dest)

    return ConversationHandler.END


# ----------------------------------------------------------------
# استعادة نسخة احتياطية
# ----------------------------------------------------------------

async def admin_restore_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """بداية استعادة نسخة احتياطية (يعرض القائمة المتوفرة)."""
    query = update.callback_query
    await query.answer()
    if not is_developer(query.from_user.id):
        return ConversationHandler.END

    # جلب قائمة النسخ من قاعدة البيانات
    backups = await db.list_backups(20)
    text = (
        "♻️ اكتب <b>اسم ملف</b> النسخة الاحتياطية التي تريد استعادتها:\n\n"
    )
    if backups:
        lines = "\n".join(
            f"• <code>{html_escape(b['filename'])}</code>" for b in backups
        )
        text += f"النسخ المتوفرة:\n{lines}"
    else:
        text += "(لا توجد نسخ مسجلة بعد - أنشئ نسخة أولاً من لوحة المطور)"

    await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    return ConversationState.ADMIN_RESTORE_BACKUP


async def admin_restore_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استلام اسم النسخة الاحتياطية واستعادتها."""
    filename = update.message.text.strip()

    # تنفيذ الاستعادة (يتم إعادة الاتصال بالقاعدة تلقائياً)
    success = await backup_service.restore_backup(filename)
    if success:
        await update.message.reply_text(
            f"✅ تمت استعادة النسخة الاحتياطية: <code>{html_escape(filename)}</code>",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"❌ تعذر استعادة <code>{html_escape(filename)}</code>.\n"
            "تأكد من كتابة الاسم بشكل صحيح.",
            parse_mode="HTML",
        )
    return ConversationHandler.END


# ----------------------------------------------------------------
# بناء محادثة لوحة المطور
# ----------------------------------------------------------------

def build_admin_conversation() -> ConversationHandler:
    """
    يبني محادثة (ConversationHandler) خاصة بلوحة المطور.
    تحتوي على جميع الإجراءات التي تتطلب أكثر من خطوة.
    """
    # أنماط الأزرار
    reply_pattern = rf"^{Callbacks.REPLY_PREFIX}\d+$"
    cancel_pattern = rf"^{Callbacks.CANCEL}$"

    # أزرار الإلغاء داخل الحالات (لتسمح بالخروج في أي وقت)
    cancel_button = CallbackQueryHandler(cancel_flow, pattern=cancel_pattern)

    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_reply_start, pattern=reply_pattern),
            CallbackQueryHandler(admin_broadcast_start, pattern=rf"^{Callbacks.DEV_BROADCAST}$"),
            CallbackQueryHandler(admin_direct_user_start, pattern=rf"^{Callbacks.DEV_DIRECT_MESSAGE}$"),
            CallbackQueryHandler(admin_ban_start, pattern=rf"^{Callbacks.DEV_BAN_USER}$"),
            CallbackQueryHandler(admin_unban_start, pattern=rf"^{Callbacks.DEV_UNBAN_USER}$"),
            CallbackQueryHandler(admin_delete_start, pattern=rf"^{Callbacks.DEV_DELETE_USER}$"),
            CallbackQueryHandler(admin_upload_start, pattern=rf"^{Callbacks.DEV_UPLOAD_DB}$"),
            CallbackQueryHandler(admin_restore_start, pattern=rf"^{Callbacks.DEV_RESTORE_BACKUP}$"),
        ],
        states={
            ConversationState.ADMIN_REPLY: [
                MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, admin_reply_receive),
                cancel_button,
            ],
            ConversationState.ADMIN_BROADCAST: [
                MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, admin_broadcast_receive),
                cancel_button,
            ],
            ConversationState.ADMIN_DIRECT_USER_ID: [
                MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, admin_direct_user_id_receive),
                cancel_button,
            ],
            ConversationState.ADMIN_DIRECT_MESSAGE: [
                MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, admin_direct_message_receive),
                cancel_button,
            ],
            ConversationState.ADMIN_BAN_USER: [
                MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, admin_ban_receive),
                cancel_button,
            ],
            ConversationState.ADMIN_UNBAN_USER: [
                MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, admin_unban_receive),
                cancel_button,
            ],
            ConversationState.ADMIN_DELETE_USER: [
                MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, admin_delete_receive),
                cancel_button,
            ],
            ConversationState.ADMIN_UPLOAD_DB: [
                MessageHandler(filters.Document.ALL & filters.ChatType.PRIVATE, admin_upload_receive),
                cancel_button,
            ],
            ConversationState.ADMIN_RESTORE_BACKUP: [
                MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, admin_restore_receive),
                cancel_button,
            ],
        },
        fallbacks=[cancel_button],
        name="admin_conv",
    )
