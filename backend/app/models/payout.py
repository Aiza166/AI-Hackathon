"""SafeSwitch: requests to change where a pension is paid (the most common way benefits are stolen)."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.platform import new_id, utcnow


class PayoutChangeRequest(Base):
    __tablename__ = "payout_change_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    old_iban: Mapped[str | None] = mapped_column(String(34), nullable=True)
    new_iban: Mapped[str] = mapped_column(String(34))
    requested_by: Mapped[str] = mapped_column(String(36))
    requested_role: Mapped[str] = mapped_column(String(20))
    payee_result: Mapped[str] = mapped_column(String(12))  # match | close_match | no_match
    flags: Mapped[list] = mapped_column(JSON, default=list)
    # held -> confirmed -> applied ; flagged -> (officer) approved -> applied ; rejected / cancelled
    status: Mapped[str] = mapped_column(String(12))
    hold_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
