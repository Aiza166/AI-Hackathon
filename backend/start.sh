#!/bin/sh
# Container entry point: apply migrations, seed demo data on first boot, serve.
set -e
alembic upgrade head
python -m app.seed_if_empty
# --proxy-headers: rate limits must see the real client IP behind Railway's proxy.
# Railway's edge is one proxy hop: rate limits key on the rightmost X-Forwarded-For entry.
export RATE_LIMIT_PROXY_HOPS="${RATE_LIMIT_PROXY_HOPS:-1}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips '*'
