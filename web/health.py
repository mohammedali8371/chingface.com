# ================================================================
# ملف web/health.py
# -----------------
# هذا الملف يحتوي على نقاط فحص الصحة (Health Checks).
#
# لماذا نحتاجها؟
# ---------------
#   1. Render (وغيرها من منصات الاستضافة) يفحص الخدمة بشكل دوري
#      للتأكد من أنها تعمل (وليس معلقة).
#   2. تساعد المطور على مراقبة حالة الخادم بسرعة.
# ================================================================

import os
import time

import psutil
from fastapi import APIRouter

from config import settings
from database import db
from logger import get_logger
from services.stats_service import START_TIME

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)

# الراوتر الخاص بنقاط الفحص
router = APIRouter()


@router.get("/health")
async def health():
    """
    نقطة فحص صحة الخدمة.
    تُرجع حالة عامة + مؤشرات أساسية (قاعدة البيانات، الذاكرة، ...).
    """
    # هل قاعدة البيانات متصلة؟
    db_connected = db.is_connected()

    # ذاكرة العملية الحالية
    try:
        memory_mb = round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 1)
    except Exception:
        memory_mb = 0.0

    # استخدام المعالج
    try:
        cpu = psutil.cpu_percent(interval=0.1)
    except Exception:
        cpu = 0.0

    return {
        "status": "ok" if db_connected else "degraded",
        "name": settings.BOT_NAME,
        "version": settings.BOT_VERSION,
        "uptime_seconds": int(time.time() - START_TIME),
        "db_connected": db_connected,
        "memory_mb": memory_mb,
        "cpu_percent": cpu,
    }


@router.get("/")
async def index():
    """نقطة جذر بسيطة (للمتصفح أو لفحص أولي)."""
    return {
        "status": "running",
        "name": settings.BOT_NAME,
        "message": "Telegram AI Face Swap Bot Pro is running",
    }
