# 📄 وصف الملفات (FILES_DESCRIPTION)

شرح مفصل لكل ملف في المشروع: ماذا يفعل، الدوال/الكلاسات الرئيسية فيه،
والعلاقة بين الملفات. الترتيب من الأدنى (الأساسيات) إلى الأعلى (نقطة التشغيل).

---

## 🧱 ملفات الأساس

### `config.py`
| العنصر | الوصف |
| --- | --- |
| `class Settings(BaseSettings)` | يقرأ الإعدادات من `.env` عبر `pydantic-settings`. |
| `validate()` | يتحقق من وجود `BOT_TOKEN` و `PUBLIC_URL` ويرفع خطأ إن لم توجد. |
| `webhook_url()` | يبني رابط الـ Webhook: `<PUBLIC_URL>/webhook`. |
| `effective_secret()` | الرمز السري: من `SECRET_TOKEN` أو مشتقاً من SHA-256 للتوكن. |
| `allowed_updates_list()` | قائمة أنواع التحديثات المسموحة (`message, callback_query`). |
| `settings` | المثيل الوحيد المشترك، يستورده كل ملف. |

**علاقاته:** يُستخدم في كل الملفات تقريباً.

---

### `logger.py`
| العنصر | الوصف |
| --- | --- |
| `setup_logging()` | إعداد تنسيق السجلات والمستوى ومجلد `logs/`. |
| `MemoryLogHandler` | مخزن أخطاء في الذاكرة (لزر «الأخطاء» في لوحة المطور). |
| `get_recent_errors(limit)` | يُرجع آخر الأخطاء المسجلة. |
| `get_logger(name)` | يُرجع سجل باسم الوحدة مع إعدادات موحدة. |

**علاقاته:** مستقل.

---

### `database.py`
| العنصر | الوصف |
| --- | --- |
| `class Database` | يدير اتصال `aiosqlite` بملف `DB_PATH`. |
| `connect()` / `close()` / `reconnect()` | إدارة دورة حياة الاتصال. |
| `init_schema()` | ينشئ الجداول: `users, messages, swap_operations, broadcasts, backups, banlist`. |
| `is_connected()` | هل الاتصال مفتوح؟ (يستخدمها وسيط الحماية). |
| دوال المستخدمين | `add_user, get_user, update_*` (اسم، عملة/لغة، مستوى جودة، موافقة المراقبة، حظر). |
| دوال الرسائل | `log_message, get_last_message_id, get_recent_messages, get_messages_count`. |
| دوال العمليات | `log_swap_operation, count_*` (صور/فيديوهات/نجاح/فشل). |
| دوال الإدارة | `list_users, count_users, get_user_by_id, delete_user, broadcast_*`. |
| دالة النسخ | `add_backup, list_backups`. |
| `db` | المثيل الوحيد المشترك. |

**علاقاته:** تستخدمه كل الخدمات والمعالجات.

---

### `states.py`
- `class ConversationState`: ثوابت أرقام حالات المحادثات:
  - الصور: `IMAGE_SWAP_SOURCE=10`, `IMAGE_SWAP_TARGET=11`.
  - الفيديو: `VIDEO_SWAP_SOURCE=20`, `VIDEO_SWAP_TARGET=21`.
  - المطور: `30` إلى `38` (إدخال رسالة جماعية، رد، حظر، ...).

**علاقاته:** يستخدمه `bot.py` ومحادثات المطور.

---

### `callbacks.py`
- `class Callbacks`: نصوص أزرار الأزرار الشفافة كلها (قائمة، إعدادات، لوحة مطور، ديناميكية).
- دوال مساعدة: `reply_callback`, `ban_msg_callback`, `delete_msg_callback`, `parse_user_id_from_callback`.

**علاقاته:** يستخدمه `keyboards.py`, `bot.py`, المعالجات.

---

