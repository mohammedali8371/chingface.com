# ================================================================
# ملف keyboards.py
# ----------------
# هذا الملف مسؤول عن بناء جميع أزرار البوت (Inline Keyboards).
#
# لماذا نبنيه في ملف منفصل؟
# --------------------------
#   1. الواجهة كلها أزرار (لا أوامر) كما طلبت.
#   2. كل الأزرار مبنية من مكان واحد ليسهل تعديلها.
#   3. نستورد ثوابت callbacks.py هنا لضمان تطابق بيانات الأزرار.
# ================================================================

from typing import List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from callbacks import Callbacks, ban_msg_callback, delete_msg_callback, reply_callback


def build_markup(rows: List[List[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    """
    دالة مساعدة عامة لبناء لوحة أزرار من صفوف.
    :param rows: قائمة صفوف، كل صف يحتوي أزراراً.
    """
    return InlineKeyboardMarkup(rows)


# ================================================================
# القائمة الرئيسية
# ================================================================

def main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    الأزرار الرئيسية للبوت.
    (كل شيء أزرار - لا أوامر)
    """
    rows = [
        [
            InlineKeyboardButton("🖼️ تبديل صورة", callback_data=Callbacks.SWAP_IMAGE),
            InlineKeyboardButton("🎬 تبديل فيديو", callback_data=Callbacks.SWAP_VIDEO),
        ],
        [
            InlineKeyboardButton("⚙️ الإعدادات", callback_data=Callbacks.SETTINGS),
            InlineKeyboardButton("❓ المساعدة", callback_data=Callbacks.HELP),
        ],
        [
            InlineKeyboardButton("👨‍💻 المطور", callback_data=Callbacks.DEVELOPER),
            InlineKeyboardButton("📜 سياسة الخصوصية", callback_data=Callbacks.PRIVACY),
        ],
        [
            InlineKeyboardButton("ℹ️ حول البوت", callback_data=Callbacks.ABOUT),
        ],
    ]
    return build_markup(rows)


# ================================================================
# شاشة الموافقة على المراقبة الشفافة
# ================================================================

def monitoring_keyboard() -> InlineKeyboardMarkup:
    """
    أزرار الموافقة/الرفض على المراقبة الشفافة.
    تظهر للمستخدم عند بدء الاستخدام (متطلب الشفافية).
    """
    rows = [
        [
            InlineKeyboardButton("✅ أوافق والمتابعة", callback_data=Callbacks.AGREE_MONITORING),
        ],
        [
            InlineKeyboardButton("📜 سياسة الخصوصية", callback_data=Callbacks.PRIVACY),
            InlineKeyboardButton("🚫 لا أوافق", callback_data=Callbacks.DECLINE_MONITORING),
        ],
    ]
    return build_markup(rows)


# ================================================================
# أزرار الإلغاء/الرجوع
# ================================================================

def cancel_keyboard() -> InlineKeyboardMarkup:
    """زر إلغاء العملية الحالية (يظهر أثناء عمليات التبديل)."""
    rows = [
        [
            InlineKeyboardButton("❌ إلغاء", callback_data=Callbacks.CANCEL),
        ],
    ]
    return build_markup(rows)


def back_keyboard() -> InlineKeyboardMarkup:
    """زر الرجوع للقائمة الرئيسية."""
    rows = [
        [
            InlineKeyboardButton("↩️ رجوع", callback_data=Callbacks.MAIN_MENU),
        ],
    ]
    return build_markup(rows)


def dev_back_keyboard() -> InlineKeyboardMarkup:
    """زر الرجوع إلى لوحة المطور."""
    rows = [
        [
            InlineKeyboardButton("👨‍💻 ↩️ لوحة المطور", callback_data=Callbacks.DEV_PANEL),
        ],
    ]
    return build_markup(rows)


# ================================================================
# قائمة الإعدادات
# ================================================================

def settings_keyboard() -> InlineKeyboardMarkup:
    """
    أزرار قائمة الإعدادات:
      - مستوى جودة التحسين (عالي / متوسط / بدون).
      - إحصائياتي الشخصية.
      - حذف بياناتي (الخصوصية).
    """
    rows = [
        [
            InlineKeyboardButton("🔝 جودة التحسين: عالي", callback_data=Callbacks.SETTINGS_QUALITY_HIGH),
        ],
        [
            InlineKeyboardButton("🔶 جودة التحسين: متوسط", callback_data=Callbacks.SETTINGS_QUALITY_MEDIUM),
            InlineKeyboardButton("⚪ بدون تحسين", callback_data=Callbacks.SETTINGS_QUALITY_OFF),
        ],
        [
            InlineKeyboardButton("📊 إحصائياتي", callback_data=Callbacks.SETTINGS_MY_STATS),
            InlineKeyboardButton("🗑️ حذف بياناتي", callback_data=Callbacks.SETTINGS_DELETE_MY_DATA),
        ],
        [
            InlineKeyboardButton("↩️ رجوع", callback_data=Callbacks.MAIN_MENU),
        ],
    ]
    return build_markup(rows)


# ================================================================
# أزرار لوحة المطور
# ================================================================

def dev_panel_keyboard() -> InlineKeyboardMarkup:
    """
    الأزرار الكاملة للوحة المطور.
    تحتوي جميع العمليات الإدارية المطلوبة.
    """
    rows = [
        [
            InlineKeyboardButton("👥 عدد المستخدمين", callback_data=Callbacks.DEV_USERS_COUNT),
            InlineKeyboardButton("🕒 آخر المستخدمين", callback_data=Callbacks.DEV_RECENT_USERS),
        ],
        [
            InlineKeyboardButton("💬 آخر الرسائل", callback_data=Callbacks.DEV_RECENT_MESSAGES),
            InlineKeyboardButton("⚠️ سجل الأخطاء", callback_data=Callbacks.DEV_ERRORS),
        ],
        [
            InlineKeyboardButton("📊 الإحصائيات الكاملة", callback_data=Callbacks.DEV_STATS),
        ],
        [
            InlineKeyboardButton("▶️ تشغيل البوت", callback_data=Callbacks.DEV_BOT_ON),
            InlineKeyboardButton("⏸️ إيقاف البوت", callback_data=Callbacks.DEV_BOT_OFF),
        ],
        [
            InlineKeyboardButton("📣 رسالة جماعية", callback_data=Callbacks.DEV_BROADCAST),
            InlineKeyboardButton("✉️ رسالة لمستخدم", callback_data=Callbacks.DEV_DIRECT_MESSAGE),
        ],
        [
            InlineKeyboardButton("🚫 حظر مستخدم", callback_data=Callbacks.DEV_BAN_USER),
            InlineKeyboardButton("✅ فك الحظر", callback_data=Callbacks.DEV_UNBAN_USER),
        ],
        [
            InlineKeyboardButton("🗑️ حذف مستخدم", callback_data=Callbacks.DEV_DELETE_USER),
            InlineKeyboardButton("🔄 إعادة تشغيل الخدمات", callback_data=Callbacks.DEV_RESTART_SERVICES),
        ],
        [
            InlineKeyboardButton("🧹 مسح الكاش", callback_data=Callbacks.DEV_CLEAR_CACHE),
            InlineKeyboardButton("⬇️ تنزيل قاعدة البيانات", callback_data=Callbacks.DEV_DOWNLOAD_DB),
        ],
        [
            InlineKeyboardButton("⬆️ رفع قاعدة البيانات", callback_data=Callbacks.DEV_UPLOAD_DB),
            InlineKeyboardButton("💾 نسخة احتياطية", callback_data=Callbacks.DEV_BACKUP),
        ],
        [
            InlineKeyboardButton("♻️ استعادة نسخة", callback_data=Callbacks.DEV_RESTORE_BACKUP),
        ],
        [
            InlineKeyboardButton("↩️ رجوع", callback_data=Callbacks.MAIN_MENU),
        ],
    ]
    return build_markup(rows)


# ================================================================
# أزرار الإجراءات على رسائل المستخدمين (تظهر للمطور)
# ================================================================

def user_action_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    أزرار تُرسل للمطور مع كل رسالة/ملف من مستخدم:
      - رد على المستخدم.
      - حظر المستخدم.
      - حذف المستخدم.

    :param user_id: معرف المستخدم صاحب الرسالة.
    """
    rows = [
        [
            InlineKeyboardButton("💬 رد", callback_data=reply_callback(user_id)),
            InlineKeyboardButton("🚫 حظر", callback_data=ban_msg_callback(user_id)),
        ],
        [
            InlineKeyboardButton("🗑️ حذف المستخدم", callback_data=delete_msg_callback(user_id)),
        ],
    ]
    return build_markup(rows)
