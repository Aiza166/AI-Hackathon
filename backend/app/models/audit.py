"""Append-only, hash-chained audit log.

A database trigger (see the first migration) blocks UPDATE, DELETE and
TRUNCATE on this table, so the application cannot rewrite history.
"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Identity, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.platform import utcnow


class AuditEvent(Base):
    __tablename__ = "audit_events"
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    actor_type: Mapped[str] = mapped_column(String(10))  # user | ai | system | agent | api_key
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    resource: Mapped[str | None] = mapped_column(String(120), nullable=True)
    case_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
