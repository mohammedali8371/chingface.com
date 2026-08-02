# ================================================================
# ملف handlers/base.py
# --------------------
# هذا الملف يحتوي على الدوال المشتركة بين جميع المعالجات:
#   1. تسجيل المستخدم (ensure_user).
#   2. التحقق من الوصول (check_access): البوت مفعل؟ المستخدم غير
#      محظور؟ لم يتجاوز حد الطلبات؟
#   3. معالج الأخطاء العام (on_error).
#   4. معالج الإلغاء المشترك (cancel_flow).
#   5. تذكير المستخدم بنوع المدخل المطلوب (expect_photo / expect_video).
# ================================================================

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from config import settings
from database import db
from keyboards import cancel_keyboard, main_menu_keyboard
from logger import get_logger
from services.user_service import user_service
from storage.manager import storage
from utils.helpers import is_developer
from utils.rate_limiter import rate_limiter

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)


async def ensure_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    يسجل المستخدم الحالي في قاعدة البيانات ويحدّث آخر ظهور له.
    يُستدعى في بداية أي تفاعل مع المستخدم.
    """
    user = update.effective_user
    if user is None:
        return
    try:
        await user_service.register_user(user)
        await user_service.touch_last_seen(user.id)
    except Exception as exc:
        # لا نوقف سير العمل بسبب فشل تسجيل (نكتفي بالتسجيل في السجل)
        logger.warning(f"فشل تسجيل المستخدم {user.id}: {exc}")


async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    يتحقق من أن المستخدم مسموح له باستخدام البوت.
    الفحوصات:
      1. البوت مفعل (إعداد bot_enabled)؟ - للمطور دائماً مسموح.
      2. المستخدم غير محظور؟
      3. لم يتجاوز حد الطلبات (Rate Limit)؟

    :return: True إذا كان مسموحاً بالمتابعة، False إن لم يكن.
    """
    user = update.effective_user
    if user is None:
        return False

    # المطور دائماً مسموح له حتى لو كان البوت متوقفاً
    if is_developer(user.id):
        return True

    # كائن الرسالة الحالية (لإرسال التنبيهات)
    target = update.effective_message

    try:
        # 1) التحقق من تفعيل البوت
        bot_enabled = await db.get_setting("bot_enabled", "true")
        if bot_enabled == "false":
            if target:
                await target.reply_text("⏸️ البوت متوقف مؤقتاً، عُد لاحقاً من فضلك.")
            return False

        # 2) التحقق من الحظر
        if await db.is_user_banned(user.id):
            if target:
                await target.reply_text("🚫 تم حظرك من استخدام هذا البوت.")
            return False

        # 3) التحقق من حد الطلبات (منع الـ Spam والـ Flood)
        if settings.ENABLE_RATE_LIMIT and not rate_limiter.is_allowed(user.id):
            if target:
                await target.reply_text("🐢 عدد الطلبات كبير، انتظر دقيقة وحاول مجدداً.")
            return False
    except Exception as exc:
        # أي خطأ في الفحص يجب ألا يمنع المستخدم من الاستخدام
        logger.warning(f"خطأ في التحقق من الوصول للمستخدم {user.id}: {exc}")

    return True


async def on_error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    معالج الأخطاء العام.
    يُستدعى تلقائياً عند حدوث أي استثناء غير معالج في البوت.
    نقوم بـ:
      1. تسجيل الخطأ في السجلات.
      2. حفظه في قاعدة البيانات.
      3. إشعار المطور.
    """
    # الخطأ الحالي
    error = context.error
    user_id = None
    if update and update.effective_user:
        user_id = update.effective_user.id

    # تسجيل في السجل
    logger.error(f"خطأ عام في البوت (المستخدم {user_id}): {error}")

    # حفظ في قاعدة البيانات
    try:
        handler_name = "unknown"
        if update:
            handler_name = type(update).__name__
        await db.add_error(user_id, handler_name, str(error))
    except Exception as exc:
        logger.error(f"فشل حفظ الخطأ في قاعدة البيانات: {exc}")

    # إشعار المطور
    try:
        await context.bot.send_message(
            chat_id=settings.DEVELOPER_ID,
            text=(
                "⚠️ <b>خطأ في البوت</b>\n"
                f"المستخدم: <code>{user_id}</code>\n"
                f"الخطأ: <code>{str(error)[:500]}</code>"
            ),
            parse_mode="HTML",
        )
    except Exception:
        pass  # تجاهل فشل الإشعار (قد يكون البوت متوقفاً)


async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    معالج إلغاء العملية الحالية.
    يُستخدم من جميع محادثات البوت (تبديل صورة، فيديو، لوحة المطور).
    يقوم بتنظيف الملفات المؤقتة والعودة للقائمة الرئيسية.
    """
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    # تنظيف أي ملفات مؤقتة معلقة
    try:
        storage.cleanup_user_temp(user_id)
    except Exception:
        pass

    # مسح البيانات المخزنة في جلسة المستخدم
    for key in ("swap_source_path", "video_source_path", "reply_target_id"):
        context.user_data.pop(key, None)

    # العودة للقائمة الرئيسية
    await query.edit_message_text(
        "تم إلغاء العملية الحالية ❌",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END


async def expect_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يُظهر عندما يرسل المستخدم شيئاً غير صورة أثناء انتظار صورة.
    (يُسجّل الرسالة أيضاً للمراقبة الشفافة)
    """
    # إشعار المطور (المراقبة الشفافة) دون إيقاف سير العمل
    try:
        from admin.handlers import notify_dev_message
        await notify_dev_message(context.bot, update.message, update.effective_user)
    except Exception:
        pass

    await update.message.reply_text(
        "📷 هذا الإجراء ينتظر <b>صورة</b> من فضلك.\nأرسل صورة واضحة:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    # نعيد الحالة الحالية عبر سياق المحادثة (يُضبط في ملفات الاستخدام)
    from states import ConversationState
    return context.user_data.get("_current_state", ConversationState.IMAGE_SWAP_SOURCE)


async def expect_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يُظهر عندما يرسل المستخدم شيئاً غير فيديو أثناء انتظار فيديو.
    (يُسجّل الرسالة أيضاً للمراقبة الشفافة)
    """
    try:
        from admin.handlers import notify_dev_message
        await notify_dev_message(context.bot, update.message, update.effective_user)
    except Exception:
        pass

    await update.message.reply_text(
        "🎬 هذا الإجراء ينتظر <b>فيديو</b> من فضلك.\nأرسل فيديو mp4 قصيراً:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    from states import ConversationState
    return context.user_data.get("_current_state", ConversationState.VIDEO_SWAP_TARGET)
