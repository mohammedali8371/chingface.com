# ================================================================
# ملف callbacks.py
# ----------------
# هذا الملف يحتوي على تعريفات بيانات الأزرار (Callback Data)
# الخاصة بالأزرار الشفافة (Inline Buttons).
#
# كيف تعمل الأزرار الشفافة؟
# --------------------------
# عند الضغط على زر يرسل تيليجرام نصاً قصيراً (Callback Data)
# إلى البوت مع معلومات الضغط. نستخدم هذا النص لمعرفة أي زر
# تم ضغطه واتخاذ الإجراء المناسب.
#
# لماذا هذا الملف منفصل؟
# -----------------------
# حتى لا نكرر النصوص في أكثر من مكان، ولكي يكون تغيير اسم
# أي زر سهلاً من مكان واحد فقط. كما نستخدم أنماطاً (Patterns)
# مع تعبيرات منتظمة لالتقاط الأزرار الديناميكية (مثل زر الرد
# على رسالة يحمل معرف المستخدم داخله).
# ================================================================


class Callbacks:
    """
    كلاس ثابت يحتوي على كل بيانات الأزرار في المشروع.
    كل متغير يمثل زراً معيناً في الواجهة.
    """

    # ============================================================
    # أزرار القائمة الرئيسية
    # ============================================================

    # زر فتح القائمة الرئيسية
    MAIN_MENU: str = "cb:main_menu"

    # زر بدء تبديل صورة
    SWAP_IMAGE: str = "cb:swap_image"

    # زر بدء تبديل فيديو
    SWAP_VIDEO: str = "cb:swap_video"

    # زر الإعدادات
    SETTINGS: str = "cb:settings"

    # زر المساعدة
    HELP: str = "cb:help"

    # زر معلومات المطور
    DEVELOPER: str = "cb:developer"

    # زر سياسة الخصوصية
    PRIVACY: str = "cb:privacy"

    # زر "حول البوت"
    ABOUT: str = "cb:about"

    # زر الرجوع للخلف
    BACK: str = "cb:back"

    # زر إلغاء العملية الحالية
    CANCEL: str = "cb:cancel"

    # ============================================================
    # أزرار الموافقة على المراقبة الشفافة (بدء الاستخدام)
    # ============================================================

    # زر الموافقة على المراقبة الشفافة والمتابعة
    AGREE_MONITORING: str = "cb:agree_monitoring"

    # زر رفض المراقبة الشفافة
    DECLINE_MONITORING: str = "cb:decline_monitoring"

    # ============================================================
    # أزرار الإعدادات
    # ============================================================

    # تغيير مستوى تحسين الجودة: عالي / متوسط / بدون
    SETTINGS_QUALITY_HIGH: str = "cb:settings:quality_high"
    SETTINGS_QUALITY_MEDIUM: str = "cb:settings:quality_medium"
    SETTINGS_QUALITY_OFF: str = "cb:settings:quality_off"

    # عرض إحصائيات المستخدم الشخصية
    SETTINGS_MY_STATS: str = "cb:settings:my_stats"

    # حذف بيانات المستخدم (الخصوصية)
    SETTINGS_DELETE_MY_DATA: str = "cb:settings:delete_my_data"

    # ============================================================
    # أزرار لوحة المطور
    # ============================================================

    # فتح لوحة المطور
    DEV_PANEL: str = "cb:dev:panel"

    # عرض الإحصائيات الكاملة (المستخدمون، الصور، الفيديوهات، ...)
    DEV_STATS: str = "cb:dev:stats"

    # عرض عدد المستخدمين
    DEV_USERS_COUNT: str = "cb:dev:users_count"

    # عرض آخر المستخدمين
    DEV_RECENT_USERS: str = "cb:dev:recent_users"

    # عرض آخر الرسائل
    DEV_RECENT_MESSAGES: str = "cb:dev:recent_messages"

    # عرض سجل الأخطاء
    DEV_ERRORS: str = "cb:dev:errors"

    # تشغيل البوت
    DEV_BOT_ON: str = "cb:dev:bot_on"

    # إيقاف البوت
    DEV_BOT_OFF: str = "cb:dev:bot_off"

    # إرسال رسالة جماعية
    DEV_BROADCAST: str = "cb:dev:broadcast"

    # إرسال رسالة لمستخدم محدد
    DEV_DIRECT_MESSAGE: str = "cb:dev:direct_message"

    # حظر مستخدم
    DEV_BAN_USER: str = "cb:dev:ban_user"

    # فك حظر مستخدم
    DEV_UNBAN_USER: str = "cb:dev:unban_user"

    # حذف مستخدم نهائياً
    DEV_DELETE_USER: str = "cb:dev:delete_user"

    # إعادة تشغيل الخدمات الداخلية
    DEV_RESTART_SERVICES: str = "cb:dev:restart_services"

    # مسح الكاش والملفات المؤقتة
    DEV_CLEAR_CACHE: str = "cb:dev:clear_cache"

    # تنزيل قاعدة البيانات
    DEV_DOWNLOAD_DB: str = "cb:dev:download_db"

    # رفع قاعدة البيانات
    DEV_UPLOAD_DB: str = "cb:dev:upload_db"

    # إنشاء نسخة احتياطية
    DEV_BACKUP: str = "cb:dev:backup"

    # استعادة نسخة احتياطية
    DEV_RESTORE_BACKUP: str = "cb:dev:restore_backup"

    # ============================================================
    # أزرار ديناميكية (تحمل معرّف المستخدم داخلها)
    # ============================================================
    # هذه الأزرار تُبنى برمجياً وتحتوي على معرف المستخدم في النص.

    # زر "رد" على رسالة مستخدم معين: cb:reply:<user_id>
    REPLY_PREFIX: str = "cb:reply:"

    # زر "حظر" من رسالة مستخدم: cb:banmsg:<user_id>
    BAN_MSG_PREFIX: str = "cb:banmsg:"

    # زر "حذف مستخدم" من رسالة: cb:delmsg:<user_id>
    DELETE_MSG_PREFIX: str = "cb:delmsg:"


# ----------------------------------------------------------------
# دوال مساعدة لبناء وتحليل الأزرار الديناميكية
# ----------------------------------------------------------------

def reply_callback(user_id: int) -> str:
    """يبني نص زر "رد" على رسالة مستخدم معين."""
    return f"{Callbacks.REPLY_PREFIX}{user_id}"


def ban_msg_callback(user_id: int) -> str:
    """يبني نص زر "حظر" من رسالة مستخدم معين."""
    return f"{Callbacks.BAN_MSG_PREFIX}{user_id}"


def delete_msg_callback(user_id: int) -> str:
    """يبني نص زر "حذف مستخدم" من رسالة مستخدم معين."""
    return f"{Callbacks.DELETE_MSG_PREFIX}{user_id}"


def parse_user_id_from_callback(callback_data: str) -> int:
    """
    يستخرج معرف المستخدم من نص زر ديناميكي.
    مثال: "cb:reply:123456" -> 123456

    :param callback_data: نص الزر القادم من تيليجرام.
    :return: معرف المستخدم الرقمي، أو 0 إذا فشل التحليل.
    """
    try:
        # نقسم النص على ":" ونأخذ آخر جزء (المعرف)
        return int(callback_data.split(":")[-1])
    except (ValueError, IndexError):
        # فشل التحويل: نعيد 0
        return 0
