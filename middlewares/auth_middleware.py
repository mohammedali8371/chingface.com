# ================================================================
# ملف middlewares/auth_middleware.py
# -----------------------------------
# هذا الملف مسؤول عن حماية نقاط الخادم من الوصول غير المصرح به.
#
# أهم نقطة حماية: /webhook
# -------------------------
# تيليجرام يرسل التحديثات عبر POST إلى /webhook مع ترويسة
# X-Telegram-Bot-Api-Secret-Token تحمل الرمز السري الذي ضبطناه.
# بدون هذا الرمز يجب رفض الطلب فوراً (أي طلب دخيل لا يصل للبوت).
#
# هذا الوسيط يعمل على مستوى FastAPI (يمر قبل جميع الرواتر).
# ================================================================

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings
from logger import get_logger

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)


class WebhookSecurityMiddleware(BaseHTTPMiddleware):
    """
    وسيط الحماية الرئيسي.
    ---------------------
    مسؤول عن:
      1. رفض طلبات /webhook التي لا تحمل الرمز السري الصحيح.
      2. إضافة ترويسات أمان عامة على جميع الردود.
    """

    async def dispatch(self, request: Request, call_next):
        # ---------- حماية نقطة الـ Webhook ----------
        if request.url.path == "/webhook":
            # نقرأ الرمز السري من الترويسة
            secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")

            # مقارنة آمنة (نستخدم == البسيطة لأن الحجم ثابت ولا يوجد
            # حساسية زمنية مؤثرة هنا؛ لكن في بيئة إنتاجية كبيرة يمكن
            # استخدام hmac.compare_digest)
            if secret != settings.effective_secret():
                # تسجيل محاولة الوصول غير المصرح به
                client_ip = request.client.host if request.client else "unknown"
                logger.warning(f"محاولة وصول غير مصرح بها إلى /webhook من {client_ip}")
                return JSONResponse(status_code=401, content={"error": "unauthorized"})

        # ---------- تمرير الطلب للمعالجة ----------
        response = await call_next(request)

        # ---------- إضافة ترويسات أمان عامة ----------
        # منع المتصفحات من تخمين نوع المحتوى (حماية من هجمات MIME sniffing)
        response.headers["X-Content-Type-Options"] = "nosniff"
        # منع تشغيل الصفحة داخل إطار (Clickjacking protection)
        response.headers["X-Frame-Options"] = "DENY"

        return response
