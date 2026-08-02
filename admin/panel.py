# ================================================================
# ملف admin/panel.py
# ------------------
# هذا الملف مسؤول عن واجهة لوحة المطور (UI) والإجراءات الفورية.
#
# يحتوي على:
#   - عرض لوحة المطور الرئيسية.
#   - الإحصائيات وعدد المستخدمين وآخر المستخدمين والرسائل والأخطاء.
#   - تشغيل / إيقاف البوت.
#   - إعادة تشغيل الخدمات ومسح الكاش.
#   - تنزيل قاعدة البيانات وإنشاء نسخة احتياطية.
#
# ملاحظة: الإجراءات التي تحتاج أكثر من خطوة (بث، حظر، رفع قاعدة
# البيانات...) تبدأ من هنا لكنها تُدار داخل محادثة المطور
# (راجع admin/handlers.py).
# ================================================================

import io

from telegram import InputFile, Update
from telegram.ext import ContextTypes

from ai.model_manager import model_manager
from callbacks import Callbacks
from database import db
from handlers.base import ensure_user
from keyboards import dev_back_keyboard, dev_panel_keyboard, main_menu_keyboard
from logger import get_logger
from services.backup_service import backup_service
from services.stats_service import stats_service
from storage.manager import storage
from utils.helpers import html_escape, is_developer
from utils.rate_limiter import rate_limiter

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)

# نص لوحة المطور الرئيسية
DEV_PANEL_TEXT = (
    "👨‍💻 <b>لوحة تحكم المطور</b>\n"
    "──────────────\n"
    "اختر إجراءً من الأزرار أدناه:"
)


# ----------------------------------------------------------------
# عرض اللوحة الرئيسية
# ----------------------------------------------------------------

async def show_dev_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    يعرض لوحة تحكم المطور الرئيسية.
    يُستدعى من زر "المطور" أو زر العودة للوحة.
    """
    query = update.callback_query
    await query.answer()

    # التحقق من أن الضاغط هو المطور
    if not is_developer(query.from_user.id):
        await query.edit_message_text(
            "⛔ هذه اللوحة متاحة للمطور فقط.",
            reply_markup=main_menu_keyboard(),
        )
        return

    # تسجيل المطور (لأغراض القياس)
    await ensure_user(update, context)

    await query.edit_message_text(
        DEV_PANEL_TEXT,
        parse_mode="HTML",
        reply_markup=dev_panel_keyboard(),
    )


# ----------------------------------------------------------------
# الإحصائيات والمعلومات
# ----------------------------------------------------------------

async def dev_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض الإحصائيات الكاملة."""
    query = update.callback_query
    await query.answer()
    if not is_developer(query.from_user.id):
        return

    snap = await stats_service.get_snapshot()
    text = stats_service.snapshot_to_text(snap)
    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=dev_back_keyboard(),
    )


async def dev_users_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض عدد المستخدمين والمحظورين."""
    query = update.callback_query
    await query.answer()
    if not is_developer(query.from_user.id):
        return

    total = await db.count_users()
    # حساب عدد المحظورين
    users = await db.get_all_users()
    banned = sum(1 for u in users if u.get("is_banned"))

    await query.edit_message_text(
        f"👥 <b>عدد المستخدمين:</b> <code>{total}</code>\n"
        f"🚫 <b>المحظورون:</b> <code>{banned}</code>",
        parse_mode="HTML",
        reply_markup=dev_back_keyboard(),
    )


async def dev_recent_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض آخر 10 مستخدمين."""
    query = update.callback_query
    await query.answer()
    if not is_developer(query.from_user.id):
        return

    users = await db.get_recent_users(10)
    lines = ["🕒 <b>آخر المستخدمين</b>", "──────────────"]
    if not users:
        lines.append("لا يوجد مستخدمون بعد.")
    else:
        for u in users:
            name = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip() or "مجهول"
            username = u.get("username") or "بدون"
            banned = " 🚫" if u.get("is_banned") else ""
            lines.append(
                f"• <code>{u['user_id']}</code> {html_escape(name)} "
                f"(@{html_escape(username)}){banned}"
            )

    await query.edit_message_text(
        "\n".join(lines)[:4000],
        parse_mode="HTML",
        reply_markup=dev_back_keyboard(),
    )


async def dev_recent_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض آخر الرسائل المستلمة."""
    query = update.callback_query
    await query.answer()
    if not is_developer(query.from_user.id):
        return

    messages = await db.get_recent_messages(20)
    lines = ["💬 <b>آخر الرسائل</b>", "──────────────"]
    if not messages:
        lines.append("لا توجد رسائل بعد.")
    else:
        for m in messages:
            snippet = (m.get("text") or "")[:50].replace("\n", " ")
            lines.append(
                f"• <code>{m['user_id']}</code> ({m.get('message_type')}): {html_escape(snippet)}"
            )

    await query.edit_message_text(
        "\n".join(lines)[:4000],
        parse_mode="HTML",
        reply_markup=dev_back_keyboard(),
    )


async def dev_errors(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض سجل الأخطاء."""
    query = update.callback_query
    await query.answer()
    if not is_developer(query.from_user.id):
        return

    errors = await db.get_recent_errors(15)
    lines = ["⚠️ <b>سجل الأخطاء</b>", "──────────────"]
    if not errors:
        lines.append("لا توجد أخطاء مسجلة. ممتاز! 🎉")
    else:
        for e in errors:
            lines.append(
                f"• <code>{e.get('created_at', '')}</code> "
                f"[user {e.get('user_id')}]\n  {html_escape(str(e.get('message', ''))[:100])}"
            )

    await query.edit_message_text(
        "\n".join(lines)[:4000],
        parse_mode="HTML",
        reply_markup=dev_back_keyboard(),
    )


