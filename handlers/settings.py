# ================================================================
# ملف handlers/settings.py
# ------------------------
# هذا الملف مسؤول عن قائمة الإعدادات:
#   - مستوى جودة التحسين (عالي / متوسط / بدون).
#   - عرض الإحصائيات الشخصية.
#   - حذف بيانات المستخدم (الخصوصية).
# ================================================================

from telegram import Update
from telegram.ext import ContextTypes

from callbacks import Callbacks
from handlers.base import ensure_user
from keyboards import back_keyboard, main_menu_keyboard, settings_keyboard
from logger import get_logger
from services.user_service import user_service
from utils.helpers import get_swap_stats_text

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)

SETTINGS_TEXT = (
    "⚙️ <b>الإعدادات</b>\n"
    "──────────────\n"
    "اضبط مستوى تحسين الجودة حسب رغبتك:\n"
    "• <b>عالي</b>: أفضل جودة لكن أبطأ.\n"
    "• <b>متوسط</b>: توازن بين الجودة والسرعة.\n"
    "• <b>بدون تحسين</b>: أسرع نتيجة."
)


async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض قائمة الإعدادات."""
    query = update.callback_query
    await query.answer()
    await ensure_user(update, context)

    await query.edit_message_text(
        SETTINGS_TEXT,
        parse_mode="HTML",
        reply_markup=settings_keyboard(),
    )


async def _set_quality(update: Update, context: ContextTypes.DEFAULT_TYPE, level: str) -> None:
    """
    دالة داخلية لضبط جودة التحسين.
    :param level: high / medium / off
    """
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    await user_service.set_pref(user_id, "quality", level)

    # نص التأكيد حسب المستوى
    labels = {
        "high": "🔝 جودة عالية",
        "medium": "🔶 جودة متوسطة",
        "off": "⚪ بدون تحسين",
    }
    await query.edit_message_text(
        f"✅ تم ضبط جودة التحسين على: <b>{labels.get(level, level)}</b>",
        parse_mode="HTML",
        reply_markup=settings_keyboard(),
    )


async def quality_high(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ضبط جودة التحسين على عالية."""
    await _set_quality(update, context, "high")


async def quality_medium(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ضبط جودة التحسين على متوسطة."""
    await _set_quality(update, context, "medium")


async def quality_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إيقاف التحسين."""
    await _set_quality(update, context, "off")


async def my_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض الإحصائيات الشخصية للمستخدم."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_row = await user_service.get_user(user_id)

    if user_row:
        text = get_swap_stats_text(user_row)
    else:
        text = "لا توجد بيانات بعد. ابدأ بتجربة أول عملية تبديل!"

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=settings_keyboard(),
    )


async def delete_my_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    حذف بيانات المستخدم نهائياً من قاعدة البيانات.
    (متوافق مع حقوق الخصوصية: حق المستخدم في حذف بياناته)
    """
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    # حذف المستخدم وكل بياناته المرتبطة
    from database import db
    await db.delete_user(user_id)

    logger.info(f"تم حذف بيانات المستخدم {user_id} بناءً على طلبه")
    await query.edit_message_text(
        "🗑️ تم حذف جميع بياناتك من قاعدة البيانات بنجاح.\n\n"
        "يمكنك البدء من جديد متى شئت.",
        reply_markup=main_menu_keyboard(),
    )
