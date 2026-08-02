# ================================================================
# ملف utils/rate_limiter.py
# --------------------------
# هذا الملف مسؤول عن الحماية من الـ Spam والـ Flood.
#
# الفكرة:
# نسمح لكل مستخدم بإرسال عدد محدود من الطلبات خلال فترة زمنية
# معينة. إذا تجاوز الحد، يُرفض طلبه مؤقتاً.
#
# مثال: حد أقصى 5 طلبات في الدقيقة لكل مستخدم.
# ================================================================

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque

from config import settings
from logger import get_logger

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)


class RateLimiter:
    """
    كلاس حماية معدل الطلبات (Rate Limiter).
    ----------------------------------------
    مسؤول عن:
        1. تتبع الطلبات لكل مفتاح (عادة معرف المستخدم).
        2. رفض الطلبات التي تتجاوز الحد المسموح.
        3. تنظيف السجلات القديمة تلقائياً لتوفير الذاكرة.

    ملاحظة: هذا التطبيق يعمل في الذاكرة (أسرع) وهو مناسب لخادم
    واحد. عند التوسع لعدة خوادم يمكن استبداله بـ Redis.
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        """
        :param max_requests: الحد الأقصى لعدد الطلبات المسموحة.
        :param window_seconds: الفترة الزمنية (بالثواني) التي يحسب فيها الحد.
        """
        # قاموس: مفتاح -> قائمة من أوقات الطلبات السابقة
        self._requests: dict = defaultdict(lambda: deque())
        # قفل لحماية القاموس عند العمل المتزامن
        self._lock = Lock()
        self._max_requests = max_requests
        self._window_seconds = window_seconds

    def is_allowed(self, key: int) -> bool:
        """
        يتحقق مما إذا كان الطلب الحالي مسموحاً به.
        إذا كان مسموحاً يسجل الطلب ويعيد True.

        :param key: المفتاح (معرف المستخدم عادة).
        """
        now = time.time()
        with self._lock:
            # قائمة طلبات هذا المستخدم
            history: Deque = self._requests[key]

            # نحذف الطلبات الأقدم من النافذة الزمنية
            while history and now - history[0] > self._window_seconds:
                history.popleft()

            # إذا تجاوزنا الحد نرفض الطلب
            if len(history) >= self._max_requests:
                logger.warning(f"منع طلب من مفتاح {key}: تجاوز حد الطلبات")
                return False

            # نسمح بالطلب ونسجله
            history.append(now)
            return True

    def reset(self, key: int = None) -> None:
        """
        يصفّر سجل طلبات مفتاح معين (أو الكل).
        :param key: إن كان محدداً يصفّر له فقط، وإلا يصفّر الكل.
        """
        with self._lock:
            if key is None:
                self._requests.clear()
            else:
                self._requests.pop(key, None)

    def clean_old(self) -> None:
        """يحذف السجلات القديمة لتوفير الذاكرة (يُستدعى دورياً)."""
        now = time.time()
        with self._lock:
            expired = [
                key
                for key, history in self._requests.items()
                if not history or now - history[-1] > self._window_seconds * 2
            ]
            for key in expired:
                del self._requests[key]


# ----------------------------------------------------------------
# كائن عام لنظام الحماية
# ----------------------------------------------------------------
# ننشئ كائناً واحداً يستخدمه المشروع كله، قيمه من الإعدادات.
# ----------------------------------------------------------------
rate_limiter = RateLimiter(
    max_requests=settings.MAX_REQUESTS_PER_MINUTE,
    window_seconds=60,
)
