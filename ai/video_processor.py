# ================================================================
# ملف ai/video_processor.py
# --------------------------
# هذا الملف مسؤول عن تبديل الوجه في الفيديو.
#
# كيف يعمل؟
# ----------
# الفيديو عبارة عن مجموعة صور (إطارات/فريمات) متتالية.
# لذلك نقوم بـ:
#   1. قراءة الفيديو إطاراً بإطار عبر OpenCV.
#   2. تطبيق نفس خوارزمية تبديل الوجه على كل إطار.
#   3. إعادة تجميع الإطارات في فيديو جديد.
#   4. دمج الصوت الأصلي + تحويل الترميز إلى H.264 (عبر FFmpeg
#      إن كان متاحاً) لضمان التوافق مع مشغلات تيليجرام.
#
# الحفاظ على الجودة:
#   - نحافظ على الدقة (Resolution) ومعدل الإطارات (FPS) الأصليين.
#   - نستخدم bitrate عالياً في الضغط النهائي لتقليل الفقد.
#
# ملاحظة: هذه العملية كثيفة الموارد، لذلك ننفذها خارج حلقة
# الأحداث (في مؤشر منفصل) حتى لا نبطئ استجابة البوت.
# ================================================================

import shutil
import subprocess
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from ai.face_swapper import NoFaceError, face_swapper
from config import settings
from logger import get_logger

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)


