# All three OCR engines in one CPU-only image, so the test is repeatable.
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir easyocr pytesseract paddleocr reportlab pymupdf pillow numpy
# paddlepaddle 3.3.1 crashes on CPU with oneDNN ("ConvertPirAttribute2RuntimeAttribute not support"); 3.1.1 works
RUN pip install --no-cache-dir "paddlepaddle==3.1.1"
WORKDIR /bench
