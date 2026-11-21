#!/bin/sh
# Container entry point: apply migrations, seed demo data on first boot, serve.
set -e
alembic upgrade head
python -m app.seed_if_empty
# --proxy-headers: rate limits must see the real client IP behind the platform proxy.
# Only X-Forwarded-For from FORWARDED_ALLOW_IPS (comma-separated IPs/CIDRs) is believed;
# never '*', or any client could pick its own IP and dodge the limits.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers \
  --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}" --no-server-header