### `keyboards.py`
| العنصر | الوصف |
| --- | --- |
| `main_menu_keyboard()` | أزرار القائمة الرئيسية (تبديل صورة/فيديو، إعدادات، مساعدة، لوحة مطور). |
| `settings_keyboard()` | إعدادات الجودة والخصوصية. |
| `help_keyboard()`, `about_keyboard()`, `privacy_keyboard()` | لوحات المساعدة. |
| `dev_panel_keyboard()`, `dev_back_keyboard()` | لوحات المطور. |
| `agree_keyboard()` | أزرار الموافقة على المراقبة. |
| أزرار ديناميكية | `message_action_buttons(user_id)` للرد/الحظر/الحذف. |

**علاقاته:** يستخدم `callbacks.py`؛ تُستخدم في كل المعالجات.

---

## 🧰 الأدوات

### `utils/validators.py`
| الدالة | الوصف |
| --- | --- |
| `is_developer(user_id)` | هل المستخدم هو المطور (`DEV_ID`)؟ |
| `is_allowed_user(user_id)` | هل غير محظور؟ |
| `validate_image_file_size` | الحد الأقصى لحجم الصورة. |
| `validate_video_file_size` | الحد الأقصى لحجم الفيديو. |
| `validate_video_duration` | أقصى مدة للفيديو (ثوانٍ). |
| `safe_text(text)` | تنسيق النص بأمان. |

### `utils/helpers.py`
| الدالة | الوصف |
| --- | --- |
| `format_bytes(n)` | تحويل البايتات إلى نص مقروء (KB/MB). |
| `format_duration(seconds)` | تنسيق المدة. |
| `utc_now_iso()` | الوقت الحالي بصيغة ISO. |
| `parse_int(text)` | تحويل آمن إلى رقم صحيح. |
| `run_in_executor(coro)` | تشغيل دالة بلوكينج في مؤشر ترابط منفصل (حتى لا نجمد البوت أثناء المعالجة). |

### `utils/rate_limiter.py`
- `class RateLimiter`: حد أقصى للطلبات لكل مستخدم لكل نافذة زمنية.
- `async check(user_id) -> bool` هل يستطيع المستخدم المتابعة الآن؟

### `utils/cleanup.py`
- `async periodic_cleanup(...)`: حلقة خلفية تحذف الملفات المؤقتة الأقدم من `max_age_seconds` كل `interval_seconds`، تتوقف عبر `stop_event`.

---

## 💾 التخزين

### `storage/manager.py`
| العنصر | الوصف |
| --- | --- |
| `class StorageManager` | ينشئ المجلدات (`storage/temp`, `storage/models`, `storage/backups`) عند البناء. |
| `new_temp_file(user_id, ext)` | مسار ملف مؤقت فريد. |
| `download_telegram_file(bot, file_id, dest)` | تنزيل من تيليجرام. |
| `cleanup_user_temp`, `clear_all_temp`, `temp_total_size` | إدارة الكاش. |
| `create_backup`, `restore_backup_file`, `list_backup_files`, `get_db_bytes`, `replace_db` | النسخ الاحتياطي. |
| `storage` | المثيل الوحيد المشترك. |

---

## 🧠 محرك الذكاء الاصطناعي

### `ai/model_manager.py`
| العنصر | الوصف |
| --- | --- |
| `MODEL_DIR` | مجلد النماذج. |
| `download_model()` | ينزل `inswapper_128.onnx` من GitHub إذا لم يوجد. |
| `load_face_analysis()` | يحمّل `buffalo_l` (كاشف الوجوه) مع شرط وجود `tritonruntime`. |
| `load_swapper()` | يحمّل مبدّل الوجه. |
| `get_face_swapper()` | وصول كسول مع التأكد من توفر الملفات. |

**علاقاته:** يستخدمه `face_swapper.py`.

### `ai/face_swapper.py`
| الدالة | الوصف |
| --- | --- |
| `swap_faces(source_path, target_path, output_path)` | يقرأ الصورتين، يستخرج الوجه الأول من كل صورة، يتحقق من وجود وجهين، يبدّل الوجه، يحفظ النتيجة. |
| `run_swap(source_path, target_path, output_path, enhancer_level)` | ينفذ التبديل (في مؤشر ترابط منفصل) + تحسين الجودة حسب المستوى، يعيد `(success, error, output_path)`. |

