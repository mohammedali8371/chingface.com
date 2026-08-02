# ================================================================
# ملف handlers/help_menu.py
# -------------------------
# هذا الملف مسؤول عن الأزرار التالية:
#   - المساعدة (HELP)
#   - حول البوت (ABOUT)
#   - سياسة الخصوصية (PRIVACY)
#   - المطور (DEVELOPER)
# ================================================================

from telegram import Update
from telegram.ext import ContextTypes

from callbacks import Callbacks
from config import settings
from handlers.base import ensure_user
from keyboards import back_keyboard
from logger import get_logger
from utils.helpers import is_developer

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)

# ----------------------------------------------------------------
# نصوص ثابتة
# ----------------------------------------------------------------

HELP_TEXT = (
    "❓ <b>المساعدة - طريقة الاستخدام</b>\n"
    "──────────────\n"
    "<b>🖼️ تبديل صورة:</b>\n"
    "1. اضغط زر «تبديل صورة».\n"
    "2. أرسل صورة وجهك (واضحة، مواجهة للكاميرا، بإضاءة جيدة).\n"
    "3. أرسل الصورة الهدف (التي تريد وضع وجهك فيها).\n"
    "4. انتظر النتيجة (عادة أقل من دقيقة).\n\n"
    "<b>🎬 تبديل فيديو:</b>\n"
    "1. اضغط زر «تبديل فيديو».\n"
    "2. أرسل صورة وجهك أولاً.\n"
    "3. أرسل فيديو mp4 (حتى 20 ثانية).\n"
    "4. انتظر معالجة الفيديو (قد تستغرق دقائق).\n\n"
    "💡 <b>نصائح للحصول على أفضل نتيجة:</b>\n"
    "• استخدم صوراً عالية الوضوح.\n"
    "• وجه الشخص في الصورة الهدف قريب من نفس اتجاه وجهك.\n"
    "• أضواء متساوية تقلل التشوهات."
)

ABOUT_TEXT = (
    f"ℹ️ <b>{settings.BOT_NAME}</b>\n"
    "──────────────\n"
    "الإصدار: <b>{version}</b>\n"
    "التقنيات المستخدمة:\n"
    "• Python 3.11\n"
    "• python-telegram-bot v22\n"
    "• FastAPI + Uvicorn (Webhook)\n"
    "• InsightFace + ONNX Runtime\n"
    "• OpenCV + NumPy + FFmpeg\n"
    "• SQLite\n\n"
    "هذا البوت يستخدم تقنية تبديل الوجه بالذكاء الاصطناعي. "
    "النتائج تعتمد على جودة الصور وقد لا تكون واقعية مضمونة في جميع الحالات."
).format(version=settings.BOT_VERSION)

PRIVACY_TEXT = (
    "📜 <b>سياسة الخصوصية</b>\n"
    "──────────────\n"
    "1️⃣ <b>البيانات التي نجمعها:</b>\n"
    "• معرفك الرقمي (User ID) واسمك واسم المستخدم.\n"
    "• الصور والفيديوهات التي ترسلها لتنفيذ عمليات التبديل.\n"
    "• إحصائيات الاستخدام (عدد العمليات، الأوقات).\n\n"
    "2️⃣ <b>كيف نستخدم بياناتك:</b>\n"
    "• تنفيذ عمليات تبديل الوجه فقط.\n"
    "• مراقبة الخدمة وتحسينها من قبل المطور (بشفافية وإعلامك مسبقاً).\n"
    "• إعداد تقارير إحصائية مجهولة الهوية.\n\n"
    "3️⃣ <b>مشاركة البيانات:</b>\n"
    "• قد تُرسل نسخة من رسائلك وملفاتك إلى المطور للإشراف، "
    "وأنت أوضحت موافقتك على ذلك عند بدء الاستخدام.\n"
    "• لا نبيع أو نشارك بياناتك مع أي جهة خارجية.\n\n"
    "4️⃣ <b>حذف البيانات:</b>\n"
    "• تُحذف ملفاتك المؤقتة تلقائياً بعد المعالجة.\n"
    "• يمكنك حذف جميع بياناتك من زر «حذف بياناتي» في الإعدادات.\n\n"
    "5️⃣ <b>الأمان:</b>\n"
    "• جميع الاتصالات مشفرة (HTTPS).\n"
    "• قاعدة البيانات محمية بكلمة سر المطور فقط."
)

DEVELOPER_TEXT = (
    "👨‍💻 <b>المطور</b>\n"
    "──────────────\n"
    "هذا البوت من تطوير وبرمجة:\n\n"
    "• <b>الاسم:</b> محمد\n"
    "• <b>المنصة:</b> Telegram AI Face Swap Bot Pro\n"
    "• <b>الإصدار:</b> {version}\n\n"
    "لأي استفسار أو اقتراح يرجى التواصل مع المطور."
).format(version=settings.BOT_VERSION)


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض زر المساعدة."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        HELP_TEXT,
        parse_mode="HTML",
        reply_markup=back_keyboard(),
    )


async def about_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض زر "حول البوت"."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        ABOUT_TEXT,
        parse_mode="HTML",
        reply_markup=back_keyboard(),
    )


async def privacy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض زر "سياسة الخصوصية"."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        PRIVACY_TEXT,
        parse_mode="HTML",
        reply_markup=back_keyboard(),
    )


async def developer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    معالج زر "المطور".
    إذا كان الضاغط هو المطور نفسه يعرض لوحة التحكم،
    وإلا يعرض معلومات المطور فقط.
    """
    query = update.callback_query
    await query.answer()
    await ensure_user(update, context)

    # التحقق: هل هذا المستخدم هو المطور؟
    if is_developer(query.from_user.id):
        # استيراد كسول لتجنب الاستيراد الدائري
        from admin.panel import show_dev_panel
        await show_dev_panel(update, context)
        return

    # مستخدم عادي: نعرض معلومات المطور
    await query.edit_message_text(
        DEVELOPER_TEXT,
        parse_mode="HTML",
        reply_markup=back_keyboard(),
    )
