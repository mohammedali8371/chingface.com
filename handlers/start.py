# ================================================================
# ملف handlers/start.py
# ---------------------
# هذا الملف مسؤول عن:
#   1. أمر /start (بداية الاستخدام).
#   2. عرض تنبيه الخصوصية والمراقبة الشفافة.
#   3. الموافقة / الرفض على المراقبة الشفافة.
#   4. عرض القائمة الرئيسية.
# ================================================================

from telegram import Update
from telegram.ext import ContextTypes

from callbacks import Callbacks
from config import settings
from handlers.base import ensure_user
from keyboards import main_menu_keyboard, monitoring_keyboard
from logger import get_logger
from services.user_service import user_service

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)

# ----------------------------------------------------------------
# نصوص الواجهة (ثوابت حتى يسهل تعديلها)
# ----------------------------------------------------------------

# نص الترحيب والقائمة الرئيسية
MAIN_MENU_TEXT = (
    f"👋 <b>مرحباً بك في {settings.BOT_NAME}</b>\n"
    "──────────────\n"
    "اختر ما تريد فعله من الأزرار أدناه:\n\n"
    "🖼️ <b>تبديل صورة</b>: ضع وجهك في أي صورة.\n"
    "🎬 <b>تبديل فيديو</b>: ضع وجهك في فيديو (حتى 20 ثانية).\n"
    "⚙️ <b>الإعدادات</b>: تحكم بجودة التحسين وبياناتك.\n"
    "❓ <b>المساعدة</b>: شرح طريقة الاستخدام."
)

# تنبيه المراقبة الشفافة (يظهر قبل السماح بالاستخدام)
MONITORING_NOTICE_TEXT = (
    "⚠️ <b>تنبيه الخصوصية والمراقبة</b>\n"
    "──────────────\n"
    "قبل أن تبدأ، نود إعلامك <b>بشفافية كاملة</b>:\n\n"
    "1️⃣ يقوم البوت بمعالجة الصور والفيديوهات التي ترسلها لتنفيذ تبديل الوجه.\n"
    "2️⃣ بموجب <b>سياسة الخصوصية</b>، قد تتم مشاركة رسائلك وملفاتك "
    "مع <b>مطوّر البوت</b> لأغراض الإشراف على الخدمة وتحسين جودتها.\n"
    "3️⃣ تُحذف ملفاتك المؤقتة تلقائياً بعد انتهاء المعالجة.\n"
    "4️⃣ لا نشارك بياناتك مع أي جهة خارجية.\n\n"
    "بضغطك «أوافق والمتابعة» فأنت تقر بالموافقة على هذه الشروط."
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    معالج أمر /start.
    يقوم بـ:
      1. تسجيل المستخدم.
      2. إذا لم يوافق على المراقبة الشفافة يعرض تنبيه الخصوصية.
      3. وإلا يعرض القائمة الرئيسية.
    """
    # تسجيل المستخدم في قاعدة البيانات
    await ensure_user(update, context)

    user = update.effective_user
    if user is None:
        return

    # التحقق من الموافقة على المراقبة الشفافة
    agreed = await user_service.has_agreed(user.id)
    if not agreed:
        await update.message.reply_text(
            MONITORING_NOTICE_TEXT,
            parse_mode="HTML",
            reply_markup=monitoring_keyboard(),
        )
        return

    # عرض القائمة الرئيسية
    await update.message.reply_text(
        MAIN_MENU_TEXT,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


async def agree_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    معالج الضغط على زر "أوافق والمتابعة".
    يحفظ الموافقة ويعرض القائمة الرئيسية.
    """
    query = update.callback_query
    await query.answer()

    # حفظ الموافقة
    await user_service.set_agreed(query.from_user.id, True)
    logger.info(f"المستخدم {query.from_user.id} وافق على المراقبة الشفافة")

    # عرض القائمة الرئيسية (نعدّل الرسالة الحالية)
    await query.edit_message_text(
        MAIN_MENU_TEXT,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


async def decline_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    معالج الضغط على زر "لا أوافق".
    يمنع الاستخدام حتى يوافق المستخدم.
    """
    query = update.callback_query
    await query.answer()

    await user_service.set_agreed(query.from_user.id, False)

    await query.edit_message_text(
        "🚫 لا يمكنك استخدام البوت دون الموافقة على سياسة الخصوصية "
        "والمراقبة الشفافة.\n\n"
        "يمكنك العودة إلى التنبيه والموافقة متى شئت:",
        reply_markup=monitoring_keyboard(),
    )


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    معالج الضغط على زر "رجوع / القائمة الرئيسية".
    يعيد عرض القائمة الرئيسية.
    """
    query = update.callback_query
    await query.answer()

    # التأكد من تسجيل المستخدم
    await ensure_user(update, context)

    await query.edit_message_text(
        MAIN_MENU_TEXT,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )
