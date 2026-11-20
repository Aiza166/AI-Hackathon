"""Platform tables: tenants, users, cases, decisions, rules, API keys."""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)


class Person(Base):
    """A citizen known to the platform (identity is verified against the mock registry)."""

    __tablename__ = "persons"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    cnic: Mapped[str] = mapped_column(String(13), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    role: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    pin_hash: Mapped[str] = mapped_column(String(100))
    person_id: Mapped[str | None] = mapped_column(ForeignKey("persons.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class HelperAssignment(Base):
    __tablename__ = "helper_assignments"
    __table_args__ = (UniqueConstraint("helper_user_id", "person_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    helper_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id"))


class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    name: Mapped[str] = mapped_column(String(80))
    key_prefix: Mapped[str] = mapped_column(String(12))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RuleVersion(Base):
    __tablename__ = "rule_versions"
    __table_args__ = (UniqueConstraint("ruleset", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ruleset: Mapped[str] = mapped_column(String(60))
    version: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(200))
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    rules: Mapped[dict] = mapped_column(JSON)
    thresholds: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(10))  # draft | live | retired
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    reference: Mapped[str] = mapped_column(String(20), unique=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    case_type: Mapped[str] = mapped_column(String(30), default="survivor_pension")
    claimant_person_id: Mapped[str] = mapped_column(ForeignKey("persons.id"))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20))
    priority: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    assigned_officer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    claim: Mapped[dict] = mapped_column(JSON)  # what the claimant submitted (validated by Pydantic)
    deceased_cnic: Mapped[str | None] = mapped_column(String(13), nullable=True, index=True)
    payout_iban: Mapped[str | None] = mapped_column(String(34), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CaseEvent(Base):
    __tablename__ = "case_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    rule_version_id: Mapped[str] = mapped_column(ForeignKey("rule_versions.id"))
    model_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    input_hash: Mapped[str] = mapped_column(String(64))
    signals: Mapped[dict] = mapped_column(JSON)
    rule_result: Mapped[dict] = mapped_column(JSON)
    jev_raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float] = mapped_column(Float)
    thresholds: Mapped[dict] = mapped_column(JSON)
    route: Mapped[str] = mapped_column(String(20))
    reason_codes: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
