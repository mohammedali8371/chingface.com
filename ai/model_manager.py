# ================================================================
# ملف ai/model_manager.py
# ------------------------
# هذا الملف مسؤول عن إدارة نماذج الذكاء الاصطناعي.
#
# النماذج المستخدمة (من مكتبة InsightFace):
#   1. buffalo_l : نموذج اكتشاف وتحليل الوجوه (يُحمَّل تلقائياً
#      من الإنترنت عند أول استخدام، ويشمل: الكشف، التعرف،
#      نقاط الوجه، تقدير العمر والجنس).
#   2. inswapper_128 : نموذج تبديل الوجه نفسه.
#
# التصميم الذكي هنا:
#   - التحميل كسول (Lazy Loading): لا نحمّل النماذج إلا عند الحاجة
#     (أول عملية تبديل) لتوفير الذاكرة عند تشغيل الخادم.
#   - تحميل واحد لكل نموذج (Singleton) مشترك بين جميع المستخدمين.
#
# ملاحظة مهمة (Render الخطة المجانية):
#   - نعمل على المعالج (CPU) فقط، لذلك ctx_id = -1.
#   - النماذج تُحمَّل من مجلد storage/models وتُعامل ككاش دائم.
# ================================================================

from pathlib import Path
from typing import Optional

from config import settings
from logger import get_logger

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)


