# Backend container for Railway (or any Docker host).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# Tesseract is the free OCR fallback when Azure Document Intelligence is not configured.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-urd libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.lock ./
# Exact versions of the whole tree (tested), not just the direct dependencies.
RUN pip install -r requirements.lock

COPY . .
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \n  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT', '8000'), timeout=4)" || exit 1

# start.sh: migrate, seed once if the database is empty, then serve on $PORT.
CMD ["sh", "start.sh"]
