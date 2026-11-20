"""Consent records (modelled on India's Account Aggregator consent artefact) and
correction requests. A citizen can see, change, withdraw and correct."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.platform import new_id, utcnow

CONSENT_FIELDS = ("cnic", "family_record", "death_certificate", "payout_account", "case_details")


class Consent(Base):
    __tablename__ = "consents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subject_person_id: Mapped[str] = mapped_column(ForeignKey("persons.id"), index=True)
    grantee_type: Mapped[str] = mapped_column(String(20))  # helper | department
    grantee_id: Mapped[str] = mapped_column(String(36), index=True)  # helper user id, or tenant id
    purpose: Mapped[str] = mapped_column(String(80))
    fields: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(12), default="active")  # active | withdrawn
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CorrectionRequest(Base):
    __tablename__ = "correction_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    field: Mapped[str] = mapped_column(String(40))
    current_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_value: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending | approved | rejected
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
