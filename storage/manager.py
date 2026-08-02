# ================================================================
# ملف storage/manager.py
# ----------------------
# هذا الملف مسؤول عن إدارة جميع الملفات في المشروع:
#   1. تنزيل الملفات من تيليجرام (صور وفيديوهات).
#   2. حفظ الملفات في مجلدات مؤقتة خاصة بكل مستخدم.
#   3. حذف الملفات المؤقتة بعد انتهاء المعالجة.
#   4. إدارة النسخ الاحتياطية لقاعدة البيانات.
#   5. توفير مسارات جاهزة لملفات النماذج.
# ================================================================

import shutil
import time
import uuid
from pathlib import Path
from typing import Optional

from config import settings
from logger import get_logger
from utils.helpers import utc_now_iso

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)


class StorageManager:
    """
    الكلاس الرئيسي لإدارة التخزين.
    --------------------------------
    مسؤول عن:
        - إنشاء المجلدات اللازمة عند أول تشغيل.
        - إنشاء مسارات مؤقتة فريدة لكل عملية.
        - تنزيل الملفات من تيليجرام.
        - حذف الملفات المؤقتة بأمان.
        - إنشاء واستعادة النسخ الاحتياطية.
    """

    def __init__(self) -> None:
        # نسخ من المسارات من الإعدادات (لسهولة الاستخدام)
        self.storage_dir: Path = settings.STORAGE_DIR
        self.temp_dir: Path = settings.TEMP_DIR
        self.models_dir: Path = settings.MODELS_DIR
        self.backup_dir: Path = settings.BACKUP_DIR
        self.db_path: Path = settings.DB_PATH

        # إنشاء جميع المجلدات المطلوبة
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """ينشئ جميع المجلدات اللازمة إن لم تكن موجودة."""
        for directory in (self.storage_dir, self.temp_dir, self.models_dir, self.backup_dir):
            directory.mkdir(parents=True, exist_ok=True)
        logger.info("تم تجهيز مجلدات التخزين ✓")

    # ============================================================
    # الملفات المؤقتة
    # ============================================================

    def user_temp_dir(self, user_id: int) -> Path:
        """
        يُرجع مجلداً مؤقتاً خاصاً بمستخدم معين.
        المجلد: temp/user_<id>
        """
        folder = self.temp_dir / f"user_{user_id}"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def new_temp_file(self, user_id: int, extension: str = ".jpg") -> Path:
        """
        ينشئ مسار ملف مؤقت فريد لمستخدم.
        نستخدم uuid لضمان عدم تكرار الأسماء حتى مع نفس المستخدم.

        :param user_id: معرف المستخدم.
        :param extension: امتداد الملف (مثال .jpg أو .mp4).
        """
        folder = self.user_temp_dir(user_id)
        unique_name = f"{int(time.time())}_{uuid.uuid4().hex[:8]}{extension}"
        return folder / unique_name

    async def download_telegram_file(
        self, bot, file_id: str, destination: Path
    ) -> Optional[Path]:
        """
        ينزل ملفاً من تيليجرام إلى المسار المحدد.

        :param bot: كائن البوت.
        :param file_id: معرف الملف في تيليجرام.
        :param destination: المسار الذي سيُحفظ فيه الملف.
        :return: المسار الكامل للملف المحفوظ، أو None عند الفشل.
        """
        try:
            # نحصل على معلومات الملف من تيليجرام
            file = await bot.get_file(file_id)
            # ننزله إلى القرص
            await file.download_to_drive(destination)
            logger.debug(f"تم تنزيل الملف {file_id} إلى {destination}")
            return destination
        except Exception as exc:
            logger.error(f"فشل تنزيل الملف {file_id}: {exc}")
            return None

    def remove_file(self, path: Path) -> None:
        """
        يحذف ملفاً بأمان (يتجاهل الأخطاء ولا يرمي استثناءات).
        :param path: المسار المطلوب حذفه.
        """
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning(f"فشل حذف الملف {path}: {exc}")

    def cleanup_user_temp(self, user_id: int) -> None:
        """يحذف مجلد المستخدم المؤقت بالكامل (بعد انتهاء المعالجة)."""
        folder = self.user_temp_dir(user_id)
        try:
            shutil.rmtree(folder, ignore_errors=True)
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning(f"فشل تنظيف مجلد المستخدم {user_id}: {exc}")

    def clear_all_temp(self) -> int:
        """يمسح كل الملفات المؤقتة (يُستخدم في زر "مسح الكاش")."""
        count = 0
        try:
            for item in self.temp_dir.iterdir():
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
                count += 1
        except OSError as exc:
            logger.warning(f"فشل مسح الملفات المؤقتة: {exc}")
        logger.info(f"تم مسح الكاش المؤقت ({count} عنصر)")
        return count

    def temp_total_size(self) -> int:
        """يُرجع الحجم الإجمالي للملفات المؤقتة بالبايت."""
        total = 0
        for file_path in self.temp_dir.rglob("*"):
            if file_path.is_file():
                try:
                    total += file_path.stat().st_size
                except OSError:
                    pass
        return total

    # ============================================================
    # قاعدة البيانات والنسخ الاحتياطية
    # ============================================================

    def get_db_bytes(self) -> bytes:
        """يقرأ ملف قاعدة البيانات ويعيده كبايتات (لتنزيله للمطور)."""
        try:
            return self.db_path.read_bytes()
        except OSError as exc:
            logger.error(f"فشل قراءة قاعدة البيانات: {exc}")
            return b""

    def replace_db(self, data: bytes) -> bool:
        """
        يستبدل ملف قاعدة البيانات الحالي ببيانات جديدة.
        يُستخدم في زر "رفع قاعدة البيانات".

        :param data: محتوى قاعدة البيانات الجديدة.
        """
        try:
            # نحفظ نسخة احتياطية سريعة من القاعدة الحالية قبل الاستبدال
            backup_name = self.create_backup(prefix="auto_before_upload")
            self.db_path.write_bytes(data)
            logger.info(f"تم استبدال قاعدة البيانات (نسخة احتياطية: {backup_name})")
            return True
        except OSError as exc:
            logger.error(f"فشل استبدال قاعدة البيانات: {exc}")
            return False

    def create_backup(self, prefix: str = "backup") -> Path:
        """
        ينشئ نسخة احتياطية من قاعدة البيانات.

        :param prefix: بادئة اسم ملف النسخة.
        :return: مسار ملف النسخة الاحتياطية.
        """
        # اسم فريد يحتوي على الوقت
        timestamp = utc_now_iso().replace(":", "-").replace(".", "-")
        backup_path = self.backup_dir / f"{prefix}_{timestamp}.db"
        try:
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"تم إنشاء نسخة احتياطية: {backup_path.name}")
            return backup_path
        except OSError as exc:
            logger.error(f"فشل إنشاء نسخة احتياطية: {exc}")
            raise

    def list_backup_files(self) -> list:
        """يُرجع قائمة ملفات النسخ الاحتياطية الموجودة فعلياً على القرص."""
        if not self.backup_dir.exists():
            return []
        return sorted(self.backup_dir.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)

    def backup_path(self, filename: str) -> Optional[Path]:
        """
        يُرجع المسار الكامل لملف نسخة احتياطية إن كان موجوداً.

        :param filename: اسم ملف النسخة الاحتياطية.
        """
        candidate = self.backup_dir / filename
        return candidate if candidate.exists() else None

    def restore_backup_file(self, filename: str) -> Optional[Path]:
        """
        يعيد ملف قاعدة البيانات من نسخة احتياطية.

        :param filename: اسم ملف النسخة الاحتياطية.
        :return: مسار الملف المستعاد، أو None إن لم يوجد.
        """
        backup = self.backup_path(filename)
        if backup is None:
            return None
        try:
            shutil.copy2(backup, self.db_path)
            logger.info(f"تمت استعادة النسخة الاحتياطية: {filename}")
            return backup
        except OSError as exc:
            logger.error(f"فشل استعادة النسخة الاحتياطية: {exc}")
            return None


# ----------------------------------------------------------------
# المثيل الوحيد المشترك (Singleton)
# تُستورد منه هذه الوحدة في جميع أنحاء المشروع:
#   from storage.manager import storage
# ----------------------------------------------------------------
storage = StorageManager()
