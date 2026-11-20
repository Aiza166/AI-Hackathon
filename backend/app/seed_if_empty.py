"""Seed demo data on boot when the database is empty or was seeded by an older seed version.

Safe to run on every boot: when the seed version matches, nothing changes, so demo
data created during judging is kept. The audit log is never wiped.
"""
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models.audit import AuditEvent
from app.models.platform import User
from app.seed import SEED_VERSION, reset


def _current_seed_version(db) -> str | None:
    last = db.execute(
        select(AuditEvent.details).where(AuditEvent.action == "DEMO_RESET").order_by(AuditEvent.seq.desc()).limit(1)
    ).scalar()
    return (last or {}).get("seed")


def main() -> None:
    with SessionLocal() as db:
        has_users = (db.execute(select(func.count(User.id))).scalar() or 0) > 0
        if has_users and _current_seed_version(db) == SEED_VERSION:
            print(f"Seed {SEED_VERSION} already loaded: skipping.")
            return
        reset(db)
        print(f"Seeded demo data ({SEED_VERSION}).")


if __name__ == "__main__":
    main()