def _find_ffmpeg() -> Optional[str]:
    """
    يبحث عن ملف FFmpeg في النظام.
    :return: مسار FFmpeg أو None إن لم يكن موجوداً.
    """
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path
    # محاولة أخيرة: المسار الشائع في بيئات Render / Linux
    for candidate in ("/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        if Path(candidate).exists():
            return candidate
    logger.warning("FFmpeg غير موجود، سيُحفظ الفيديو بدون صوت وبترميز mp4v")
    return None


def _convert_with_ffmpeg(
    ffmpeg: str,
    input_video: Path,
    raw_video: Path,
    output_video: Path,
) -> Path:
    """
    يحوّل الفيديو الخام إلى ترميز H.264 ويدمج الصوت الأصلي.

    :param ffmpeg: مسار ملف FFmpeg.
    :param input_video: الفيديو الأصلي (مصدر الصوت).
    :param raw_video: الفيديو الخام بعد المعالجة (بدون صوت).
    :param output_video: الفيديو النهائي.
    """
    try:
        command = [
            ffmpeg,
            "-y",                        # تجاوز الملفات الموجودة
            "-i", str(raw_video),        # المدخل 1: الفيديو المعالج
            "-i", str(input_video),      # المدخل 2: الفيديو الأصلي (للصوت)
            "-map", "0:v:0",             # خذ الفيديو من المدخل الأول
            "-map", "1:a:0",             # خذ الصوت من المدخل الثاني (إن وجد)
            "-c:v", "libx264",           # ترميز فيديو H.264 (متوافق مع كل شيء)
            "-preset", "fast",
            "-crf", "20",                # جودة عالية (كلما قل الرقم زادت الجودة)
            "-c:a", "aac",               # ترميز صوت
            "-b:a", "128k",
            "-shortest",                 # قص الناتج لأقصر مدخل (حماية من عدم التطابق)
            "-movflags", "+faststart",   # تشغيل أسرع على الهواتف
            "-pix_fmt", "yuv420p",       # توافق كامل مع المشغلات
            str(output_video),
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            timeout=600,  # مهلة أمان 10 دقائق
            check=True,
        )
        logger.info(f"تم تحويل الفيديو عبر FFmpeg بنجاح: {output_video}")
        return output_video
    except subprocess.CalledProcessError as exc:
        logger.error(f"فشل FFmpeg: {exc.stderr.decode('utf-8', 'ignore')[:500]}")
        # في حالة الفشل نعيد الفيديو الخام (بدون صوت) كحل احتياطي
        return raw_video
    except Exception as exc:
        logger.error(f"خطأ غير متوقع في FFmpeg: {exc}")
        return raw_video


def process_video(
    source_path: Path,
    video_path: Path,
    output_path: Path,
    max_duration: Optional[int] = None,
    enable_enhance: bool = True,
    enhance_level: str = "high",
) -> Path:
    """
    ينفذ تبديل الوجه على فيديو كامل ويحفظ النتيجة.

    :param source_path: مسار صورة الوجه (المصدر).
    :param video_path: مسار الفيديو الهدف.
    :param output_path: مسار حفظ النتيجة.
    :param max_duration: الحد الأقصى للفريمات المعالجة (بالثواني).
    :param enable_enhance: هل نفعّل تحسين الجودة لكل إطار؟
    :param enhance_level: مستوى التحسين.
    :return: مسار الفيديو الناتج.
    """
    logger.info(f"بدء معالجة الفيديو: {video_path.name}")

    # ---------- فتح الفيديو الأصلي ----------
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError("تعذر فتح الفيديو. تأكد من سلامة الملف.")

    # قراءة خصائص الفيديو
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # فرض حد المدة إن وجد
    max_frames = total_frames
    if max_duration:
        max_frames = min(total_frames, int(max_duration * fps))

    # حماية من الدقة الصفرية أو الكبيرة جداً
    if width <= 0 or height <= 0:
        cap.release()
        raise ValueError("الفيديو لا يحتوي على بيانات صالحة.")

    # ---------- تجهيز كاتب الفيديو الخام ----------
    # نستخدم ترميز mp4v مؤقتاً ثم نحوله لاحقاً لـ H.264
    raw_output = output_path.with_suffix(".raw.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(raw_output), fourcc, fps, (width, height))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError("تعذر إنشاء ملف الفيديو الناتج.")

    # ---------- تحضير نماذج الوجه (مرة واحدة) ----------
    source_img = cv2.imread(str(source_path))
    if source_img is None:
        cap.release()
        writer.release()
        raise ValueError("تعذر قراءة صورة الوجه.")

    models = face_swapper.models
    face_app = models.get_face_app()
    swapper = models.get_swapper()

    # استخراج وجه المصدر
    source_faces = face_app.get(source_img)
    if not source_faces:
        cap.release()
        writer.release()
        raise NoFaceError("source")
    source_face = source_faces[0]

    # ---------- معالجة الإطارات ----------
    frame_index = 0
    processed_frames = 0
    skipped_frames = 0

    while frame_index < max_frames:
        # نقرأ الإطار التالي (مباشرة إلى max_frames)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, frame = cap.read()
        if not ret:
            break

        try:
            # اكتشاف الوجوه في الإطار الحالي
            faces = face_app.get(frame)
            result = frame.copy()

            if faces:
                # تبديل كل وجه في الإطار
                for face in faces:
                    result = swapper.get(result, face, source_face, paste_back=True)
                # التحسين الخفيف حسب الإعدادات (اختياري لتوفير الوقت)
                if enable_enhance and enhance_level != "off":
                    # نطبقه فقط على كل إطار (خفيف جداً)
                    from ai.enhancer import FaceEnhancer

                    temp_enhancer = FaceEnhancer(enabled=True, level=enhance_level)
                    result = temp_enhancer.enhance(result)
                processed_frames += 1
            else:
                # إطار بدون وجوه: نمرره كما هو
                skipped_frames += 1

            writer.write(result)
        except Exception as exc:
            logger.warning(f"خطأ في الإطار {frame_index}: {exc}")
            # نكتب الإطار الأصلي لضمان استمرارية الفيديو
            writer.write(frame)

        # نعدّل القراءة: نزيد بخطوة 1 إطار (تطابق طبيعي)
        frame_index += 1

    # ---------- إنهاء الكتابة ----------
    cap.release()
    writer.release()

    logger.info(
        f"تمت معالجة الفيديو: {processed_frames} إطاراً بـ وجوه، "
        f"{skipped_frames} إطاراً بدون وجوه"
    )

    # ---------- تحويل ودمج الصوت عبر FFmpeg ----------
    ffmpeg = _find_ffmpeg()
    final_path: Path = output_path
    if ffmpeg:
        final_path = _convert_with_ffmpeg(ffmpeg, video_path, raw_output, output_path)
    else:
        # لا يوجد FFmpeg: نستخدم الفيديو الخام مباشرة
        shutil.move(str(raw_output), str(output_path))

    # تنظيف الملف الخام المؤقت إن بقي
    if raw_output.exists() and raw_output != output_path:
        try:
            raw_output.unlink(missing_ok=True)
        except OSError:
            pass

    logger.info(f"تم الانتهاء من الفيديو: {output_path}")
    return final_path
