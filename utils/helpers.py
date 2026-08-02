# ================================================================
# ملف utils/helpers.py
# --------------------
# هذا الملف يحتوي على دوال مساعدة عامة تستخدم في أكثر من مكان.
# ================================================================

import re
from datetime import datetime
from typing import Optional

from telegram import User

from config import settings
from logger import get_logger

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)


def utc_now_iso() -> str:
    """
    يُعيد الوقت الحالي بصيغة ISO موحدة.
    نستخدم UTC دائماً لتوحيد التوقيت بين المستخدمين والخادم.
    """
    return datetime.utcnow().isoformat()


def is_developer(user_id: int) -> bool:
    """
    يتحقق مما إذا كان معرف المستخدم هو معرف المطور.
    :param user_id: معرف المستخدم الرقمي.
    """
    return user_id == settings.DEVELOPER_ID


def format_size(size_bytes: int) -> str:
    """
    يحول الحجم بالبايت إلى صيغة مقروءة.
    مثال: 2048 -> "2.0 KB"
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    kb = size_bytes / 1024
    if kb < 1024:
        return f"{kb:.1f} KB"
    mb = kb / 1024
    if mb < 1024:
        return f"{mb:.1f} MB"
    return f"{mb / 1024:.1f} GB"


def safe_filename(name: str) -> str:
    """
    ينظف اسم ملف من الرموز الخطيرة لحماية نظام الملفات.
    :param name: اسم الملف الأصلي.
    """
    # نحذف كل ما ليس حرفاً أو رقماً أو نقطة أو شرطة
    cleaned = re.sub(r"[^a-zA-Z0-9_.\-]", "_", name)
    # نمنع أسماء قصيرة جداً أو فارغة
    return cleaned or "file"


def user_display_name(user: Optional[User]) -> str:
    """
    يُرجع الاسم الكامل للمستخدم (الاسم الأول + الأخير).
    :param user: كائن المستخدم من تيليجرام.
    """
    if not user:
        return "مجهول"
    parts = [user.first_name or "", user.last_name or ""]
    name = " ".join(parts).strip()
    return name or "مجهول"


def user_username(user: Optional[User]) -> str:
    """يُرجع اسم المستخدم (@username) أو "بدون اسم مستخدم"."""
    return user.username if user and user.username else "بدون اسم مستخدم"


def build_user_info_text(user: Optional[User], message_type: str, time_str: str) -> str:
    """
    يبني نص معلومات المستخدم الذي يُرسل للمطور مع كل رسالة/ملف.
    يحتوي على: الاسم، اليوزرنيم، المعرّف، الوقت، نوع الملف.
    """
    user_id = user.id if user else 0
    return (
        f"👤 الاسم: {user_display_name(user)}\n"
        f"🆔 User ID: <code>{user_id}</code>\n"
        f"📛 Username: @{user_username(user)}\n"
        f"🕒 الوقت: {time_str}\n"
        f"📦 نوع الملف: {message_type}"
    )


def split_long_text(text: str, limit: int = 4000) -> list:
    """
    يقسم نصاً طويلاً إلى أجزاء صالحة لإرسال تيليجرام.
    تيليجرام يسمح بـ 4096 حرفاً لكل رسالة.
    :param text: النص الكامل.
    :param limit: الحد الأقصى لطول الجزء.
    """
    if len(text) <= limit:
        return [text]
    parts = []
    while len(text) > limit:
        # نقسم عند أقرب مسافة قبل الحد الأقصى
        cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    parts.append(text)
    return parts


def html_escape(text: str) -> str:
    """
    ينظف النص من الرموز الخاصة في HTML تيليجرام
    لمنع كسر التنسيق أو أخطاء العرض.
    """
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def get_swap_stats_text(user_row: dict) -> str:
    """
    يبني نص إحصائيات مستخدم شخصية من صف قاعدة البيانات.
    :param user_row: قاموس صف المستخدم.
    """
    return (
        "📊 <b>إحصائياتك الشخصية</b>\n"
        "──────────────\n"
        f"🖼️ عدد الصور المبدلة: <b>{user_row.get('total_images', 0)}</b>\n"
        f"🎬 عدد الفيديوهات المبدلة: <b>{user_row.get('total_videos', 0)}</b>\n"
        f"🔁 إجمالي الطلبات: <b>{user_row.get('total_requests', 0)}</b>\n"
        f"📅 تاريخ الانضمام: <code>{user_row.get('created_at', 'غير معروف')}</code>"
    )
