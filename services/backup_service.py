# ================================================================
# ملف services/backup_service.py
# -------------------------------
# هذا الملف مسؤول عن منطق النسخ الاحتياطية لقاعدة البيانات.
# يجمع بين عمليات التخزين (storage/manager) وقاعدة البيانات
# (تسجيل النسخ في جدول backups).
# ================================================================

from typing import Optional

from database import db
from logger import get_logger
from storage.manager import storage
from utils.helpers import utc_now_iso

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)


class BackupService:
    """
    كلاس خدمة النسخ الاحتياطية.
    ----------------------------
    يوفر عمليات: إنشاء نسخة، قائمة النسخ، استعادة نسخة.
    """

    async def create_backup(self) -> Optional[str]:
        """
        ينشئ نسخة احتياطية من قاعدة البيانات ويسجلها.

        :return: اسم ملف النسخة الاحتياطية أو None عند الفشل.
        """
        try:
            # إنشاء النسخة على القرص
            backup_path = storage.create_backup(prefix="backup")
            # تسجيلها في قاعدة البيانات
            await db.add_backup(backup_path.name, backup_path.stat().st_size)
            logger.info(f"تم إنشاء نسخة احتياطية: {backup_path.name}")
            return backup_path.name
        except Exception as exc:
            logger.error(f"فشل إنشاء النسخة الاحتياطية: {exc}")
            return None

    async def list_backups(self, limit: int = 20) -> list:
        """يُرجع قائمة النسخ الاحتياطية من قاعدة البيانات."""
        return await db.list_backups(limit)

    async def restore_backup(self, filename: str) -> bool:
        """
        يستعيد نسخة احتياطية.

        :param filename: اسم ملف النسخة الاحتياطية.
        :return: True عند النجاح، False عند الفشل.
        """
        # البحث عن الملف على القرص
        backup_path = storage.backup_path(filename)
        if backup_path is None:
            logger.warning(f"نسخة احتياطية غير موجودة: {filename}")
            return False

        # استعادة الملف (نسخه مكان قاعدة البيانات الحالية)
        restored = storage.restore_backup_file(filename)
        if restored is None:
            return False

        # إعادة الاتصال بقاعدة البيانات (بعد استبدال الملف)
        await db.reconnect()
        # إعادة إنشاء الجداول إذا كانت القاعدة المستعادة حديثة
        await db.init_schema()
        logger.info(f"تمت استعادة النسخة الاحتياطية: {filename}")
        return True

    async def list_disk_backups(self) -> list:
        """يُرجع قائمة النسخ الموجودة فعلياً على القرص."""
        return storage.list_backup_files()


# ----------------------------------------------------------------
# المثيل الوحيد المشترك (Singleton)
# تُستورد منه هذه الوحدة في جميع أنحاء المشروع:
#   from services.backup_service import backup_service
# ----------------------------------------------------------------
backup_service = BackupService()
