FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies for document intelligence and OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY app/ /app/app/
COPY tools/ /app/tools/
COPY outputs/ /app/outputs/
COPY scripts/ /app/scripts/
COPY tests/ /app/tests/

# Persistent directory for document uploads
RUN mkdir -p /app/storage/uploads && chmod -R 777 /app/storage

EXPOSE 8080

HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=10 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
