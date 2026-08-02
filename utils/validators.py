# ================================================================
# ملف utils/validators.py
# ------------------------
# هذا الملف مسؤول عن التحقق من صحة الملفات التي يرسلها المستخدمون.
#
# التحقق ضروري لـ:
#   1. حماية البوت من رفع ملفات ضارة أو ضخمة.
#   2. توفير موارد الخادم (لا نقبل صوراً أكبر من الحد المسموح).
#   3. تحسين تجربة المستخدم (رسائل خطأ واضحة قبل بدء المعالجة).
# ================================================================

from typing import Optional, Tuple

from telegram import Message, Update, Video

from config import settings
from logger import get_logger

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)

# قائمة امتدادات الصور المسموحة (لأمان إضافي)
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# قائمة امتدادات الفيديو المسموحة
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


class ValidationError(Exception):
    """استثناء خاص بأخطاء التحقق من الملفات. الرسالة تُعرض للمستخدم مباشرة."""


def _megabytes_to_bytes(mb: int) -> int:
    """يحول حجم بالميغابايت إلى بايت."""
    return mb * 1024 * 1024


def validate_photo(update: Update) -> Tuple[str, int, str]:
    """
    يتحقق من صورة أرسلها المستخدم ويعيد معلوماتها.
    نختار أكبر حجم للصورة (أفضل جودة للتبديل).

    :param update: التحديث القادم من تيليجرام.
    :return: (file_id، حجم الملف بالبايت، مسار مؤقت مقترح بالامتداد المناسب).
    :raises ValidationError: إذا كانت الصورة غير صالحة أو كبيرة جداً.
    """
    message: Optional[Message] = update.effective_message
    if not message or not message.photo:
        raise ValidationError("أرسل صورة صالحة من فضلك 🖼️")

    # photo قائمة من الأحجام مرتبة تصاعدياً، نأخذ الأكبر (الأخير)
    largest = message.photo[-1]
    file_id = largest.file_id
    file_size = largest.file_size or 0

    # فحص الحجم مقابل الحد المسموح
    max_bytes = _megabytes_to_bytes(settings.MAX_IMAGE_SIZE_MB)
    if file_size > max_bytes:
        raise ValidationError(
            f"حجم الصورة كبير جداً ({format(file_size // 1024)} كيلوبايت).\n"
            f"الحد الأقصى المسموح: {settings.MAX_IMAGE_SIZE_MB} ميجابايت."
        )

    # نحصل على الامتداد الحقيقي من t.me/telegram عن طريق ملف الصورة
    # نختار jpg لأنه التنسيق الأكثر شيوعاً لصور تيليجرام
    suggested_name = f"source_{file_id}.jpg"
    return file_id, file_size, suggested_name


def validate_video(video: Video) -> Tuple[int, str, str]:
    """
    يتحقق من فيديو أرسله المستخدم ويعيد معلوماته.

    :param video: كائن الفيديو من تيليجرام.
    :return: (حجم الملف بالبايت، اسم مقترح، نص تحذير إن وجد).
    :raises ValidationError: إذا كان الفيديو غير صالح.
    """
    if not video:
        raise ValidationError("أرسل فيديو صالحاً من فضلك 🎬")

    # ---------- فحص المدة ----------
    duration = video.duration or 0
    if duration > settings.MAX_VIDEO_DURATION_SECONDS:
        raise ValidationError(
            f"مدة الفيديو ({duration} ثانية) أطول من المسموح.\n"
            f"الحد الأقصى هو {settings.MAX_VIDEO_DURATION_SECONDS} ثانية."
        )

    # ---------- فحص الحجم ----------
    file_size = video.file_size or 0
    max_bytes = _megabytes_to_bytes(settings.MAX_VIDEO_SIZE_MB)
    if file_size > max_bytes:
        raise ValidationError(
            f"حجم الفيديو كبير جداً.\n"
            f"الحد الأقصى المسموح: {settings.MAX_VIDEO_SIZE_MB} ميجابايت."
        )

    # ---------- فحص الامتداد (إن وُجد اسم ملف) ----------
    file_name = video.file_name or "video.mp4"
    ext = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ".mp4"
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise ValidationError(f"صيغة الفيديو غير مدعومة ({ext}).\nالصيغ المدعومة: mp4")

    suggested_name = f"target_{file_name}"
    return file_size, suggested_name, f"المدة: {duration} ثانية"


def validate_extension(filename: str, allowed: set) -> bool:
    """
    يتحقق من أن امتداد ملف ما موجود في قائمة مسموحة.
    :param filename: اسم الملف.
    :param allowed: مجموعة الامتدادات المسموحة.
    """
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in allowed


def is_safe_document(filename: str) -> bool:
    """
    يتحقق من أن ملفاً مرفوعاً (Document) آمن للاستخدام في الاستعادة.
    يُستخدم للتحقق من ملفات رفع قاعدة البيانات.
    نسمح فقط بامتداد db أو sqlite أو sqlite3.
    """
    return validate_extension(filename, {".db", ".sqlite", ".sqlite3"})
