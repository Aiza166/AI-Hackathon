"""Scam Shield checks. Stores signals and verdicts for the Scam Map, never the phone number,
and only a hash of the message text (no personal data kept)."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.platform import new_id, utcnow


class ScamCheck(Base):
    __tablename__ = "scam_checks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    text_hash: Mapped[str] = mapped_column(String(64))
    scam_type: Mapped[str] = mapped_column(String(30))  # fee | secret_code | link | impersonation | other
    area: Mapped[str | None] = mapped_column(String(60), nullable=True)
    signals: Mapped[dict] = mapped_column(JSON)
    model_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    verdict: Mapped[str] = mapped_column(String(20))
    score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
