# ================================================================
# ملف main.py
# -----------
# هذا هو ملف التشغيل الرئيسي للتطبيق.
#
# يتم تشغيله عبر:
#   uvicorn main:app --host 0.0.0.0 --port $PORT
#
# مسؤول عن:
#   1. إعداد السجلات (Logging).
#   2. التحقق من صحة الإعدادات.
#   3. الاتصال بقاعدة البيانات وإنشاء الجداول.
#   4. بناء وبدء تطبيق البوت.
#   5. ضبط الـ Webhook على تيليجرام.
#   6. تشغيل مهام الخلفية (التنظيف الدوري).
#   7. إيقاف كل شيء بأمان عند إغلاق التطبيق.
# ================================================================

import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from bot import build_application, setup_webhook
from config import settings
from database import db
from logger import get_logger, setup_logging
from middlewares.auth_middleware import WebhookSecurityMiddleware
from utils.cleanup import periodic_cleanup
from web.health import router as health_router
from web.webhook import router as webhook_router

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)

# حدث إيقاف لمهمة التنظيف الدوري
_stop_event = asyncio.Event()


# ----------------------------------------------------------------
# دورة حياة التطبيق (Startup / Shutdown)
# ----------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    إدارة دورة حياة التطبيق.
    - عند بدء التشغيل: تهيئة كل شيء.
    - عند الإغلاق: إيقاف كل شيء بأمان.
    """
    # ============================================================
    # مرحلة بدء التشغيل
    # ============================================================

    # 1) إعداد نظام السجلات
    setup_logging()

    # 2) التحقق من صحة الإعدادات الأساسية
    try:
        settings.validate()
    except ValueError as exc:
        # إعدادات غير صالحة: نمنع تشغيل البوت ونعرض السبب
        logger.critical(f"إعدادات غير صالحة، إيقاف التشغيل: {exc}")
        raise

    # 3) الاتصال بقاعدة البيانات وإنشاء الجداول
    await db.connect()
    await db.init_schema()
    logger.info("قاعدة البيانات جاهزة ✓")

    # 4) بناء وبدء تطبيق البوت
    application = build_application()
    await application.initialize()
    await application.start()

    # 5) ضبط الـ Webhook على تيليجرام
    #    (يُتخطى عند التجربة المحلية إذا كان ENABLE_WEBHOOK=false)
    if settings.ENABLE_WEBHOOK:
        await setup_webhook(application)
    else:
        logger.warning("الـ Webhook معطّل (ENABLE_WEBHOOK=false) — وضع التشغيل المحلي")

    # 6) تشغيل مهمة التنظيف الدوري في الخلفية
    cleanup_task = asyncio.create_task(
        periodic_cleanup(
            temp_dir=settings.TEMP_DIR,
            interval_seconds=1800,   # كل 30 دقيقة
            max_age_seconds=3600,    # نحذف ملفات عمرها أكثر من ساعة
            stop_event=_stop_event,
        )
    )

    logger.info("🎉 البوت جاهز ويعمل بنجاح!")

    # ============================================================
    # مرحلة الاستقبال (يعمل التطبيق هنا)
    # ============================================================
    try:
        yield
    finally:
        # ============================================================
        # مرحلة إيقاف التشغيل (عند إغلاق التطبيق)
        # ============================================================
        logger.info("جارٍ إيقاف تشغيل التطبيق بأمان...")

        # إيقاف مهمة التنظيف
        _stop_event.set()
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass

        # إيقاف البوت
        await application.stop()
        await application.shutdown()

        # إغلاق قاعدة البيانات
        await db.close()

        logger.info("تم إيقاف التطبيق بنجاح ✓")


# ----------------------------------------------------------------
# إنشاء تطبيق FastAPI
# ----------------------------------------------------------------

app = FastAPI(
    title=settings.BOT_NAME,
    version=settings.BOT_VERSION,
    description="بوت تيليجرام لتبديل الوجه بالذكاء الاصطناعي (Webhook)",
    lifespan=lifespan,
)

# إضافة وسيط الحماية (فحص الرمز السري للـ Webhook)
app.add_middleware(WebhookSecurityMiddleware)

# تسجيل الراوترات
app.include_router(webhook_router)   # نقطة استقبال تحديثات تيليجرام
app.include_router(health_router)    # نقاط فحص الصحة


# ----------------------------------------------------------------
# نقطة تشغيل مباشرة (اختيارية - للتشغيل المحلي)
# ----------------------------------------------------------------

if __name__ == "__main__":
    # للتشغيل المحلي: uvicorn main:app --host 0.0.0.0 --port 8000
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT)
