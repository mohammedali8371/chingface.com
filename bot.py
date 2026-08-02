# ================================================================
# ملف bot.py
# ----------
# هذا الملف هو نقطة بناء تطبيق البوت (Application).
#
# مسؤول عن:
#   1. بناء تطبيق python-telegram-bot v22.
#   2. تسجيل جميع المعالجات (Handlers) بالترتيب الصحيح.
#   3. ضبط الـ Webhook على تيليجرام.
#
# ترتيب تسجيل المعالجات مهم جداً:
#   1. /start أولاً.
#   2. محادثات التبديل (صورة/فيديو) ثم محادثة لوحة المطور.
#   3. الأزرار العامة (القوائم والإعدادات ولوحة المطور الفورية).
#   4. أخيراً المعالج الشامل الذي يلتقط أي رسالة أخرى
#      (لتسجيلها والمراقبة الشفافة).
# ================================================================

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from admin.handlers import (
    admin_ban_msg,
    admin_delete_msg,
    build_admin_conversation,
    on_message_logging,
)
from admin.panel import (
    dev_backup,
    dev_bot_off,
    dev_bot_on,
    dev_clear_cache,
    dev_download_db,
    dev_errors,
    dev_recent_messages,
    dev_recent_users,
    dev_restart_services,
    dev_stats,
    dev_users_count,
    show_dev_panel,
)
from callbacks import Callbacks
from config import settings
from handlers.base import cancel_flow, expect_photo, expect_video, on_error
from handlers.help_menu import (
    about_callback,
    developer_callback,
    help_callback,
    privacy_callback,
)
from handlers.image_swap import (
    image_swap_receive_source,
    image_swap_receive_target,
    image_swap_start,
)
from handlers.settings import (
    delete_my_data,
    my_stats,
    quality_high,
    quality_medium,
    quality_off,
    settings_menu,
)
from handlers.start import (
    agree_monitoring,
    decline_monitoring,
    main_menu_callback,
    start_command,
)
from handlers.video_swap import (
    video_swap_receive_source,
    video_swap_receive_target,
    video_swap_start,
)
from logger import get_logger
from states import ConversationState

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)

# المتغير العام لتطبيق البوت (يُبنى مرة واحدة فقط)
application: Application = None


# ----------------------------------------------------------------
# بناء التطبيق
# ----------------------------------------------------------------