# ----------------------------------------------------------------
# تشغيل / إيقاف البوت
# ----------------------------------------------------------------

async def dev_bot_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تشغيل البوت."""
    query = update.callback_query
    await query.answer()
    if not is_developer(query.from_user.id):
        return

    await db.set_setting("bot_enabled", "true")
    logger.info("تم تشغيل البوت من لوحة المطور")
    await query.edit_message_text(
        "▶️ تم <b>تشغيل</b> البوت بنجاح.\nجميع المستخدمين يستطيعون الاستخدام الآن.",
        parse_mode="HTML",
        reply_markup=dev_back_keyboard(),
    )


async def dev_bot_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إيقاف البوت."""
    query = update.callback_query
    await query.answer()
    if not is_developer(query.from_user.id):
        return

    await db.set_setting("bot_enabled", "false")
    logger.info("تم إيقاف البوت من لوحة المطور")
    await query.edit_message_text(
        "⏸️ تم <b>إيقاف</b> البوت.\nلن يستقبل البوت الطلبات إلا من المطور نفسه.",
        parse_mode="HTML",
        reply_markup=dev_back_keyboard(),
    )


# ----------------------------------------------------------------
# إعادة تشغيل الخدمات ومسح الكاش
# ----------------------------------------------------------------

async def dev_restart_services(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    إعادة تشغيل الخدمات الداخلية:
      - تحرير نماذج الذكاء الاصطناعي من الذاكرة (تعيد التحميل عند الحاجة).
      - إعادة ضبط نظام الحماية من الـ Spam.
      - تنظيف الملفات المؤقتة القديمة.
    """
    query = update.callback_query
    await query.answer()
    if not is_developer(query.from_user.id):
        return

    # 1) تحرير النماذج
    model_manager.reset()
    # 2) إعادة ضبط نظام الحماية
    rate_limiter.reset()
    # 3) تنظيف الملفات المؤقتة
    cleared = await __import__("asyncio").to_thread(storage.clear_all_temp)

    logger.info("تمت إعادة تشغيل الخدمات الداخلية")
    await query.edit_message_text(
        "🔄 <b>تمت إعادة تشغيل الخدمات الداخلية:</b>\n"
        "• تحرير نماذج الذكاء الاصطناعي ✓\n"
        "• إعادة ضبط نظام الحماية ✓\n"
        f"• تنظيف الملفات المؤقتة ({cleared} عنصر) ✓",
        parse_mode="HTML",
        reply_markup=dev_back_keyboard(),
    )


async def dev_clear_cache(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """مسح الكاش والملفات المؤقتة."""
    query = update.callback_query
    await query.answer()
    if not is_developer(query.from_user.id):
        return

    count = await __import__("asyncio").to_thread(storage.clear_all_temp)
    await query.edit_message_text(
        f"🧹 تم مسح الكاش والملفات المؤقتة.\nعدد العناصر المحذوفة: <b>{count}</b>",
        parse_mode="HTML",
        reply_markup=dev_back_keyboard(),
    )


# ----------------------------------------------------------------
# قاعدة البيانات والنسخ الاحتياطية
# ----------------------------------------------------------------

async def dev_download_db(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تنزيل قاعدة البيانات الحالية للمطور."""
    query = update.callback_query
    await query.answer()
    if not is_developer(query.from_user.id):
        return

    data = storage.get_db_bytes()
    if not data:
        await query.edit_message_text(
            "❌ تعذر قراءة قاعدة البيانات.",
            reply_markup=dev_back_keyboard(),
        )
        return

    # نرسل الملف ثم نحدّث رسالة اللوحة
    await query.message.reply_document(
        document=InputFile(io.BytesIO(data), filename="database.db"),
        caption="🗄️ ملف قاعدة البيانات الحالية.",
    )
    await query.edit_message_text(
        "⬇️ تم إرسال قاعدة البيانات إليك.",
        reply_markup=dev_back_keyboard(),
    )


async def dev_backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إنشاء نسخة احتياطية من قاعدة البيانات."""
    query = update.callback_query
    await query.answer()
    if not is_developer(query.from_user.id):
        return

    name = await backup_service.create_backup()
    if name:
        await query.edit_message_text(
            f"💾 تم إنشاء نسخة احتياطية:\n<code>{html_escape(name)}</code>",
            parse_mode="HTML",
            reply_markup=dev_back_keyboard(),
        )
    else:
        await query.edit_message_text(
            "❌ فشل إنشاء النسخة الاحتياطية.",
            reply_markup=dev_back_keyboard(),
        )