class ModelManager:
    """
    الكلاس المسؤول عن تحميل وإدارة نماذج الذكاء الاصطناعي.
    -----------------------------------------------
    يوفر:
        - الوصول إلى نموذج تحليل الوجوه (FaceAnalysis).
        - الوصول إلى نموذج تبديل الوجه (inswapper).
        - إعادة تعيين النماذج (يُستخدم في "إعادة تشغيل الخدمات").
    """

    def __init__(self) -> None:
        # كائن تحليل الوجوه (يُحمَّل عند الطلب الأول)
        self._face_app = None

        # كائن نموذج تبديل الوجه (يُحمَّل عند الطلب الأول)
        self._swapper = None

        # مجلد النماذج
        self.models_dir: Path = settings.MODELS_DIR
        self.models_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------
    # التحقق من توفر المكتبات
    # ------------------------------------------------------------

    @staticmethod
    def _import_insightface():
        """
        يستورد مكتبة insightface بشكل آمن.
        نستورد داخل دالة (وليس أعلى الملف) حتى لا يتعطل البوت
        إذا لم تكن المكتبة مثبتة (مثلاً في بيئة التطوير المحلي).
        """
        try:
            import insightface  # noqa: F401
            return insightface
        except ImportError as exc:
            raise RuntimeError(
                "مكتبة insightface غير مثبتة. قم بتشغيل: pip install -r requirements.txt"
            ) from exc

    def _build_session_options(self):
        """
        يُنشئ خيارات جلسة ONNX Runtime لتقليل استهلاك الذاكرة.
        - يعطّل تخصيص الذاكرة المستمر (Memory Arena) لتقليل التضخم.
        - يحدد عدد الخيوط لمنع ازدحام الذاكرة على الخطة المجانية.
        """
        try:
            import onnxruntime as ort
            opts = ort.SessionOptions()
            # الذاكرة: منع الخوارزميات كثيفة الاستهلاك للمخططات
            opts.enable_cpu_mem_arena = False
            opts.enable_mem_pattern = False
            opts.enable_mem_reuse = True
            # الخيوط: خيط واحد لكل معالج لتقليل الذاكرة
            opts.intra_op_num_threads = 1
            opts.inter_op_num_threads = 1
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            return opts
        except Exception:
            return None

    # ------------------------------------------------------------
    # نموذج تحليل الوجوه
    # ------------------------------------------------------------

    def get_face_app(self):
        """
        يُرجع كائن تحليل الوجوه (FaceAnalysis) مع تحميله عند الحاجة.
        يبحث عن الوجوه ويرجع: الإحداثيات، الملامح، والتضمينات (embeddings).
        """
        if self._face_app is None:
            insightface = self._import_insightface()
            from insightface.app import FaceAnalysis

            logger.info(f"جارٍ تحميل نموذج تحليل الوجوه ({settings.MODEL_NAME})...")
            try:
                # إنشاء كائن التحليل مع مجلد النماذج المخصص
                face_app = FaceAnalysis(
                    name=settings.MODEL_NAME,
                    root=str(self.models_dir),
                    providers=["CPUExecutionProvider"],  # العمل على المعالج
                )
                # تجهيز النموذج: ctx_id=-1 يعني CPU، det_size حجم الكشف
                # حجم كشف أصغر (320) يقلل استهلاك الذاكرة بشكل كبير
                face_app.prepare(
                    ctx_id=-1,
                    det_size=(settings.DET_SIZE, settings.DET_SIZE),
                )
                self._face_app = face_app
                logger.info("نموذج تحليل الوجوه جاهز ✓")
            except Exception as exc:
                logger.error(f"فشل تحميل نموذج تحليل الوجوه: {exc}")
                raise RuntimeError(
                    "تعذر تحميل نموذج تحليل الوجوه. تأكد من الاتصال بالإنترنت "
                    "عند أول تشغيل (يُحمَّل النموذج تلقائياً)."
                ) from exc
        return self._face_app

    # ------------------------------------------------------------
    # نموذج تبديل الوجه
    # ------------------------------------------------------------

    def get_swapper(self):
        """
        يُرجع نموذج تبديل الوجه (inswapper_128) مع تحميله عند الحاجة.
        """
        if self._swapper is None:
            insightface = self._import_insightface()

            # مسار ملف النموذج داخل مجلد النماذج
            model_path = self.models_dir / f"{settings.SWAPPER_MODEL}.onnx"

            # إذا لم يكن الملف موجوداً نحاول تحميله من مكتبة insightface
            if not model_path.exists():
                logger.info(
                    f"ملف النموذج {settings.SWAPPER_MODEL}.onnx غير موجود، "
                    "سيُحمَّل تلقائياً من مكتبة insightface..."
                )

            logger.info(f"جارٍ تحميل نموذج تبديل الوجه ({settings.SWAPPER_MODEL})...")
            try:
                kwargs = {"providers": ["CPUExecutionProvider"]}
                session_options = self._build_session_options()
                if session_options is not None:
                    kwargs["session_options"] = session_options
                # insightface.model_zoo يعرف كيفية تحميل inswapper_128 تلقائياً
                swapper = insightface.model_zoo.get_model(
                    str(model_path),
                    **kwargs,
                )
                self._swapper = swapper
                logger.info("نموذج تبديل الوجه جاهز ✓")
            except Exception as exc:
                logger.error(f"فشل تحميل نموذج تبديل الوجه: {exc}")
                raise RuntimeError("تعذر تحميل نموذج تبديل الوجه.") from exc
        return self._swapper

    # ------------------------------------------------------------
    # إعادة التعيين
    # ------------------------------------------------------------

    def reset(self) -> None:
        """
        يحرر النماذج من الذاكرة.
        يُستخدم في زر "إعادة تشغيل الخدمات" من لوحة المطور
        لتحرير الذاكرة أو إعادة تحميل النماذج بعد تحديثها.
        """
        self._face_app = None
        self._swapper = None
        # تحرير الذاكرة فوراً بعد تحرير المرجعين
        import gc
        gc.collect()
        logger.info("تم تحرير نماذج الذكاء الاصطناعي من الذاكرة")

    def is_ready(self) -> bool:
        """يُعيد True إذا كانت النماذج محمّلة بالفعل."""
        return self._face_app is not None and self._swapper is not None


# ----------------------------------------------------------------
# كائن عام لمدير النماذج (Singleton)
# ----------------------------------------------------------------
model_manager = ModelManager()
