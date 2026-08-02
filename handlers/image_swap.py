# ================================================================
# ملف handlers/image_swap.py
# ---------------------------
# هذا الملف مسؤول عن عملية تبديل الوجه في الصور.
#
# مراحل العملية (حالة محادثة):
#   1. IMAGE_SWAP_SOURCE: يطلب صورة الوجه (المصدر).
#   2. IMAGE_SWAP_TARGET: يطلب الصورة الهدف.
#   3. بعد استلام الهدف: تُنفذ المعالجة في الخلفية (Background Task)
#      حتى لا يتجمد البوت أثناء المعالجة الثقيلة.
# ================================================================

import asyncio
import time
from pathlib import Path

from telegram import InputFile, Update
from telegram.ext import ContextTypes, ConversationHandler

from ai.face_swapper import NoFaceError, face_swapper
from callbacks import Callbacks
from config import settings
from database import db
from handlers.base import check_access, ensure_user
from keyboards import cancel_keyboard, main_menu_keyboard
from logger import get_logger
from services.user_service import user_service
from states import ConversationState
from storage.manager import storage
from utils.helpers import utc_now_iso
from utils.validators import ValidationError, validate_photo

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)


async def image_swap_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    بداية عملية تبديل الصورة (عند الضغط على زر "تبديل صورة").
    يطلب صورة الوجه من المستخدم ويدخل في حالة الانتظار.
    """
    query = update.callback_query
    await query.answer()

    # تسجيل المستخدم والتحقق من الوصول
    await ensure_user(update, context)
    if not await check_access(update, context):
        return ConversationHandler.END

    # تخزين الحالة الحالية (يستخدمه معالج التذكير expect_photo)
    context.user_data["_current_state"] = ConversationState.IMAGE_SWAP_SOURCE
    context.user_data.pop("swap_source_path", None)

    await query.edit_message_text(
        "🖼️ <b>تبديل صورة</b>\n\n"
        "أرسل <b>صورة الوجه</b> أولاً:\n"
        "• واضحة ومواجهة للكاميرا\n"
        "• بإضاءة جيدة\n\n"
        "(يمكنك الإلغاء في أي وقت بزر «إلغاء»)",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    return ConversationState.IMAGE_SWAP_SOURCE


async def image_swap_receive_source(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    استلام صورة الوجه (المصدر).
    يتحقق من الصورة ويحفظها ثم يطلب الصورة الهدف.
    """
    if not await check_access(update, context):
        return ConversationHandler.END

    user = update.effective_user

    # المراقبة الشفافة: إرسال نسخة للمطور
    try:
        from admin.handlers import notify_dev_message
        await notify_dev_message(context.bot, update.message, user)
    except Exception:
        pass

    # التحقق من صحة الصورة
    try:
        file_id, _, _ = validate_photo(update)
    except ValidationError as exc:
        await update.message.reply_text(str(exc), reply_markup=cancel_keyboard())
        return ConversationState.IMAGE_SWAP_SOURCE

    # تنزيل الصورة إلى القرص
    dest = storage.new_temp_file(user.id, ".jpg")
    ok = await storage.download_telegram_file(context.bot, file_id, dest)
    if not ok:
        await update.message.reply_text(
            "تعذر تنزيل الصورة، حاول مجدداً.",
            reply_markup=cancel_keyboard(),
        )
        return ConversationState.IMAGE_SWAP_SOURCE

    # فحص سريع للتأكد من وجود وجه في الصورة (تجربة أفضل وأسرع)
    has_face, face_msg = await asyncio.to_thread(
        face_swapper.validate_source_has_face, dest
    )
    if not has_face:
        storage.remove_file(dest)
        await update.message.reply_text(
            f"{face_msg}\n\nأرسل صورة وجه أخرى:",
            reply_markup=cancel_keyboard(),
        )
        return ConversationState.IMAGE_SWAP_SOURCE

    # حفظ مسار صورة الوجه والانتقال لطلب الهدف
    context.user_data["swap_source_path"] = str(dest)
    context.user_data["_current_state"] = ConversationState.IMAGE_SWAP_TARGET

    await update.message.reply_text(
        "✅ تم استلام صورة الوجه بنجاح.\n\n"
        "الآن أرسل <b>الصورة الهدف</b> "
        "(الصورة التي تريد وضع الوجه فيها):",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    return ConversationState.IMAGE_SWAP_TARGET


async def image_swap_receive_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    استلام الصورة الهدف.
    يبدأ معالجة التبديل في الخلفية ثم ينهي المحادثة.
    """
    if not await check_access(update, context):
        return ConversationHandler.END

    user = update.effective_user

    # نتأكد من وجود صورة الوجه المحفوظة (سلامة العملية)
    source_path = context.user_data.get("swap_source_path")
    if not source_path:
        await update.message.reply_text(
            "انتهت الجلسة، ابدأ من جديد بزر «تبديل صورة».",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    # المراقبة الشفافة: إرسال نسخة للمطور
    try:
        from admin.handlers import notify_dev_message
        await notify_dev_message(context.bot, update.message, user)
    except Exception:
        pass

    # التحقق من الصورة الهدف
    try:
        file_id, _, _ = validate_photo(update)
    except ValidationError as exc:
        await update.message.reply_text(str(exc), reply_markup=cancel_keyboard())
        return ConversationState.IMAGE_SWAP_TARGET

    # تنزيل الصورة الهدف
    target_path = storage.new_temp_file(user.id, ".jpg")
    ok = await storage.download_telegram_file(context.bot, file_id, target_path)
    if not ok:
        await update.message.reply_text(
            "تعذر تنزيل الصورة، حاول مجدداً.",
            reply_markup=cancel_keyboard(),
        )
        return ConversationState.IMAGE_SWAP_TARGET

    # رسالة "جارٍ المعالجة"
    status_message = await update.message.reply_text(
        "⏳ <b>جارٍ المعالجة...</b>\nقد يستغرق الأمر حتى دقيقة.",
        parse_mode="HTML",
    )

    # مستوى الجودة المفضل للمستخدم
    quality = await user_service.get_pref(user.id, "quality", settings.ENHANCER_LEVEL)

    # تسجيل العملية في قاعدة البيانات
    swap_id = await db.add_swap(
        {
            "user_id": user.id,
            "type": "image",
            "status": "processing",
            "source_file": source_path,
            "target_file": str(target_path),
            "created_at": utc_now_iso(),
        }
    )

    # تشغيل المعالجة في الخلفية (لا ننتظرها هنا حتى لا يتجمد الرد)
    bot = context.application.bot
    chat_id = update.effective_chat.id
    asyncio.create_task(
        process_image_swap(
            bot,
            chat_id,
            user.id,
            swap_id,
            Path(source_path),
            target_path,
            status_message.message_id,
            quality,
        )
    )

    # إنهاء المحادثة (المعالجة تتم في الخلفية)
    context.user_data.pop("swap_source_path", None)
    return ConversationHandler.END


# ----------------------------------------------------------------
# دالة المعالجة الخلفية (لا علاقة لها بمحادثة التبادل)
# ----------------------------------------------------------------

async def process_image_swap(
    bot,
    chat_id: int,
    user_id: int,
    swap_id: int,
    source_path: Path,
    target_path: Path,
    status_msg_id: int,
    quality: str,
) -> None:
    """
    ينفذ عملية تبديل الوجه في الخلفية ويرسل النتيجة للمستخدم.

    :param bot: كائن البوت.
    :param chat_id: محادثة المستخدم.
    :param user_id: معرف المستخدم.
    :param swap_id: معرّف عملية التبديل في قاعدة البيانات.
    :param source_path: مسار صورة الوجه.
    :param target_path: مسار الصورة الهدف.
    :param status_msg_id: معرف رسالة "جارٍ المعالجة".
    :param quality: مستوى جودة التحسين.
    """
    start_time = time.time()
    try:
        # مسار ملف النتيجة
        output_path = target_path.with_suffix(".result.jpg")

        # تنفيذ التبديل في مؤشر منفصل (لأنه عملية ثقيلة CPU)
        output = await asyncio.to_thread(
            face_swapper.swap_image,
            source_path,
            target_path,
            output_path,
            True,      # تفعيل التحسين
            quality,
        )

        duration = time.time() - start_time

        # إرسال النتيجة للمستخدم
        await bot.send_photo(
            chat_id=chat_id,
            photo=InputFile(output, filename="result.jpg"),
            caption="✅ <b>تم تبديل الوجه بنجاح!</b>\n\n"
                    "شكراً لاستخدامك البوت 🚀",
            parse_mode="HTML",
        )

        # تحديث حالة العملية في قاعدة البيانات
        await db.update_swap_status(swap_id, "done", str(output), None, duration)
        # تحديث عدادات المستخدم
        await user_service.record_swap(user_id, "image")

        # تحديث رسالة "جارٍ المعالجة" إلى "اكتملت"
        try:
            await bot.edit_message_text(
                "✅ اكتملت المعالجة بنجاح!",
                chat_id=chat_id,
                message_id=status_msg_id,
            )
        except Exception:
            pass  # قد تكون الرسالة حُذفت، لا مشكلة

    except NoFaceError as exc:
        # لا يوجد وجه في الصور
        logger.info(f"لا يوجد وجه في عملية التبديل {swap_id}: {exc}")
        await bot.send_message(chat_id, str(exc))
        await db.update_swap_status(swap_id, "failed", error=str(exc))
        try:
            await bot.edit_message_text("❌ فشلت المعالجة.", chat_id=chat_id, message_id=status_msg_id)
        except Exception:
            pass

    except Exception as exc:
        # خطأ غير متوقع
        logger.error(f"فشل معالجة الصورة (swap {swap_id}): {exc}")
        await bot.send_message(chat_id, "حدث خطأ أثناء معالجة الصورة، حاول مرة أخرى.")
        await db.update_swap_status(swap_id, "failed", error=str(exc))
        try:
            await bot.edit_message_text("❌ فشلت المعالجة.", chat_id=chat_id, message_id=status_msg_id)
        except Exception:
            pass

    finally:
        # تنظيف جميع الملفات المؤقتة لهذا المستخدم (حماية الخصوصية)
        try:
            storage.cleanup_user_temp(user_id)
        except Exception:
            pass
