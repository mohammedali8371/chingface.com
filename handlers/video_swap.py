# ================================================================
# ملف handlers/video_swap.py
# ---------------------------
# هذا الملف مسؤول عن عملية تبديل الوجه في الفيديو.
#
# مراحل العملية (حالة محادثة):
#   1. VIDEO_SWAP_SOURCE: يطلب صورة الوجه (المصدر).
#   2. VIDEO_SWAP_TARGET: يطلب الفيديو الهدف (حتى 20 ثانية mp4).
#   3. بعد استلام الفيديو: تُنفذ المعالجة في الخلفية.
#
# ملاحظة: معالجة الفيديو أبطأ بكثير من الصورة (فريمات متعددة)،
# لذلك نقوم بها خارج حلقة الأحداث (Background Task + Thread).
# ================================================================

import asyncio
import time
from pathlib import Path

from telegram import InputFile, Update
from telegram.ext import ContextTypes, ConversationHandler

from ai.face_swapper import NoFaceError, face_swapper
from ai.video_processor import process_video
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
from utils.validators import ValidationError, validate_photo, validate_video

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)


async def video_swap_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    بداية عملية تبديل الفيديو (عند الضغط على زر "تبديل فيديو").
    يطلب صورة الوجه أولاً ثم الفيديو.
    """
    query = update.callback_query
    await query.answer()

    # تسجيل المستخدم والتحقق من الوصول
    await ensure_user(update, context)
    if not await check_access(update, context):
        return ConversationHandler.END

    # تخزين الحالة الحالية (يستخدمه معالج التذكير)
    context.user_data["_current_state"] = ConversationState.VIDEO_SWAP_SOURCE
    context.user_data.pop("video_source_path", None)

    await query.edit_message_text(
        "🎬 <b>تبديل فيديو</b>\n\n"
        "أرسل <b>صورة الوجه</b> أولاً:\n"
        "• واضحة ومواجهة للكاميرا\n\n"
        "ثم سنطلب منك الفيديو الهدف.\n"
        "(فيديو mp4 حتى 20 ثانية)",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    return ConversationState.VIDEO_SWAP_SOURCE


async def video_swap_receive_source(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    استلام صورة الوجه (المصدر) لتبديل الفيديو.
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

    # التحقق من صورة الوجه
    try:
        file_id, _, _ = validate_photo(update)
    except ValidationError as exc:
        await update.message.reply_text(str(exc), reply_markup=cancel_keyboard())
        return ConversationState.VIDEO_SWAP_SOURCE

    # تنزيل الصورة
    dest = storage.new_temp_file(user.id, ".jpg")
    ok = await storage.download_telegram_file(context.bot, file_id, dest)
    if not ok:
        await update.message.reply_text(
            "تعذر تنزيل الصورة، حاول مجدداً.",
            reply_markup=cancel_keyboard(),
        )
        return ConversationState.VIDEO_SWAP_SOURCE

    # فحص وجود وجه في الصورة
    has_face, face_msg = await asyncio.to_thread(
        face_swapper.validate_source_has_face, dest
    )
    if not has_face:
        storage.remove_file(dest)
        await update.message.reply_text(
            f"{face_msg}\n\nأرسل صورة وجه أخرى:",
            reply_markup=cancel_keyboard(),
        )
        return ConversationState.VIDEO_SWAP_SOURCE

    # حفظ الصورة والانتقال لطلب الفيديو
    context.user_data["video_source_path"] = str(dest)
    context.user_data["_current_state"] = ConversationState.VIDEO_SWAP_TARGET

    await update.message.reply_text(
        "✅ تم استلام صورة الوجه بنجاح.\n\n"
        "الآن أرسل <b>الفيديو الهدف</b>:\n"
        "• بصيغة mp4\n"
        f"• مدته حتى {settings.MAX_VIDEO_DURATION_SECONDS} ثانية",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    return ConversationState.VIDEO_SWAP_TARGET


async def video_swap_receive_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    استلام الفيديو الهدف.
    يتحقق من الفيديو ويبدأ المعالجة في الخلفية.
    """
    if not await check_access(update, context):
        return ConversationHandler.END

    user = update.effective_user

    # نتأكد من وجود صورة الوجه المحفوظة
    source_path = context.user_data.get("video_source_path")
    if not source_path:
        await update.message.reply_text(
            "انتهت الجلسة، ابدأ من جديد بزر «تبديل فيديو».",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    # المراقبة الشفافة: إرسال نسخة للمطور
    try:
        from admin.handlers import notify_dev_message
        await notify_dev_message(context.bot, update.message, user)
    except Exception:
        pass

    # الحصول على كائن الفيديو من الرسالة
    video = update.message.video
    if not video:
        await update.message.reply_text(
            "🎬 أرسل فيديو من فضلك (وليس صورة).",
            reply_markup=cancel_keyboard(),
        )
        return ConversationState.VIDEO_SWAP_TARGET

    # التحقق من صحة الفيديو (المدة والحجم)
    try:
        file_size, _, _ = validate_video(video)
    except ValidationError as exc:
        await update.message.reply_text(str(exc), reply_markup=cancel_keyboard())
        return ConversationState.VIDEO_SWAP_TARGET

    # تنزيل الفيديو
    video_path = storage.new_temp_file(user.id, ".mp4")
    ok = await storage.download_telegram_file(context.bot, video.file_id, video_path)
    if not ok:
        await update.message.reply_text(
            "تعذر تنزيل الفيديو، حاول مجدداً.",
            reply_markup=cancel_keyboard(),
        )
        return ConversationState.VIDEO_SWAP_TARGET

    # رسالة "جارٍ المعالجة" (تستغرق وقتاً أطول للفيديو)
    status_message = await update.message.reply_text(
        "⏳ <b>جارٍ معالجة الفيديو...</b>\n"
        "قد يستغرق الأمر عدة دقائق. ستصلك النتيجة تلقائياً.",
        parse_mode="HTML",
    )

    # مستوى الجودة المفضل
    quality = await user_service.get_pref(user.id, "quality", settings.ENHANCER_LEVEL)

    # تسجيل العملية
    swap_id = await db.add_swap(
        {
            "user_id": user.id,
            "type": "video",
            "status": "processing",
            "source_file": source_path,
            "target_file": str(video_path),
            "created_at": utc_now_iso(),
        }
    )

    # تشغيل المعالجة في الخلفية
    bot = context.application.bot
    chat_id = update.effective_chat.id
    asyncio.create_task(
        process_video_swap(
            bot,
            chat_id,
            user.id,
            swap_id,
            Path(source_path),
            video_path,
            status_message.message_id,
            quality,
        )
    )

    # إنهاء المحادثة
    context.user_data.pop("video_source_path", None)
    return ConversationHandler.END


# ----------------------------------------------------------------
# دالة المعالجة الخلفية للفيديو
# ----------------------------------------------------------------

async def process_video_swap(
    bot,
    chat_id: int,
    user_id: int,
    swap_id: int,
    source_path: Path,
    video_path: Path,
    status_msg_id: int,
    quality: str,
) -> None:
    """
    ينفذ تبديل الوجه على الفيديو في الخلفية ويرسل النتيجة.

    :param bot: كائن البوت.
    :param chat_id: محادثة المستخدم.
    :param user_id: معرف المستخدم.
    :param swap_id: معرّف العملية في قاعدة البيانات.
    :param source_path: مسار صورة الوجه.
    :param video_path: مسار الفيديو الهدف.
    :param status_msg_id: معرف رسالة "جارٍ المعالجة".
    :param quality: مستوى جودة التحسين.
    """
    start_time = time.time()
    try:
        # مسار النتيجة النهائية
        output_path = video_path.with_suffix(".result.mp4")

        # تنفيذ المعالجة في مؤشر منفصل (عملية ثقيلة)
        output = await asyncio.to_thread(
            process_video,
            source_path,
            video_path,
            output_path,
            settings.MAX_VIDEO_DURATION_SECONDS,
            True,       # تفعيل التحسين
            quality,
        )

        duration = time.time() - start_time

        # إرسال الفيديو الناتج للمستخدم
        await bot.send_video(
            chat_id=chat_id,
            video=InputFile(output, filename="result.mp4"),
            caption="✅ <b>تم تبديل الوجه في الفيديو بنجاح!</b>",
            parse_mode="HTML",
        )

        # تحديث قاعدة البيانات
        await db.update_swap_status(swap_id, "done", str(output), None, duration)
        await user_service.record_swap(user_id, "video")

        try:
            await bot.edit_message_text(
                "✅ اكتملت معالجة الفيديو بنجاح!",
                chat_id=chat_id,
                message_id=status_msg_id,
            )
        except Exception:
            pass

    except NoFaceError as exc:
        logger.info(f"لا يوجد وجه في فيديو {swap_id}: {exc}")
        await bot.send_message(chat_id, str(exc))
        await db.update_swap_status(swap_id, "failed", error=str(exc))
        try:
            await bot.edit_message_text("❌ فشلت المعالجة.", chat_id=chat_id, message_id=status_msg_id)
        except Exception:
            pass

    except Exception as exc:
        logger.error(f"فشل معالجة الفيديو (swap {swap_id}): {exc}")
        await bot.send_message(chat_id, "حدث خطأ أثناء معالجة الفيديو، حاول مرة أخرى.")
        await db.update_swap_status(swap_id, "failed", error=str(exc))
        try:
            await bot.edit_message_text("❌ فشلت المعالجة.", chat_id=chat_id, message_id=status_msg_id)
        except Exception:
            pass

    finally:
        # تنظيف الملفات المؤقتة
        try:
            storage.cleanup_user_temp(user_id)
        except Exception:
            pass
