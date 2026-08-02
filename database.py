# ================================================================
# ملف database.py
# ----------------
# هذا الملف مسؤول عن الاتصال بقاعدة البيانات والتخزين والاسترجاع.
#
# قاعدة البيانات المستخدمة: SQLite (عبر مكتبة aiosqlite غير المتزامنة).
#
# لماذا aiosqlite؟
# -----------------
# البوت يعمل بشكل غير متزامن (Async) بالكامل، وaiosqlite تسمح
# بتنفيذ استعلامات SQLite دون حظر حلقة الأحداث (Event Loop)،
# وهذا مهم جداً عند دعم عدة مستخدمين في نفس الوقت.
#
# ملاحظة للتطوير المستقبلي:
# تم تصميم هذا الكلاس (Database) ليكون الواجهة الوحيدة مع قاعدة
# البيانات. عند الرغبة في التحويل إلى PostgreSQL لاحقاً، يكفي
# إعادة تنفيذ نفس الدوال بداخل هذا الكلاس فقط دون تغيير بقية
# المشروع (نفس أسماء الدوال ونفس التوقيعات).
# ================================================================

import json
import sqlite3
from typing import Any, Dict, List, Optional

import aiosqlite

from config import settings
from logger import get_logger

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)


class Database:
    """
    الكلاس الرئيسي للتعامل مع قاعدة البيانات.
    ------------------------------------------
    مسؤول عن:
        1. الاتصال بقاعدة بيانات SQLite.
        2. إنشاء الجداول (Schema) عند أول تشغيل.
        3. توفير دوال جاهزة للتخزين والاسترجاع لكل كيان
           (مستخدم، عملية تبديل، رسالة، خطأ، إعداد، نسخة احتياطية).
    """

    def __init__(self, db_path) -> None:
        """
        :param db_path: مسار ملف قاعدة البيانات (Path).
        """
        self.db_path = db_path
        # الاتصال غير المتزامن (يُفتح في connect)
        self._conn: Optional[aiosqlite.Connection] = None
        # قفل للكتابة لمنع تعارض الاستعلامات المتزامنة
        self._write_lock = None

    # ============================================================
    # إدارة الاتصال
    # ============================================================

    async def connect(self) -> None:
        """
        يفتح الاتصال بقاعدة البيانات.
        - ينشئ مجلد قاعدة البيانات إن لم يكن موجوداً.
        - يفعّل وضع WAL لتحسين الأداء عند التعدد.
        """
        # نتأكد من وجود مجلد القاعدة
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # فتح الاتصال غير المتزامن
        self._conn = await aiosqlite.connect(self.db_path)
        # السماح بالوصول إلى الأعمدة بالاسم (مثل القاموس)
        self._conn.row_factory = aiosqlite.Row
        # تفعيل WAL: يسمح بالقراءة والكتابة في نفس الوقت
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        # تفعيل قيود المفاتيح الأجنبية
        await self._conn.execute("PRAGMA foreign_keys=ON;")
        # تهيئة قفل الكتابة
        self._write_lock = __import__("asyncio").Lock()
        logger.info(f"تم الاتصال بقاعدة البيانات: {self.db_path}")

    async def close(self) -> None:
        """يغلق الاتصال بقاعدة البيانات بأمان."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            logger.info("تم إغلاق الاتصال بقاعدة البيانات")

    def is_connected(self) -> bool:
        """يُعيد True إذا كان الاتصال بقاعدة البيانات مفتوحاً حالياً."""
        return self._conn is not None

    async def reconnect(self) -> None:
        """
        يعيد الاتصال بقاعدة البيانات.
        يُستخدم بعد استعادة قاعدة بيانات جديدة أو رفع ملف قاعدة جديد.
        """
        await self.close()
        await self.connect()

    # ============================================================
    # أدوات داخلية مساعدة
    # ============================================================

    async def _execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        """
        ينفذ استعلاماً ويحفظ التغييرات.
        يُستخدم للاستعلامات التي تعدّل البيانات (INSERT/UPDATE/DELETE).

        :param sql: نص الاستعلام.
        :param params: القيم التي تُمرر بأمان (تمنع حقن SQL).
        """
        if self._conn is None:
            raise RuntimeError("قاعدة البيانات غير متصلة")
        # نستخدم القفل لمنع الكتابة المتزامنة
        async with self._write_lock:
            cursor = await self._conn.execute(sql, params)
            await self._conn.commit()
            return cursor

    async def _fetchall(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        ينفذ استعلام قراءة ويعيد النتائج كقائمة قواميس.

        :param sql: نص الاستعلام.
        :param params: القيم الآمنة.
        """
        if self._conn is None:
            raise RuntimeError("قاعدة البيانات غير متصلة")
        cursor = await self._conn.execute(sql, params)
        rows = await cursor.fetchall()
        # تحويل صفوف sqlite إلى قواميس
        return [dict(row) for row in rows]

    async def _fetchone(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """ينفذ استعلام قراءة ويعيد صفاً واحداً كقاموس (أو None)."""
        rows = await self._fetchall(sql, params)
        return rows[0] if rows else None

    # ============================================================
    # إنشاء الجداول (Schema)
    # ============================================================

    async def init_schema(self) -> None:
        """
        ينشئ جميع الجداول اللازمة إذا لم تكن موجودة.
        تُستدعى مرة واحدة عند تشغيل التطبيق.
        """
        schema = """
        -- جدول المستخدمين
        CREATE TABLE IF NOT EXISTS users (
            user_id            INTEGER PRIMARY KEY,
            username           TEXT,
            first_name         TEXT,
            last_name          TEXT,
            is_banned          INTEGER DEFAULT 0,
            monitoring_agreed  INTEGER DEFAULT 0,
            prefs              TEXT DEFAULT '{}',
            total_images       INTEGER DEFAULT 0,
            total_videos       INTEGER DEFAULT 0,
            total_requests     INTEGER DEFAULT 0,
            created_at         TEXT,
            last_seen          TEXT
        );

        -- جدول عمليات التبديل (صور وفيديوهات)
        CREATE TABLE IF NOT EXISTS swaps (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER,
            type         TEXT,
            status       TEXT DEFAULT 'processing',
            source_file  TEXT,
            target_file  TEXT,
            result_file  TEXT,
            duration     REAL,
            error        TEXT,
            created_at   TEXT
        );

        -- جدول الرسائل (للمراقبة الشفافة)
        CREATE TABLE IF NOT EXISTS messages (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER,
            username     TEXT,
            name         TEXT,
            message_type TEXT,
            text         TEXT,
            file_id      TEXT,
            replied      INTEGER DEFAULT 0,
            reply_text   TEXT,
            created_at   TEXT
        );

        -- جدول الأخطاء
        CREATE TABLE IF NOT EXISTS errors (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            handler    TEXT,
            message    TEXT,
            created_at TEXT
        );

        -- جدول الإعدادات العامة (مفتاح/قيمة)
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        -- جدول النسخ الاحتياطية
        CREATE TABLE IF NOT EXISTS backups (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            filename   TEXT,
            size       INTEGER,
            created_at TEXT
        );

        -- فهارس لتحسين سرعة البحث
        CREATE INDEX IF NOT EXISTS idx_swaps_user ON swaps(user_id);
        CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);
        CREATE INDEX IF NOT EXISTS idx_errors_time ON errors(created_at);
        """
        if self._conn is None:
            raise RuntimeError("قاعدة البيانات غير متصلة")
        # executescript تنفذ مخططاً بعدة عبارات SQL دفعة واحدة
        async with self._write_lock:
            await self._conn.executescript(schema)
        logger.info("تم إنشاء جداول قاعدة البيانات بنجاح ✓")

    # ============================================================
    # دوال المستخدمين
    # ============================================================

    async def upsert_user(self, user: dict) -> None:
        """
        يسجل مستخدماً جديداً أو يحدّث بيانات مستخدم موجود.
        يستخدم INSERT ... ON CONFLICT لتحديث البيانات المتغيرة فقط.

        :param user: قاموس يحتوي على بيانات المستخدم.
        """
        await self._execute(
            """
            INSERT INTO users (user_id, username, first_name, last_name, monitoring_agreed, prefs, created_at, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                last_seen = excluded.last_seen
            """,
            (
                user.get("user_id"),
                user.get("username"),
                user.get("first_name"),
                user.get("last_name"),
                1 if user.get("monitoring_agreed") else 0,
                user.get("prefs", "{}"),
                user.get("created_at"),
                user.get("last_seen"),
            ),
        )

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """يُرجع بيانات مستخدم حسب معرفه، أو None إن لم يوجد."""
        return await self._fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))

    async def is_user_banned(self, user_id: int) -> bool:
        """يُرجع True إذا كان المستخدم محظوراً."""
        row = await self._fetchone("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
        return bool(row and row.get("is_banned"))

    async def set_monitoring_agreed(self, user_id: int, agreed: bool) -> None:
        """يحفظ موافقة/رفض المستخدم على المراقبة الشفافة."""
        await self._execute(
            "UPDATE users SET monitoring_agreed = ? WHERE user_id = ?",
            (1 if agreed else 0, user_id),
        )

    async def set_user_pref(self, user_id: int, key: str, value: str) -> None:
        """
        يحدّث تفضيلاً واحداً في حقل prefs (JSON) لمستخدم محدد.
        مثال: set_user_pref(123, "quality", "high")
        """
        user = await self.get_user(user_id)
        prefs = {}
        if user and user.get("prefs"):
            try:
                prefs = json.loads(user["prefs"])
            except (json.JSONDecodeError, TypeError):
                prefs = {}
        # تحديث القيمة المطلوبة
        prefs[key] = value
        await self._execute(
            "UPDATE users SET prefs = ? WHERE user_id = ?",
            (json.dumps(prefs, ensure_ascii=False), user_id),
        )

    async def get_user_pref(self, user_id: int, key: str, default: str = "") -> str:
        """يُرجع تفضيلاً معيناً لمستخدم، أو القيمة الافتراضية."""
        user = await self.get_user(user_id)
        if user and user.get("prefs"):
            try:
                return json.loads(user["prefs"]).get(key, default)
            except (json.JSONDecodeError, TypeError):
                pass
        return default

    async def increment_user_counter(self, user_id: int, field: str, amount: int = 1) -> None:
        """
        يزيد عدّاداً رقمياً لمستخدم.
        :param user_id: معرف المستخدم.
        :param field: اسم العمود (total_images / total_videos / total_requests).
        :param amount: مقدار الزيادة.
        """
        allowed = {"total_images", "total_videos", "total_requests"}
        if field not in allowed:
            return
        await self._execute(
            f"UPDATE users SET {field} = {field} + ? WHERE user_id = ?",
            (amount, user_id),
        )

    async def update_last_seen(self, user_id: int, timestamp: str) -> None:
        """يحدّث وقت آخر ظهور للمستخدم."""
        await self._execute(
            "UPDATE users SET last_seen = ? WHERE user_id = ?", (timestamp, user_id)
        )

    async def count_users(self) -> int:
        """يُرجع العدد الإجمالي للمستخدمين."""
        row = await self._fetchone("SELECT COUNT(*) AS c FROM users")
        return int(row["c"]) if row else 0

    async def get_all_users(self) -> List[Dict[str, Any]]:
        """يُرجع جميع المستخدمين (يُستخدم في الإرسال الجماعي)."""
        return await self._fetchall("SELECT * FROM users ORDER BY created_at ASC")

    async def get_recent_users(self, limit: int = 10) -> List[Dict[str, Any]]:
        """يُرجع آخر المستخدمين تسجيلاً."""
        return await self._fetchall(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT ?", (limit,)
        )

    async def ban_user(self, user_id: int) -> None:
        """يحظر مستخدماً (لن يتمكن من استخدام البوت)."""
        await self._execute(
            "UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,)
        )

    async def unban_user(self, user_id: int) -> None:
        """يفك الحظر عن مستخدم."""
        await self._execute(
            "UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,)
        )

    async def delete_user(self, user_id: int) -> None:
        """
        يحذف مستخدماً وجميع بياناته المرتبطة نهائياً.
        (متوافق مع مبادئ الخصوصية: حق المستخدم في حذف بياناته)
        """
        await self._execute("DELETE FROM swaps WHERE user_id = ?", (user_id,))
        await self._execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
        await self._execute("DELETE FROM users WHERE user_id = ?", (user_id,))

    # ============================================================
    # دوال عمليات التبديل
    # ============================================================

    async def add_swap(self, swap: dict) -> int:
        """
        يسجل عملية تبديل جديدة ويعيد معرّفها.
        :param swap: قاموس SwapRecord.
        """
        cursor = await self._execute(
            """
            INSERT INTO swaps (user_id, type, status, source_file, target_file, result_file, duration, error, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                swap.get("user_id"),
                swap.get("type"),
                swap.get("status", "processing"),
                swap.get("source_file"),
                swap.get("target_file"),
                swap.get("result_file"),
                swap.get("duration"),
                swap.get("error"),
                swap.get("created_at"),
            ),
        )
        # نعيد آخر معرّف مدرج
        return cursor.lastrowid

    async def update_swap_status(
        self,
        swap_id: int,
        status: str,
        result_file: Optional[str] = None,
        error: Optional[str] = None,
        duration: Optional[float] = None,
    ) -> None:
        """يحدّث حالة عملية تبديل بعد انتهائها (done / failed)."""
        await self._execute(
            "UPDATE swaps SET status = ?, result_file = ?, error = ?, duration = ? WHERE id = ?",
            (status, result_file, error, duration, swap_id),
        )

    async def count_swaps(self, swap_type: Optional[str] = None) -> int:
        """يُرجع عدد عمليات التبديل (لكل الأنواع أو لنوع محدد)."""
        if swap_type:
            row = await self._fetchone(
                "SELECT COUNT(*) AS c FROM swaps WHERE type = ?", (swap_type,)
            )
        else:
            row = await self._fetchone("SELECT COUNT(*) AS c FROM swaps")
        return int(row["c"]) if row else 0

    async def sum_requests(self) -> int:
        """يُرجع مجموع طلبات التبديل الناجحة (صور + فيديوهات)."""
        row = await self._fetchone(
            "SELECT COALESCE(SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END), 0) AS c FROM swaps"
        )
        return int(row["c"]) if row else 0

    # ============================================================
    # دوال الرسائل (المراقبة الشفافة)
    # ============================================================

    async def add_message(self, msg: dict) -> int:
        """يسجل رسالة واردة ويعيد معرّفها."""
        cursor = await self._execute(
            """
            INSERT INTO messages (user_id, username, name, message_type, text, file_id, replied, reply_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg.get("user_id"),
                msg.get("username"),
                msg.get("name"),
                msg.get("message_type"),
                msg.get("text"),
                msg.get("file_id"),
                1 if msg.get("replied") else 0,
                msg.get("reply_text"),
                msg.get("created_at"),
            ),
        )
        return cursor.lastrowid

    async def mark_message_replied(self, msg_id: int, reply_text: str) -> None:
        """يعلّم رسالة كمُرد عليها مع نص الرد."""
        await self._execute(
            "UPDATE messages SET replied = 1, reply_text = ? WHERE id = ?",
            (reply_text, msg_id),
        )

    async def count_messages(self) -> int:
        """يُرجع العدد الإجمالي للرسائل المستلمة."""
        row = await self._fetchone("SELECT COUNT(*) AS c FROM messages")
        return int(row["c"]) if row else 0

    async def get_recent_messages(self, limit: int = 30) -> List[Dict[str, Any]]:
        """يُرجع آخر الرسائل المستلمة."""
        return await self._fetchall(
            "SELECT * FROM messages ORDER BY id DESC LIMIT ?", (limit,)
        )

    async def get_last_message_id(self, user_id: int) -> Optional[int]:
        """
        يُرجع معرّف آخر رسالة لمستخدم معين (يُستخدم عند رد المطور).
        :param user_id: معرف المستخدم.
        """
        row = await self._fetchone(
            "SELECT id FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        )
        return int(row["id"]) if row else None

    # ============================================================
    # دوال الأخطاء
    # ============================================================

    async def add_error(self, user_id: Optional[int], handler: Optional[str], message: str) -> None:
        """يسجل خطأ في قاعدة البيانات."""
        await self._execute(
            "INSERT INTO errors (user_id, handler, message, created_at) VALUES (?, ?, ?, ?)",
            (user_id, handler, message[:2000], __import__("datetime").datetime.utcnow().isoformat()),
        )

    async def count_errors(self) -> int:
        """يُرجع عدد الأخطاء المسجلة."""
        row = await self._fetchone("SELECT COUNT(*) AS c FROM errors")
        return int(row["c"]) if row else 0

    async def get_recent_errors(self, limit: int = 30) -> List[Dict[str, Any]]:
        """يُرجع آخر الأخطاء المسجلة."""
        return await self._fetchall(
            "SELECT * FROM errors ORDER BY id DESC LIMIT ?", (limit,)
        )

    # ============================================================
    # دوال الإعدادات العامة
    # ============================================================

    async def get_setting(self, key: str, default: str = "") -> str:
        """يُرجع قيمة إعداد عام، أو القيمة الافتراضية."""
        row = await self._fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        """يضبط قيمة إعداد عام (ينشئه إن لم يكن موجوداً)."""
        await self._execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )

    # ============================================================
    # دوال النسخ الاحتياطية
    # ============================================================

    async def add_backup(self, filename: str, size: int) -> None:
        """يسجل نسخة احتياطية جديدة في قاعدة البيانات."""
        await self._execute(
            "INSERT INTO backups (filename, size, created_at) VALUES (?, ?, ?)",
            (filename, size, __import__("datetime").datetime.utcnow().isoformat()),
        )

    async def list_backups(self, limit: int = 20) -> List[Dict[str, Any]]:
        """يُرجع قائمة النسخ الاحتياطية الأخيرة."""
        return await self._fetchall(
            "SELECT * FROM backups ORDER BY id DESC LIMIT ?", (limit,)
        )

    async def backup_exists(self, filename: str) -> bool:
        """يتحقق من وجود نسخة احتياطية باسم محدد."""
        row = await self._fetchone(
            "SELECT 1 FROM backups WHERE filename = ?", (filename,)
        )
        return row is not None


# ----------------------------------------------------------------
# كائن قاعدة البيانات العام (Singleton)
# ----------------------------------------------------------------
# ننشئ كائناً واحداً يستخدمه المشروع كله.
# الاتصال الفعلي يتم في دالة connect (تُستدعى عند تشغيل التطبيق).
# ----------------------------------------------------------------
db = Database(settings.DB_PATH)
