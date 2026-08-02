# ================================================================
# ملف web/webhook.py
# -------------------
# هذا الملف يحتوي على نقطة استقبال تحديثات تيليجرام (Webhook).
#
# كيف يعمل الـ Webhook؟
# ----------------------
# بدلاً من أن يسأل البوت تيليجرام عن الرسائل الجديدة (Polling)،
# يقوم تيليجرام بإرسال التحديثات مباشرة إلى عنواننا عبر HTTP POST.
#
# تسلسل الاستقبال:
#   1. تيليجرام يرسل JSON إلى /webhook (مع ترويسة الرمز السري).
#   2. نتحقق من الرمز السري (حماية إضافية فوق الميدل وير).
#   3. نحول JSON إلى كائن Update.
#   4. نمرره لتطبيق البوت للمعالجة (process_update).
#   5. نرد بـ {"ok": true} بسرعة حتى لا يعيد تيليجرام الإرسال.
# ================================================================

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from telegram import Update

from bot import get_application
from config import settings
from logger import get_logger

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)

# الراوتر الخاص بهذه النقطة
router = APIRouter()


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """
    نقطة استقبال التحديثات من تيليجرام.
    تُستدعى من تيليجرام عند كل رسالة/ضغطة زر جديدة.

    :param request: طلب HTTP الوارد من تيليجرام.
    :return: {"ok": true} دائماً حتى لو فشل المعالجة
             (حتى لا تتكدس التحديثات ويُعاد إرسالها).
    """
    # ---------- التحقق من الرمز السري (حماية مزدوجة) ----------
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret != settings.effective_secret():
        logger.warning("طلب Webhook بدون رمز سري صحيح")
        return JSONResponse(status_code=401, content={"error": "unauthorized"})

    try:
        # ---------- قراءة بيانات التحديث ----------
        data = await request.json()

        # ---------- الحصول على تطبيق البوت ----------
        application = get_application()

        # ---------- تحويل JSON إلى كائن Update ----------
        update = Update.de_json(data, application.bot)

        # ---------- معالجة التحديث ----------
        if update is not None:
            await application.process_update(update)
        else:
            logger.warning("استلمنا تحديثاً فارغاً من تيليجرام")
    except Exception as exc:
        # لا نعيد خطأ لتيليجرام (سيعيد الإرسال ويسبب ازدحاماً).
        # نسجل الخطأ فقط ثم نرد بـ ok.
        logger.error(f"خطأ أثناء معالجة Webhook: {exc}")

    # نرد فوراً بـ ok (تيليجرام يتوقع رداً سريعاً)
    return {"ok": True}
