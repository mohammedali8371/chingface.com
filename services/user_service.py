# ================================================================
# ملف services/user_service.py
# -----------------------------
# هذا الملف مسؤول عن منطق التعامل مع المستخدمين.
# يجمع عمليات قاعدة البيانات الخاصة بالمستخدمين في دوال جاهزة
# تستخدمها معالجات البوت (Handlers).
# ================================================================

from typing import Dict, Optional

from telegram import User

from database import db
from logger import get_logger
from utils.helpers import utc_now_iso

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)


class UserService:
    """
    كلاس خدمات المستخدمين.
    ----------------------
    يوفر دوالاً جاهزة للتعامل مع المستخدمين دون الحاجة
    لمعرفة تفاصيل قاعدة البيانات.
    """

    async def register_user(self, telegram_user: User) -> Dict:
        """
        يسجل مستخدماً جديداً أو يحدّث بيانات مستخدم موجود.
        يُستدعى في بداية أي تفاعل مع المستخدم.

        :param telegram_user: كائن المستخدم من تيليجرام.
        :return: بيانات المستخدم من قاعدة البيانات.
        """
        user_id = telegram_user.id
        now = utc_now_iso()

        # نجهز قاموس بيانات المستخدم
        user_data = {
            "user_id": user_id,
            "username": telegram_user.username,
            "first_name": telegram_user.first_name,
            "last_name": telegram_user.last_name,
            "monitoring_agreed": False,
            "prefs": "{}",
            "created_at": now,
            "last_seen": now,
        }

        # التحقق من وجود المستخدم لحفظ تاريخ التسجيل الأصلي
        existing = await db.get_user(user_id)
        if existing:
            user_data["created_at"] = existing.get("created_at") or now

        # تسجيل/تحديث المستخدم
        await db.upsert_user(user_data)
        return await db.get_user(user_id)

    async def get_user(self, user_id: int) -> Optional[Dict]:
        """يُرجع بيانات مستخدم أو None."""
        return await db.get_user(user_id)

    async def is_banned(self, user_id: int) -> bool:
        """يتحقق مما إذا كان المستخدم محظوراً."""
        return await db.is_user_banned(user_id)

    async def has_agreed(self, user_id: int) -> bool:
        """يتحقق مما إذا كان المستخدم وافق على المراقبة الشفافة."""
        user = await db.get_user(user_id)
        return bool(user and user.get("monitoring_agreed"))

    async def set_agreed(self, user_id: int, agreed: bool) -> None:
        """يحفظ موافقة/رفض المستخدم."""
        await db.set_monitoring_agreed(user_id, agreed)

    async def set_pref(self, user_id: int, key: str, value: str) -> None:
        """يضبط تفضيلاً لمستخدم."""
        await db.set_user_pref(user_id, key, value)

    async def get_pref(self, user_id: int, key: str, default: str = "") -> str:
        """يُرجع تفضيلاً لمستخدم."""
        return await db.get_user_pref(user_id, key, default)

    async def touch_last_seen(self, user_id: int) -> None:
        """يحدّث وقت آخر ظهور."""
        await db.update_last_seen(user_id, utc_now_iso())

    async def record_swap(self, user_id: int, swap_type: str) -> None:
        """
        يحدّث عدادات المستخدم بعد نجاح عملية تبديل.
        :param user_id: معرف المستخدم.
        :param swap_type: نوع العملية (image / video).
        """
        await db.increment_user_counter(user_id, "total_requests")
        if swap_type == "image":
            await db.increment_user_counter(user_id, "total_images")
        elif swap_type == "video":
            await db.increment_user_counter(user_id, "total_videos")


# ----------------------------------------------------------------
# كائن عام لخدمة المستخدمين (Singleton)
# ----------------------------------------------------------------
user_service = UserService()