def build_application() -> Application:
    """
    يبني تطبيق البوت مع جميع المعالجات.
    يُستدعى مرة واحدة عند تشغيل التطبيق (في main.py).

    :return: كائن Application جاهز للتشغيل.
    """
    global application
    if application is not None:
        return application

    logger.info("جارٍ بناء تطبيق البوت...")

    # بناء التطبيق مع التوكن وضبط مهلات الشبكة
    # (المدد الأطول ضرورية لتنزيل ملفات كبيرة)
    builder = (
        Application.builder()
        .token(settings.BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
    )
    app = builder.build()

    # تسجيل جميع المعالجات
    _register_handlers(app)

    # معالج الأخطاء العام
    app.add_error_handler(on_error)

    application = app
    logger.info("تم بناء تطبيق البوت ✓")
    return app


def get_application() -> Application:
    """
    يُرجع تطبيق البوت الحالي (يبنيه إن لم يكن مبنيّاً).
    يُستخدم من نقطة الـ Webhook.
    """
    if application is None:
        return build_application()
    return application


# ----------------------------------------------------------------
# تسجيل المعالجات
# ----------------------------------------------------------------

def _register_handlers(app: Application) -> None:
    """
    يسجل جميع المعالجات بالترتيب الصحيح.
    :param app: تطبيق البوت.
    """
    # ============================================================
    # 1) أمر /start (البداية)
    # ============================================================
    app.add_handler(CommandHandler("start", start_command))

    # ============================================================
    # 2) محادثة تبديل الصورة
    # ============================================================
    cancel_image = CallbackQueryHandler(cancel_flow, pattern=rf"^{Callbacks.CANCEL}$")
    image_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(image_swap_start, pattern=rf"^{Callbacks.SWAP_IMAGE}$"),
        ],
        states={
            ConversationState.IMAGE_SWAP_SOURCE: [
                MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, image_swap_receive_source),
                MessageHandler(filters.ALL & ~filters.PHOTO & filters.ChatType.PRIVATE, expect_photo),
                cancel_image,
            ],
            ConversationState.IMAGE_SWAP_TARGET: [
                MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, image_swap_receive_target),
                MessageHandler(filters.ALL & ~filters.PHOTO & filters.ChatType.PRIVATE, expect_photo),
                cancel_image,
            ],
        },
        fallbacks=[cancel_image],
        name="image_swap_conv",
    )
    app.add_handler(image_conv)

    # ============================================================
    # 3) محادثة تبديل الفيديو
    # ============================================================
    cancel_video = CallbackQueryHandler(cancel_flow, pattern=rf"^{Callbacks.CANCEL}$")
    video_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(video_swap_start, pattern=rf"^{Callbacks.SWAP_VIDEO}$"),
        ],
        states={
            ConversationState.VIDEO_SWAP_SOURCE: [
                MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, video_swap_receive_source),
                MessageHandler(filters.ALL & ~filters.PHOTO & filters.ChatType.PRIVATE, expect_photo),
                cancel_video,
            ],
            ConversationState.VIDEO_SWAP_TARGET: [
                MessageHandler(filters.VIDEO & filters.ChatType.PRIVATE, video_swap_receive_target),
                MessageHandler(filters.ALL & ~filters.VIDEO & filters.ChatType.PRIVATE, expect_video),
                cancel_video,
            ],
        },
        fallbacks=[cancel_video],
        name="video_swap_conv",
    )
    app.add_handler(video_conv)

    # ============================================================
    # 4) محادثة لوحة المطور
    # ============================================================
    app.add_handler(build_admin_conversation())

    # ============================================================
    # 5) الأزرار العامة (القوائم والإعدادات ولوحة المطور الفورية)
    # ============================================================

    # --- شاشة الموافقة على المراقبة الشفافة ---
    app.add_handler(CallbackQueryHandler(agree_monitoring, pattern=rf"^{Callbacks.AGREE_MONITORING}$"))
    app.add_handler(CallbackQueryHandler(decline_monitoring, pattern=rf"^{Callbacks.DECLINE_MONITORING}$"))

    # --- القائمة الرئيسية والمساعدة ---
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern=rf"^{Callbacks.MAIN_MENU}$"))
    app.add_handler(CallbackQueryHandler(help_callback, pattern=rf"^{Callbacks.HELP}$"))
    app.add_handler(CallbackQueryHandler(about_callback, pattern=rf"^{Callbacks.ABOUT}$"))
    app.add_handler(CallbackQueryHandler(privacy_callback, pattern=rf"^{Callbacks.PRIVACY}$"))
    app.add_handler(CallbackQueryHandler(developer_callback, pattern=rf"^{Callbacks.DEVELOPER}$"))

    # --- الإعدادات ---
    app.add_handler(CallbackQueryHandler(settings_menu, pattern=rf"^{Callbacks.SETTINGS}$"))
    app.add_handler(CallbackQueryHandler(quality_high, pattern=rf"^{Callbacks.SETTINGS_QUALITY_HIGH}$"))
    app.add_handler(CallbackQueryHandler(quality_medium, pattern=rf"^{Callbacks.SETTINGS_QUALITY_MEDIUM}$"))
    app.add_handler(CallbackQueryHandler(quality_off, pattern=rf"^{Callbacks.SETTINGS_QUALITY_OFF}$"))
    app.add_handler(CallbackQueryHandler(my_stats, pattern=rf"^{Callbacks.SETTINGS_MY_STATS}$"))
    app.add_handler(CallbackQueryHandler(delete_my_data, pattern=rf"^{Callbacks.SETTINGS_DELETE_MY_DATA}$"))

    # --- لوحة المطور: فتح اللوحة ---
    app.add_handler(CallbackQueryHandler(show_dev_panel, pattern=rf"^{Callbacks.DEV_PANEL}$"))

    # --- لوحة المطور: إجراءات فورية ---
    app.add_handler(CallbackQueryHandler(dev_stats, pattern=rf"^{Callbacks.DEV_STATS}$"))
    app.add_handler(CallbackQueryHandler(dev_users_count, pattern=rf"^{Callbacks.DEV_USERS_COUNT}$"))
    app.add_handler(CallbackQueryHandler(dev_recent_users, pattern=rf"^{Callbacks.DEV_RECENT_USERS}$"))
    app.add_handler(CallbackQueryHandler(dev_recent_messages, pattern=rf"^{Callbacks.DEV_RECENT_MESSAGES}$"))
    app.add_handler(CallbackQueryHandler(dev_errors, pattern=rf"^{Callbacks.DEV_ERRORS}$"))
    app.add_handler(CallbackQueryHandler(dev_bot_on, pattern=rf"^{Callbacks.DEV_BOT_ON}$"))
    app.add_handler(CallbackQueryHandler(dev_bot_off, pattern=rf"^{Callbacks.DEV_BOT_OFF}$"))
    app.add_handler(CallbackQueryHandler(dev_restart_services, pattern=rf"^{Callbacks.DEV_RESTART_SERVICES}$"))
    app.add_handler(CallbackQueryHandler(dev_clear_cache, pattern=rf"^{Callbacks.DEV_CLEAR_CACHE}$"))
    app.add_handler(CallbackQueryHandler(dev_download_db, pattern=rf"^{Callbacks.DEV_DOWNLOAD_DB}$"))
    app.add_handler(CallbackQueryHandler(dev_backup, pattern=rf"^{Callbacks.DEV_BACKUP}$"))

    # --- أزرار فورية على رسائل المستخدمين المحولة (حظر/حذف) ---
    app.add_handler(CallbackQueryHandler(
        admin_ban_msg,
        pattern=rf"^{Callbacks.BAN_MSG_PREFIX}\d+$",
    ))
    app.add_handler(CallbackQueryHandler(
        admin_delete_msg,
        pattern=rf"^{Callbacks.DELETE_MSG_PREFIX}\d+$",
    ))

    # ============================================================
    # 6) المعالج الشامل (أخيراً): يلتقط أي رسالة غير معالجة
    #    لتسجيلها في قاعدة البيانات والمراقبة الشفافة.
    # ============================================================
    app.add_handler(MessageHandler(filters.ALL, on_message_logging))


