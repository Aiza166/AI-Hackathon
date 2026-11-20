"""Seed demo data only when the database has no users (first deploy). Safe to run on every boot."""
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models.platform import User
from app.seed import reset


def main() -> None:
    with SessionLocal() as db:
        if (db.execute(select(func.count(User.id))).scalar() or 0) > 0:
            print("Database already has data: skipping seed.")
            return
        reset(db)
        print("Seeded demo data (first boot).")


if __name__ == "__main__":
    main()
