# ================================================================
# ملف utils/cleanup.py
# --------------------
# هذا الملف مسؤول عن تنظيف الملفات المؤقتة والبيانات القديمة.
#
# لماذا التنظيف الدوري ضروري؟
# ----------------------------
#   1. عمليات تبديل الوجه تنشئ ملفات مؤقتة (صور وفيديوهات).
#   2. بدون تنظيف ستمتلئ مساحة التخزين على الخادم المجاني.
#   3. حذف البيانات بعد المعالجة يحمي خصوصية المستخدمين.
# ================================================================

import asyncio
import shutil
import time
from pathlib import Path
from typing import Optional

from logger import get_logger

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)


def cleanup_temp_files(temp_dir: Path, max_age_seconds: int = 3600) -> int:
    """
    يحذف الملفات المؤقتة التي تجاوز عمرها الحد المسموح.

    :param temp_dir: مجلد الملفات المؤقتة.
    :param max_age_seconds: العمر الأقصى للملفات قبل حذفها (بالثواني).
    :return: عدد الملفات المحذوفة.
    """
    if not temp_dir.exists():
        return 0

    deleted = 0
    now = time.time()
    try:
        # نمر على جميع الملفات داخل مجلد المؤقت (بشكل متكرر)
        for file_path in temp_dir.rglob("*"):
            if not file_path.is_file():
                continue
            # وقت التعديل الأخير للملف
            try:
                mtime = file_path.stat().st_mtime
            except OSError:
                continue
            # إذا تجاوز الملف العمر المسموح نحذفه
            if now - mtime > max_age_seconds:
                try:
                    file_path.unlink(missing_ok=True)
                    deleted += 1
                except OSError as exc:
                    logger.warning(f"فشل حذف {file_path}: {exc}")

        # نحذف المجلدات الفارغة المتبقية
        for folder in sorted(
            (p for p in temp_dir.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True
        ):
            try:
                if not any(folder.iterdir()):
                    folder.rmdir()
            except OSError:
                pass

        if deleted:
            logger.info(f"التنظيف: تم حذف {deleted} ملفاً مؤقتاً")
    except Exception as exc:
        logger.error(f"خطأ أثناء تنظيف الملفات المؤقتة: {exc}")
    return deleted


def clear_directory(directory: Path) -> int:
    """
    يمسح محتويات مجلد بالكامل (يُستخدم لمسح الكاش).

    :param directory: المجلد المراد مسحه.
    :return: عدد العناصر المحذوفة.
    """
    if not directory.exists():
        return 0
    count = 0
    try:
        for item in directory.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)
            count += 1
        logger.info(f"تم مسح المجلد: {directory} ({count} عنصر)")
    except Exception as exc:
        logger.error(f"خطأ أثناء مسح المجلد {directory}: {exc}")
    return count


async def periodic_cleanup(
    temp_dir: Path,
    interval_seconds: int = 1800,
    max_age_seconds: int = 3600,
    stop_event: Optional[asyncio.Event] = None,
) -> None:
    """
    مهمة دورية تعمل في الخلفية لتنظيف الملفات المؤقتة.
    تعمل بشكل مستمر كل فترة زمنية محددة.

    :param temp_dir: مجلد الملفات المؤقتة.
    :param interval_seconds: الفترة بين كل عملية تنظيف.
    :param max_age_seconds: العمر الأقصى للملفات.
    :param stop_event: حدث إيقاف (عند إغلاق التطبيق).
    """
    logger.info(f"بدء مهمة التنظيف الدوري (كل {interval_seconds} ثانية)")
    while True:
        # ننتظر الفترة المحددة (أو حتى الإيقاف)
        if stop_event is not None:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
                break  # طلب إيقاف
            except asyncio.TimeoutError:
                pass  # انتهت الفترة، نواصل
        else:
            await asyncio.sleep(interval_seconds)

        # تنفيذ التنظيف في مؤشر منفصل حتى لا نعطل البوت
        try:
            await asyncio.to_thread(cleanup_temp_files, temp_dir, max_age_seconds)
        except Exception as exc:
            logger.error(f"خطأ في مهمة التنظيف الدوري: {exc}")
