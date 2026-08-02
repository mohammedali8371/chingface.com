# ================================================================
# ملف ai/enhancer.py
# -------------------
# هذا الملف مسؤول عن تحسين جودة الوجه بعد عملية التبديل.
#
# الهدف من التحسين:
#   - إعادة ملامح الوجه الطبيعية بعد دمج الوجه الجديد.
#   - تحسين الوضوح والحدة مع الحفاظ على:
#       * الإضاءة والألوان والظلال.
#       * اتجاه الوجه ومنظوره.
#       * التفاصيل الدقيقة.
#
# خيارات التحسين:
#   1. GFPGAN (الأفضل): نموذج تعلم عميق لترميم الوجوه.
#      يتطلب تثبيت حزمة gfpgan مع torch يدوياً (ضخمة).
#   2. OpenCV Fallback (خفيف): تحسين يدوي خفيف بالاعتماد على
#      OpenCV فقط - يعمل دائماً وبدون مكتبات إضافية.
#
# ملاحظة صادقة: لا يوجد نظام يحقق واقعية مضمونة في جميع الصور،
# فالنتيجة تعتمد على جودة الصور وزواياها وإضاءتها.
# ================================================================

from typing import Optional

import cv2
import numpy as np

from config import settings
from logger import get_logger

# سجل خاص بهذه الوحدة
logger = get_logger(__name__)


class FaceEnhancer:
    """
    الكلاس المسؤول عن تحسين جودة الوجوه.
    --------------------------------------
    يحاول استخدام GFPGAN إن كان مثبتاً، ويرجع تلقائياً
    إلى تحسين خفيف بـ OpenCV في حالة عدم توفره.
    """

    def __init__(self, enabled: bool = None, level: str = None) -> None:
        """
        :param enabled: هل التحسين مفعّل؟ (يُؤخذ من الإعدادات افتراضياً).
        :param level: مستوى التحسين (high / medium / off).
        """
        self.enabled = settings.ENABLE_ENHANCER if enabled is None else enabled
        self.level = (settings.ENHANCER_LEVEL if level is None else level).lower()

        # كائن GFPGAN (يُحمَّل عند أول استخدام فقط)
        self._ganer: Optional[object] = None
        self._gfpgan_available: bool = False
        self._gfpgan_tried: bool = False

    # ------------------------------------------------------------
    # تحميل GFPGAN (اختياري)
    # ------------------------------------------------------------

    def _load_gfpgan(self) -> None:
        """
        يحاول تحميل GFPGAN من مكتبة gfpgan.
        إن فشل التحميل (المكتبة غير مثبتة) نعتمد على OpenCV.
        """
        self._gfpgan_tried = True
        try:
            from gfpgan import GFPGANer

            # تحميل النموذج بمستوى إعادة إعمار منخفض (أسرع وأخف)
            self._ganer = GFPGANer(
                model_path="GFPGANv1.4",
                upscale=1,          # لا نكبّر الصورة، نرمّمها فقط
                arch="clean",
                channel_multiplier=2,
                bg_upsampler=None,  # لا نعالج الخلفية (أسرع)
            )
            self._gfpgan_available = True
            logger.info("GFPGAN جاهز للاستخدام ✓")
        except Exception as exc:
            self._gfpgan_available = False
            logger.warning(
                f"GFPGAN غير متاح، سيُستخدم تحسين OpenCV الخفيف. ({exc})"
            )

    # ------------------------------------------------------------
    # التحسين الخفيف بـ OpenCV
    # ------------------------------------------------------------

    @staticmethod
    def _light_enhance(img: np.ndarray, level: str = "medium") -> np.ndarray:
        """
        تحسين خفيف يعمل دائماً دون مكتبات إضافية:
          1. معادلة التوازن اللوني (Automatic White Balance).
          2. تقليل التشويش (Denoising) للحصول على ملمس أنعم.
          3. ضبط التباين والحدة قليلاً.

        :param img: صورة BGR.
        :param level: قوة التحسين (high / medium).
        """
        try:
            result = img.copy()

            # 1) توازن الألوان: نقل متوسط كل قناة نحو القيمة المتوسطة
            lab = cv2.cvtColor(result, cv2.COLOR_BGR2LAB)
            lab_planes = list(cv2.split(lab))
            # تصحيح متوسط قناة a و b (توازن الألوان)
            for i in (1, 2):
                mean_val = np.mean(lab_planes[i])
                # نعدل القناة بلطف نحو المتوسط (0.2 * فرق)
                lab_planes[i] = cv2.add(
                    lab_planes[i],
                    (128 - mean_val) * 0.2,
                )
            result = cv2.cvtColor(cv2.merge(lab_planes), cv2.COLOR_LAB2BGR)

            # 2) إزالة التشويش مع الحفاظ على الحواف
            result = cv2.fastNlMeansDenoisingColored(result, None, 3, 3, 7, 21)

            # 3) ضبط التباين والسطوع (Gamma = 1.0 يعني بدون تغيير تقريباً)
            # زيادة خفيفة في الحدة عبر Unsharp Masking
            blur = cv2.GaussianBlur(result, (0, 0), 2.0 if level == "high" else 1.0)
            sharpened = cv2.addWeighted(result, 1.5, blur, -0.5, 0)

            # نطبق الحدة فقط على مستوى معتدل حفاظاً على الملامح
            alpha = 0.7 if level == "high" else 0.4
            result = cv2.addWeighted(result, 1 - alpha, sharpened, alpha, 0)

            return result
        except Exception as exc:
            logger.warning(f"فشل التحسين الخفيف: {exc}")
            return img

    # ------------------------------------------------------------
    # الدالة الرئيسية للتحسين
    # ------------------------------------------------------------

    def enhance(self, img_bgr: np.ndarray) -> np.ndarray:
        """
        يحسّن جودة صورة وجه بعد التبديل.

        :param img_bgr: الصورة بتنسيق BGR (تنسيق OpenCV).
        :return: الصورة المحسّنة (نفس التنسيق BGR).
        """
        # إذا كان التحسين معطلاً نرجع الصورة كما هي
        if not self.enabled or self.level == "off":
            return img_bgr

        # محاولة تحميل GFPGAN (مرة واحدة فقط)
        if not self._gfpgan_tried:
            self._load_gfpgan()

        # 1) استخدام GFPGAN إن كان متاحاً
        if self._gfpgan_available and self._ganer is not None:
            try:
                # GFPGANer يعمل على RGB داخلياً
                _, _, enhanced = self._ganer.enhance(
                    img_bgr,
                    has_aligned=False,       # الوجه غير محاذى (صورة عادية)
                    only_center_face=False,  # نحسّن كل الوجوه
                    paste_back=True,         # نعيد الوجه للخلفية الأصلية
                )
                if enhanced is not None:
                    logger.debug("تم تحسين الصورة باستخدام GFPGAN")
                    return enhanced
            except Exception as exc:
                logger.warning(f"فشل GFPGAN على هذه الصورة: {exc}")

        # 2) الرجوع للتحسين الخفيف بـ OpenCV
        logger.debug("تحسين خفيف بـ OpenCV")
        return self._light_enhance(img_bgr, self.level)


# ----------------------------------------------------------------
# كائن عام لنظام التحسين (Singleton)
# ----------------------------------------------------------------
# ننشئ كائناً واحداً يعتمد على الإعدادات العامة.
# ----------------------------------------------------------------
enhancer = FaceEnhancer()
