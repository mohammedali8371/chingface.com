# ================================================================
# Dockerfile — للنشر على Hugging Face Spaces (وأي سحابة Docker)
# ----------------------------------------------------------------
# يستخدم Python 3.11 لأن المكتبات (numpy 1.26.4 / onnxruntime 1.17.1)
# مقفلة عليه، ويبني insightface من المصدر (يتطلب gcc/cython).
# ================================================================

# صورة بايثون 3.11 مع أدوات البناء (gcc) لتجميع insightface
FROM python:3.11-slim

# أدوات نظام مطلوبة لتجميع insightface وopencv
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        g++ \
        libglib2.0-0 \
        libgl1 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# إعدادات بايثون
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# مجلد العمل
WORKDIR /app

# نسخ ملف المتطلبات أولاً للاستفادة من ذاكرة التخزين المؤقت
COPY requirements.txt .

# تثبيت المتطلبات
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# نسخ باقي المشروع
COPY . .

# المنفذ الذي تستخدمه Hugging Face Spaces (7860)
ENV PORT=7860
EXPOSE 7860

# أمر التشغيل
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1"]
