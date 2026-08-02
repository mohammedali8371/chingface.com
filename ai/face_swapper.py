# ================================================================
# ملف ai/face_swapper.py
# -----------------------
# هذا الملف مسؤول عن عملية تبديل الوجه في الصور.
#
# كيف تعمل العملية؟
# ------------------
#   1. نستخرج الوجه من صورة المصدر (صورة الوجه).
#   2. نكتشف كل الوجوه في الصورة الهدف.
#   3. نستبدل كل وجه في الصورة الهدف بوجه المصدر
#      باستخدام نموذج inswapper_128.
#   4. نحسّن النتيجة (إن كان التحسين مفعلاً).
#
# نحافظ على الإضاءة والظلال والملامح الطبيعية عبر خيار
# paste_back الذي يعيد دمج الوجه مع الخلفية الأصلية بلطف.
# ================================================================

from pathlib import Path
from typing import Optional, Tuple

import cv2

from ai.enhancer import enhancer
from ai.model_manager import model_manager
from config import settings
from logger import get_logger

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)


class NoFaceError(Exception):
    """يُرفع عندما لا يجد النظام أي وجه في صورة معينة."""

    def __init__(self, context: str = "") -> None:
        # رسالة واضحة للمستخدم حسب السياق
        msg = "لم أتمكن من العثور على وجه واضح في الصورة."
        if context == "source":
            msg = "لم أجد وجهك في صورة الوجه. تأكد أن الصورة تحتوي على وجه واضح ومواجه للكاميرا."
        elif context == "target":
            msg = "لم أجد وجوهاً في الصورة الهدف. تأكد أن الصورة تحتوي على وجوه واضحة."
        super().__init__(msg)
        self.message = msg


class FaceSwapper:
    """
    الكلاس المسؤول عن تبديل الوجه في الصور.
    -----------------------------------------
    يستخدم نموذجين:
        - FaceAnalysis (buffalo_l) لاكتشاف الوجوه.
        - inswapper_128 لتنفيذ التبديل.
    """

    def __init__(self) -> None:
        # نأخذ مدير النماذج العام (مشترك بين الجميع)
        self.models = model_manager

    # ------------------------------------------------------------
    # دوال مساعدة
    # ------------------------------------------------------------

    def _read_image(self, path: Path):
        """يقرأ صورة من القرص ويعيدها بتنسيق BGR."""
        img = cv2.imread(str(path))
        if img is None:
            raise ValueError(f"تعذر قراءة الصورة: {path}")
        # تصغير الصور الكبيرة لتوفير الذاكرة وتسريع المعالجة
        return self._resize_if_large(img)

    def _resize_if_large(self, img):
        """
        يصغر الصورة إذا كان بعدها الأطول أكبر من الحد المحدد.
        هذا يقلل استهلاك الذاكرة بشكل كبير على الخطط المجانية.
        """
        h, w = img.shape[:2]
        max_dim = settings.MAX_IMAGE_DIM
        if max_dim <= 0:
            return img
        longest = max(h, w)
        if longest <= max_dim:
            return img
        scale = max_dim / longest
        new_size = (int(w * scale), int(h * scale))
        logger.debug(f"تصغير الصورة {w}x{h} -> {new_size[0]}x{new_size[1]}")
        return cv2.resize(img, new_size, interpolation=cv2.INTER_AREA)

    def _detect_faces(self, img, required: int = 1, context: str = ""):
        """
        يكتشف الوجوه في صورة.
        :param img: الصورة بتنسيق BGR.
        :param required: الحد الأدنى لعدد الوجوه المطلوبة.
        :param context: سياق الصورة (source / target) لرسالة الخطأ.
        """
        face_app = self.models.get_face_app()
        faces = face_app.get(img)
        if not faces or len(faces) < required:
            raise NoFaceError(context)
        return faces

    # ------------------------------------------------------------
    # تبديل الصورة
    # ------------------------------------------------------------

    def swap_image(
        self,
        source_path: Path,
        target_path: Path,
        output_path: Path,
        enable_enhance: bool = True,
        enhance_level: str = "high",
    ) -> Path:
        """
        ينفذ عملية تبديل الوجه بين صورتين ويحفظ النتيجة.

        :param source_path: مسار صورة الوجه (المصدر).
        :param target_path: مسار الصورة الهدف.
        :param output_path: مسار حفظ النتيجة.
        :param enable_enhance: هل نفعّل تحسين الجودة؟
        :param enhance_level: مستوى التحسين (high / medium / off).
        :return: مسار النتيجة.
        """
        logger.info(f"بدء تبديل الوجه: {source_path.name} -> {target_path.name}")

        # قراءة الصور
        source_img = self._read_image(source_path)
        target_img = self._read_image(target_path)

        # 1) استخراج وجه المصدر (نأخذ أول وجه - الأكثر وضوحاً)
        source_faces = self._detect_faces(source_img, required=1, context="source")
        source_face = source_faces[0]

        # 2) اكتشاف كل الوجوه في الصورة الهدف
        target_faces = self._detect_faces(target_img, required=1, context="target")

        # 3) الحصول على نموذج التبديل
        swapper = self.models.get_swapper()

        # 4) تبديل كل وجه في الصورة الهدف
        result = target_img.copy()
        for face in target_faces:
            # paste_back=True يعيد دمج الوجه مع الخلفية الأصلية بلطف
            # مما يحافظ على الإضاءة والظلال والمنظور الطبيعي
            result = swapper.get(result, face, source_face, paste_back=True)

        # 5) تحسين الجودة (اختياري)
        if enable_enhance and enhance_level != "off":
            # نمرر مستوى التحسين عبر كائن enhancer
            from ai.enhancer import FaceEnhancer

            temp_enhancer = FaceEnhancer(enabled=True, level=enhance_level)
            result = temp_enhancer.enhance(result)

        # 6) حفظ النتيجة
        # نتأكد من صحة امتداد الملف الناتج
        output_path = Path(output_path)
        cv2.imwrite(str(output_path), result)
        if not output_path.exists():
            raise RuntimeError("فشل حفظ الصورة الناتجة.")

        # تحرير الذاكرة مؤقتاً بعد العملية لتخفيف الضغط على الخطة المجانية
        try:
            del source_img, target_img, result
            import gc
            gc.collect()
        except Exception:
            pass

        logger.info(f"تم تبديل الوجه بنجاح: {output_path}")
        return output_path

    # ------------------------------------------------------------
    # الحصول على معلومات عملية (للتقارير)
    # ------------------------------------------------------------

    def validate_source_has_face(self, source_path: Path) -> Tuple[bool, str]:
        """
        يتحقق مسبقاً من وجود وجه في صورة المصدر.
        يُستخدم قبل إجراء التبديل لإعطاء رد أسرع.

        :return: (هل يوجد وجه، رسالة توضيحية).
        """
        try:
            img = self._read_image(source_path)
            faces = self._detect_faces(img, required=1, context="source")
            return True, f"تم العثور على {len(faces)} وجه."
        except NoFaceError as exc:
            return False, exc.message
        except Exception as exc:
            logger.error(f"خطأ في فحص صورة المصدر: {exc}")
            return False, "حدث خطأ أثناء فحص الصورة."


# ----------------------------------------------------------------
# كائن عام لنظام تبديل الوجه (Singleton)
# ----------------------------------------------------------------
face_swapper = FaceSwapper()
