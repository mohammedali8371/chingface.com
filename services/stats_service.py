# ================================================================
# ملف services/stats_service.py
# ------------------------------
# هذا الملف مسؤول عن تجميع الإحصائيات الكاملة للوحة المطور.
#
# الإحصائيات المطلوبة:
#   - عدد المستخدمين.
#   - عدد الصور المبدلة.
#   - عدد الفيديوهات المبدلة.
#   - عدد الطلبات.
#   - عدد الرسائل.
#   - عدد الأخطاء.
#   - وقت التشغيل (Uptime).
#   - استهلاك الذاكرة.
#   - استهلاك المعالج.
# ================================================================

import os
import time
from typing import Dict

import psutil

from database import db
from logger import get_logger
from models.schemas import StatsSnapshot

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)

# وقت بدء تشغيل التطبيق (يُضبط في main.py عند البدء)
START_TIME: float = time.time()


class StatsService:
    """
    كلاس تجميع الإحصائيات.
    -----------------------
    يجمع البيانات من قاعدة البيانات ومن نظام التشغيل
    ويعيدها ككائن StatsSnapshot جاهز للعرض.
    """

    async def get_snapshot(self) -> StatsSnapshot:
        """
        يجمع لقطة إحصائيات كاملة.

        :return: كائن StatsSnapshot يحتوي كل الإحصائيات.
        """
        # ---------- إحصائيات من قاعدة البيانات ----------
        users = await db.count_users()
        images = await db.count_swaps("image")
        videos = await db.count_swaps("video")
        requests = await db.sum_requests()
        messages = await db.count_messages()
        errors = await db.count_errors()

        # ---------- إحصائيات النظام ----------
        # وقت التشغيل: الوقت المنقضي منذ بدء التطبيق
        uptime = int(time.time() - START_TIME)

        # الذاكرة المستهلكة بالكيلوبايت
        try:
            memory_bytes = psutil.Process(os.getpid()).memory_info().rss
            memory_mb = memory_bytes / (1024 * 1024)
        except Exception:
            memory_mb = 0.0

        # استخدام المعالج
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
        except Exception:
            cpu_percent = 0.0

        # تجميع كل شيء في كائن واحد
        return StatsSnapshot(
            users=users,
            images=images,
            videos=videos,
            requests=requests,
            messages=messages,
            errors=errors,
            uptime_seconds=uptime,
            memory_mb=round(memory_mb, 1),
            cpu_percent=round(cpu_percent, 1),
        )

    def format_uptime(self, seconds: int) -> str:
        """
        يحول الثواني إلى صيغة مقروءة.
        مثال: 3661 -> "1 ساعة، 1 دقيقة، 1 ثانية"
        """
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, secs = divmod(rem, 60)

        parts = []
        if days:
            parts.append(f"{days} يوم")
        if hours:
            parts.append(f"{hours} ساعة")
        if minutes:
            parts.append(f"{minutes} دقيقة")
        parts.append(f"{secs} ثانية")
        return "، ".join(parts)

    def snapshot_to_text(self, snap: StatsSnapshot) -> str:
        """
        يحول لقطة الإحصائيات إلى نص منسق لعرضه في تيليجرام.

        :param snap: كائن StatsSnapshot.
        """
        return (
            "📊 <b>لوحة الإحصائيات</b>\n"
            "──────────────\n"
            f"👥 المستخدمون: <b>{snap.users}</b>\n"
            f"🖼️ الصور المبدلة: <b>{snap.images}</b>\n"
            f"🎬 الفيديوهات المبدلة: <b>{snap.videos}</b>\n"
            f"🔁 إجمالي الطلبات: <b>{snap.requests}</b>\n"
            f"💬 الرسائل المستلمة: <b>{snap.messages}</b>\n"
            f"⚠️ الأخطاء: <b>{snap.errors}</b>\n"
            "──────────────\n"
            f"🕒 وقت التشغيل: {self.format_uptime(snap.uptime_seconds)}\n"
            f"🧠 الذاكرة: <b>{snap.memory_mb} MB</b>\n"
            f"⚙️ المعالج: <b>{snap.cpu_percent}%</b>"
        )


# ----------------------------------------------------------------
# كائن عام لخدمة الإحصائيات (Singleton)
# ----------------------------------------------------------------
stats_service = StatsService()
