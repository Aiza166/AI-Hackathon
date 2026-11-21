"""Idempotency keys for POST /api/v1/cases (IETF Idempotency-Key header draft).

One row per (principal, key). The row is written as "in_flight" and committed
before the claim is processed, then updated to "done" with the stored response,
so a retry from a weak connection replays the first answer instead of filing a
second claim.
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.platform import new_id, utcnow


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("principal_id", "key", name="uq_idempotency_principal_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    principal_id: Mapped[str] = mapped_column(String(36))
    key: Mapped[str] = mapped_column(String(255))
    request_hash: Mapped[str] = mapped_column(String(64))  # sha256 of the canonical JSON body
    status: Mapped[str] = mapped_column(String(12))  # in_flight | done
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