**علاقاته:** يستخدم `model_manager`, `enhancer`.

### `ai/enhancer.py`
| الدالة | الوصف |
| --- | --- |
| `enhance_image(img, level)` | تحسين لون (CLAHE) + إزالة ضوضاء + توضيح حسب المستوى (`high`/`medium`). |
| `enhancer` | وصول لتثبيت الحجم الأقصى للصورة. |

### `ai/video_processor.py`
| الدالة | الوصف |
| --- | --- |
| `process_video(source_path, video_path, output_path, max_duration)` | يقرأ الفيديو، يستخرج الوجه من الصورة، يبدّل الوجه إطاراً بإطار، يكتب الناتج. |
| `_find_ffmpeg()` | يبحث عن `ffmpeg`؛ إن وجد يضغط بالفيديو مع الصوت، وإلا يكتب `mp4v` بدون صوت (خطة بديلة). |

**علاقاته:** يستخدم `face_swapper`.

---

## 🧩 الخدمات

### `services/user_service.py`
- `ensure_user(user_id, first_name, username)` — تسجيل/تحديث المستخدم.
- `user_agreed_monitoring`, `set_quality_level`, `get_quality_level`, `is_banned`, `ban_user`, `unban_user`.

### `services/stats_service.py`
- `get_stats()` — إجماليات (مستخدمون، صور، فيديوهات، نجاح/فشل، وقت التشغيل).
- `get_users_count()`, `get_recent_users(limit)`.

### `services/broadcast_service.py`
- `async send_broadcast(application, text)` — إرسال لكل المستخدمين، يعيد `(sent, failed)`.

### `services/backup_service.py`
- `create_backup()`, `list_backups()`, `restore_backup(filename)`, `list_disk_backups()`.
- `backup_service` — المثيل الوحيد المشترك.

---

## 🖥️ معالجات المستخدم

### `handlers/base.py`
| الدالة | الوصف |
| --- | --- |
| `ensure_user(update)` | تسجيل المستخدم قبل أي معالجة. |
| `check_access(update)` | رفض المحظورين. |
| `cancel_flow(update, context)` | إلغاء المحادثة الحالية. |
| `expect_photo(update, context)` | يطلب صورة صالحة. |
| `expect_video(update, context)` | يطلب فيديو صالحاً. |
| `on_error(update, context)` | معالج الأخطاء العام (يسجل ويخبر المستخدم). |

### `handlers/start.py`
- `start_command` — يرسل الترحيب، وإن لم يوافق بعد على المراقبة يعرض شاشة الموافقة.
- `agree_monitoring` / `decline_monitoring` — الموافقة أو الرفض.
- `main_menu_callback` — يفتح القائمة الرئيسية.

### `handlers/help_menu.py`
- `help_callback`, `about_callback`, `privacy_callback`, `developer_callback`.

### `handlers/settings.py`
- `settings_menu`, `quality_high`, `quality_medium`, `quality_off`, `my_stats`, `delete_my_data`.

### `handlers/image_swap.py`
- `image_swap_start` — يبدأ المحادثة ويطلب الصورة الأولى (المصدر).
- `image_swap_receive_source` — يحفظ صورة المصدر، يطلب الصورة الثانية.
- `image_swap_receive_target` — يتحقق من الحجم، ينفذ التبديل في الخلفية (`asyncio.create_task`) ويرسل النتيجة.

### `handlers/video_swap.py`
- `video_swap_start`, `video_swap_receive_source`, `video_swap_receive_target` — نفس النمط مع فيديو (فحص الحجم والمدة).

---

## 🧑‍💻 لوحة المطور

### `admin/handlers.py`
| العنصر | الوصف |
| --- | --- |
| `build_admin_conversation()` | ConversationHandler لمحاورات المطور (إدخال نص الرسالة الجماعية، معرف المستخدم، رسالة مباشرة...). |
| `notify_dev_message(update, ...)` | إرسال رسالة المستخدم للمطور مع الأزرار (مراقبة شفافة). |
| `admin_ban_msg(update, context)` | زر «حظر» من رسالة محولة. |
| `admin_delete_msg(update, context)` | زر «حذف مستخدم» من رسالة محولة. |
| `on_message_logging(update, context)` | المعالج الشامل: يسجل كل رسالة في قاعدة البيانات، وإن كانت المراقبة مفعّلة يحولها للمطور. |