# ----------------------------------------------------------------
# ضبط الـ Webhook
# ----------------------------------------------------------------

async def setup_webhook(app: Application) -> bool:
    """
    يضبط الـ Webhook على تيليجرام.
    العنوان: <PUBLIC_URL>/webhook
    مع الرمز السري للتحقق من مصدر الطلبات.

    :param app: تطبيق البوت.
    :return: True عند النجاح.
    """
    url = settings.webhook_url()
    logger.info(f"ضبط الـ Webhook على: {url}")

    await app.bot.set_webhook(
        url=url,
        secret_token=settings.effective_secret(),
        allowed_updates=settings.allowed_updates_list(),
        drop_pending_updates=True,   # إسقاط أي تحديثات قديمة قبل البدء
    )

    # ضبط أوامر البوت الظاهرة للمستخدم
    try:
        await app.bot.set_my_commands(
            [BotCommand("start", "بدء الاستخدام 🚀")]
        )
    except Exception as exc:
        logger.warning(f"فشل ضبط أوامر البوت: {exc}")

    logger.info("تم ضبط الـ Webhook بنجاح ✓")
    return True


async def delete_webhook(app: Application) -> None:
    """
    يحذف الـ Webhook (يُستخدم عند إيقاف التشغيل).
    :param app: تطبيق البوت.
    """
    try:
        await app.bot.delete_webhook()
        logger.info("تم حذف الـ Webhook")
    except Exception as exc:
        logger.warning(f"فشل حذف الـ Webhook: {exc}")
