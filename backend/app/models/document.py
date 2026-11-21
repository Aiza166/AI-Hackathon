"""Uploaded case documents: the analysis result plus a downsized copy for the officer.

Stored per case (case_id, tenant_id) in the database, never on shared disk. Kept: the
SHA-256 of the upload, the fields read, the registry checks, forensic and Jev results,
a JPEG copy at most 1568 px (what the officer needs to look at) and the ELA heatmap.
Not kept: the original file and the raw OCR text.
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.db import Base
from app.models.platform import new_id, utcnow


class CaseDocument(Base):
    __tablename__ = "case_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    sha256: Mapped[str] = mapped_column(String(64))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    ocr_engine: Mapped[str | None] = mapped_column(String(40), nullable=True)
    jev_model: Mapped[str | None] = mapped_column(String(40), nullable=True)
    risk_level: Mapped[str] = mapped_column(String(10))  # low | confirm | mismatch | high
    indicator_codes: Mapped[list] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)  # quality, fields, checks, forensics, jev, indicators
    confirmed_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    image_jpeg: Mapped[bytes] = deferred(mapped_column(LargeBinary))
    ela_jpeg: Mapped[bytes] = deferred(mapped_column(LargeBinary))
    uploaded_by: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