### `admin/panel.py`
- أزرار اللوحة الفورية: `show_dev_panel`, `dev_stats`, `dev_users_count`, `dev_recent_users`, `dev_recent_messages`, `dev_errors`, `dev_bot_on`, `dev_bot_off`, `dev_restart_services`, `dev_clear_cache`, `dev_download_db`, `dev_backup` + استعادة/رفع/حظر/حذف.

---

## 🌐 الويب والوسائط

### `middlewares/auth_middleware.py`
- `class WebhookSecurityMiddleware`: يفحص ترويسة `X-Telegram-Bot-Api-Secret-Token` في مسار `/webhook`، ويعيد 403 عند اختلافها، ويتحقق أن البوت يعمل وقاعدة البيانات متصلة.

### `web/webhook.py`
- `router` مع `POST /webhook`: يتسلم التحديث، يبني `Update` عبر `Update.de_json`، يمرره إلى `application.process_update`.

### `web/health.py`
- `GET /health` — حالة التطبيق وقاعدة البيانات.
- `GET /` — صفحة تعريف بسيطة.

---

## 🚀 نقطة التشغيل

### `bot.py`
| العنصر | الوصف |
| --- | --- |
| `build_application()` | يبني `Application` ويسجل كل المعالجات بالترتيب الصحيح. |
| `get_application()` | يُرجع التطبيق الحالي (يبنيه إن لزم) — تُستدعى من الـ Webhook. |
| `_register_handlers(app)` | التسجيل الفعلي: `/start`، محادثات الصور والفيديو، محادثة المطور، الأزرار العامة، ثم المعالج الشامل. |
| `setup_webhook(app)` | يضبط `set_webhook` بالرمز السري و `drop_pending_updates`. |
| `delete_webhook(app)` | حذف الـ Webhook عند الإغلاق. |

### `main.py`
| العنصر | الوصف |
| --- | --- |
| `lifespan(app)` | عند البدء: إعداد السجلات → التحقق من الإعدادات → الاتصال بقاعدة البيانات → بناء البوت → ضبط الـ Webhook → تشغيل التنظيف الدوري. عند الإغلاق: عكس كل ذلك بأمان. |
| `app` | تطبيق FastAPI مع الوسيط والراوترات. |

---

## 🗂️ ملفات الإعدادات

| الملف | الوصف |
| --- | --- |
| `requirements.txt` | المكتبات: `python-telegram-bot~=22.0`, `fastapi`, `uvicorn`, `aiosqlite`, `insightface==0.7.3`, `numpy==1.26.4`, `opencv-python-headless`, `onnxruntime`, `psutil`, `pydantic-settings`, `python-dotenv`, `python-multipart`. |
| `render.yaml` | إعداد Web Service على Render (build/start/memory/متغيرات). |
| `.env.example` | قالب المتغيرات (نسخ إلى `.env`). |
| `.python-version` | يثبت إصدار بايثون 3.11.9. |
| `.gitignore` | يحمي التوكن والملفات المؤقتة. |
| `README.md` | دليل التشغيل والنشر. |
| `CHANGELOG.md` | سجل التغييرات. |

---

## 🔗 العلاقات الرئيسية باختصار

```
main.py ──► bot.py ──► handlers/ (المستخدم) ──► ai/ (المحرك) ──► storage/ + services/
   │            │                              │
   │            └── admin/ (لوحة المطور)       └── models/ (نماذج على القرص)
   │
   ├── web/webhook.py ──► bot.get_application()
   ├── web/health.py
   └── middlewares/auth_middleware.py
```

كل المسارات مبنية في `config.py`، وكل طبقة تتحدث مع `database.py` عبر مثيل `db` الوحيد.
