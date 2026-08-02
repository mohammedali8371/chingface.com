# ================================================================
# ملف logger.py
# --------------
# هذا الملف مسؤول عن إعداد نظام السجلات (Logging) الاحترافي.
#
# السجلات ضرورية لـ:
#   1. تتبع كل عمليات البوت (رسائل، تبديلات، أخطاء).
#   2. تسهيل اكتشاف المشاكل وحلها.
#   3. إظهار أخطاء حديثة للمطور من داخل لوحة التحكم.
#
# النظام يحتوي على 3 قنوات إخراج (Handlers):
#   أ) Console Handler   : طباعة السجلات على الشاشة/وحدة التحكم.
#   ب) File Handler      : حفظ السجلات في ملفات مع تدوير تلقائي.
#   ج) Memory Handler    : الاحتفاظ بآخر الأخطاء في الذاكرة
#                          لعرضها للمطور في لوحة التحكم.
# ================================================================

import logging
import sys
from collections import deque
from logging.handlers import RotatingFileHandler
from typing import List

from config import settings

# ----------------------------------------------------------------
# قناة ذاكرة للسجلات
# --------------------
# هذا الكلاس يخزن السجلات (خصوصاً الأخطاء) في قائمة داخلية
# محدودة الحجم، حتى نتمكن من عرض "آخر الأخطاء" للمطور مباشرة.
# ----------------------------------------------------------------
class MemoryLogHandler(logging.Handler):
    """يقوم بتخزين سجلات في الذاكرة (Ring Buffer) لعرضها للمطور."""

    def __init__(self, capacity: int = 300) -> None:
        """
        :param capacity: الحد الأقصى لعدد السجلات المحفوظة في الذاكرة.
        """
        super().__init__()
        # deque بحجم محدد: عند الامتلاء تُحذف أقدم السجلات تلقائياً
        self._records: deque = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        """
        تُستدعى من نظام logging عند تسجيل أي سجل.
        نضيف السجل المنسق إلى الذاكرة الداخلية.
        """
        try:
            self._records.append(self.format(record))
        except Exception:
            # لا نريد أن يكسر فشل التخزين نظام السجلات نفسه
            self.handleError(record)

    def get_records(self, limit: int = 50) -> List[str]:
        """
        يُعيد آخر السجلات المخزنة.
        :param limit: عدد السجلات المطلوبة.
        """
        return list(self._records)[-limit:]


# كائن عام لقناة الذاكرة (نستخدمه في لوحة المطور)
_memory_handler: MemoryLogHandler = MemoryLogHandler()
_memory_handler.setLevel(logging.ERROR)


def setup_logging() -> logging.Logger:
    """
    الدالة الرئيسية لإعداد نظام السجلات.
    يجب استدعاؤها مرة واحدة فقط عند تشغيل التطبيق (في main.py).

    تقوم بـ:
        1. تحديد مستوى التسجيل من الإعدادات.
        2. إنشاء مجلد السجلات إن لم يكن موجوداً.
        3. إضافة القنوات الثلاث (Console / File / Memory).
        4. تقليل ضجيج مكتبات الطرف الثالث.
    """
    # إعداد تنسيق موحد للسجلات
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # جذر نظام السجلات
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # ------------------------------------------------------------
    # 1) قناة وحدة التحكم (Console)
    # ------------------------------------------------------------
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # ------------------------------------------------------------
    # 2) قناة الملف مع تدوير تلقائي
    # ------------------------------------------------------------
    # نتأكد من وجود مجلد السجلات
    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        filename=settings.LOG_DIR / "bot.log",
        maxBytes=5 * 1024 * 1024,  # 5 ميجابايت لكل ملف
        backupCount=5,             # نحتفظ بـ 5 نسخ قديمة كحد أقصى
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # ------------------------------------------------------------
    # 3) قناة الذاكرة (Memory) لتظهر للمطور في لوحة التحكم
    # ------------------------------------------------------------
    root_logger.addHandler(_memory_handler)

    # ------------------------------------------------------------
    # تقليل ضجيج المكتبات الخارجية
    # ------------------------------------------------------------
    # httpx مكتبة HTTP المستخدمة من قبل مكتبة تيليجرام
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # urllib3 مكتبة الطلبات
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    # onnxruntime محرك الذكاء الاصطناعي
    logging.getLogger("onnxruntime").setLevel(logging.WARNING)

    # سجل بداية النظام
    root_logger.info("تم إعداد نظام السجلات بنجاح ✓")
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    دالة مساعدة لإرجاع Logger مخصص لأي وحدة (Module).
    مثال: logger = get_logger(__name__)

    :param name: اسم الوحدة (عادة __name__).
    """
    return logging.getLogger(name)


def get_recent_errors(limit: int = 50) -> List[str]:
    """
    يُعيد آخر الأخطاء المسجلة في الذاكرة.
    تُستخدم في لوحة المطور لعرض "سجل الأخطاء".

    :param limit: عدد الأخطاء المطلوب عرضها.
    """
    return _memory_handler.get_records(limit)
