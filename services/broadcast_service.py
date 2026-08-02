# ================================================================
# ملف services/broadcast_service.py
# ---------------------------------
# هذا الملف مسؤول عن إرسال الرسائل الجماعية (Broadcast).
#
# كيف يعمل؟
# ----------
# المطور يكتب رسالة، ثم نرسلها لكل المستخدمين غير المحظورين
# في خلفية (Background Task) حتى لا نعلق لوحة التحكم.
# ================================================================

from typing import Dict, List, Optional, Tuple

from database import db
from logger import get_logger

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)


class BroadcastService:
    """
    كلاس خدمة الإرسال الجماعي.
    ---------------------------
    يوفر دالة إرسال جماعي مع تتبع النتائج (نجح / فشل).
    """

    async def send_to_all(
        self,
        bot,
        text: str,
        parse_mode: str = "HTML",
        exclude_banned: bool = True,
    ) -> Tuple[int, int]:
        """
        يرسل رسالة لجميع المستخدمين المسجلين.

        :param bot: كائن البوت.
        :param text: نص الرسالة.
        :param parse_mode: وضع التنسيق (HTML / Markdown).
        :param exclude_banned: هل نستثني المحظورين؟
        :return: (عدد المرسلة بنجاح، عدد الفاشلة).
        """
        # جلب جميع المستخدمين
        users: List[Dict] = await db.get_all_users()
        sent = 0
        failed = 0

        # تجهيز قائمة المستلمين النهائية
        targets = []
        for user in users:
            if exclude_banned and user.get("is_banned"):
                continue
            targets.append(user.get("user_id"))

        logger.info(f"بدء الإرسال الجماعي إلى {len(targets)} مستخدماً")

        # إرسال الرسالة لكل مستخدم
        for user_id in targets:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode=parse_mode,
                )
                sent += 1
            except Exception as exc:
                # تجاهل الأخطاء الفردية (مستخدم حظر البوت مثلاً)
                failed += 1
                logger.debug(f"فشل إرسال لمستخدم {user_id}: {exc}")

        logger.info(f"انتهى الإرسال الجماعي: نجح {sent}، فشل {failed}")
        return sent, failed


# ----------------------------------------------------------------
# كائن عام لخدمة الإرسال الجماعي (Singleton)
# ----------------------------------------------------------------
broadcast_service = BroadcastService()
