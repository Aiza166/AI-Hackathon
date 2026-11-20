# Backend container for Railway (or any Docker host).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

# start.sh: migrate, seed once if the database is empty, then serve on $PORT.
CMD ["sh", "start.sh"]
