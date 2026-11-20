"""Mock government and payment registries (all data is invented).

These stand in for NADRA-like identity and family records, the death registry,
the pension office and Raast-like account title lookup. They sit behind clean
service functions so they could be swapped for real APIs.
"""
from datetime import date

from sqlalchemy import Boolean, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.platform import new_id


class MockPerson(Base):
    __tablename__ = "mock_persons"
    cnic: Mapped[str] = mapped_column(String(13), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    father_or_husband_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dob: Mapped[date | None] = mapped_column(Date, nullable=True)  # missing on purpose for some
    gender: Mapped[str] = mapped_column(String(1))
    district: Mapped[str] = mapped_column(String(60))
    marital_status: Mapped[str] = mapped_column(String(20), default="married")
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)


class MockFamilyLink(Base):
    """One row per member of a family registration certificate (FRC)."""

    __tablename__ = "mock_family_links"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    frc_number: Mapped[str] = mapped_column(String(20), index=True)
    head_cnic: Mapped[str] = mapped_column(String(13), index=True)
    member_cnic: Mapped[str] = mapped_column(String(13), index=True)
    relation: Mapped[str] = mapped_column(String(20))  # head | wife | son | daughter


class MockDeath(Base):
    __tablename__ = "mock_deaths"
    cnic: Mapped[str] = mapped_column(String(13), primary_key=True)
    name_on_certificate: Mapped[str] = mapped_column(String(120))
    date_of_death: Mapped[date] = mapped_column(Date)
    certificate_no: Mapped[str] = mapped_column(String(30))
    union_council: Mapped[str] = mapped_column(String(80))


class MockPension(Base):
    __tablename__ = "mock_pensions"
    pensioner_cnic: Mapped[str] = mapped_column(String(13), primary_key=True)
    name_in_pension_office: Mapped[str] = mapped_column(String(120))
    monthly_amount: Mapped[int] = mapped_column(Integer)  # invented amounts, labelled as mock
    status: Mapped[str] = mapped_column(String(20))  # active | stopped


class MockFamilyPensionDrawn(Base):
    """People already drawing a family pension (for rule R6: single pension)."""

    __tablename__ = "mock_family_pensions_drawn"
    cnic: Mapped[str] = mapped_column(String(13), primary_key=True)
    since: Mapped[date] = mapped_column(Date)


class MockAccount(Base):
    __tablename__ = "mock_accounts"
    iban: Mapped[str] = mapped_column(String(34), primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    owner_cnic: Mapped[str] = mapped_column(String(13))
    bank: Mapped[str] = mapped_column(String(60))


class MockFault(Base):
    """Failure injection for the judge console: per-service error or delay."""

    __tablename__ = "mock_faults"
    service: Mapped[str] = mapped_column(String(30), primary_key=True)
    mode: Mapped[str] = mapped_column(String(10), default="ok")  # ok | error | slow
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
