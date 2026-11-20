"""Demo world: invented people, records and accounts. Run: python -m app.seed

Everything here is fake. CNICs start with 90000 and IBANs with PK00MOCK so they
cannot be confused with real ones. Names in the registry are spelled
differently on purpose (Muhammad / Mohd. / Muhammed) to test matching.
"""
import json
from datetime import date
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import audit
from app.core.security import hash_pin
from app.db import SessionLocal
from app.models.mock import MockAccount, MockDeath, MockFamilyLink, MockFamilyPensionDrawn, MockPension, MockPerson
from app.models.platform import HelperAssignment, Person, RuleVersion, Tenant, User, utcnow

DEMO_PIN = "1234"
RULESET_DIR = Path(__file__).parent / "decision" / "rulesets"
RESET_TABLES = (
    "decisions", "case_events", "cases", "api_keys", "helper_assignments", "users", "persons", "rule_versions", "tenants",
    "mock_accounts", "mock_family_pensions_drawn", "mock_pensions", "mock_deaths", "mock_family_links", "mock_persons", "mock_faults",
)

# cnic, name, father/husband, dob, gender, district, marital, disabled
PEOPLE = [
    ("9000000000011", "Muhammad Aslam", "Ghulam Nabi", date(1955, 3, 10), "M", "Karachi East", "married", False),
    ("9000000000022", "Zainab Bibi", "Ghulam Rasool", date(1962, 6, 1), "F", "Karachi East", "widowed", False),
    ("9000000000023", "Imran Aslam", "Muhammad Aslam", date(1986, 2, 14), "M", "Karachi East", "married", False),
    ("9000000000024", "Nadia Aslam", "Muhammad Aslam", date(1989, 9, 30), "F", "Karachi East", "married", False),
    ("9000000000033", "Rukhsana", "Abdul Majeed", date(1975, 1, 20), "F", "Hyderabad", "widowed", False),
    ("9000000000044", "Muhammad Aslam", "Fazal Din", date(1955, 9, 2), "M", "Lahore", "married", False),
    ("9000000000055", "Abdul Rauf", "Noor Muhammad", date(1958, 11, 5), "M", "Sukkur", "married", False),
    ("9000000000056", "Saima", "Abdul Rauf", None, "F", "Sukkur", "widowed", False),
    ("9000000000057", "Nasreen", "Abdul Rauf", date(1966, 4, 18), "F", "Sukkur", "widowed", False),
    ("9000000000066", "Ghulam Haider", "Allah Ditta", date(1950, 7, 7), "M", "Multan", "married", False),
    ("9000000000067", "Shamim Akhtar", "Ghulam Haider", date(1957, 3, 3), "F", "Multan", "widowed", False),
    ("9000000000068", "Bilal Haider", "Ghulam Haider", date(2006, 5, 1), "M", "Multan", "unmarried", False),
    ("9000000000069", "Hina Haider", "Ghulam Haider", date(1991, 12, 12), "F", "Multan", "divorced", False),
    ("9000000000077", "Rafiq Ahmed", "Bashir Ahmed", date(1980, 8, 8), "M", "Karachi South", "married", False),
    ("9000000000088", "Kausar Parveen", "Tariq Mehmood", date(1968, 10, 10), "F", "Quetta", "widowed", False),
    ("9000000000089", "Tariq Mehmood", "Sher Khan", date(1960, 1, 1), "M", "Quetta", "married", False),
]
FAMILIES = [  # frc, head, member, relation
    ("FRC-1001", "9000000000011", "9000000000022", "wife"),
    ("FRC-1001", "9000000000011", "9000000000023", "son"),
    ("FRC-1001", "9000000000011", "9000000000024", "daughter"),
    ("FRC-1002", "9000000000055", "9000000000056", "wife"),
    ("FRC-1002", "9000000000055", "9000000000057", "wife"),
    ("FRC-1003", "9000000000066", "9000000000067", "wife"),
    ("FRC-1003", "9000000000066", "9000000000068", "son"),
    ("FRC-1003", "9000000000066", "9000000000069", "daughter"),
    ("FRC-1004", "9000000000089", "9000000000088", "wife"),
]
DEATHS = [  # cnic, name on certificate (spelled differently on purpose), date, cert no, union council
    ("9000000000011", "Mohd. Aslam", date(2026, 8, 14), "DC-UC12-2026-0412", "UC-12 Gulshan (mock)"),
    ("9000000000055", "Abdul Rauf", date(2026, 7, 1), "DC-UC03-2026-0099", "UC-3 Sukkur (mock)"),
    ("9000000000066", "Ghulam Haider", date(2010, 2, 2), "DC-UC07-2010-0031", "UC-7 Multan (mock)"),
    ("9000000000067", "Shamim Akhtar", date(2024, 11, 1), "DC-UC07-2024-0777", "UC-7 Multan (mock)"),
    ("9000000000089", "Tariq Mehmood", date(2019, 5, 5), "DC-UC01-2019-0123", "UC-1 Quetta (mock)"),
]
PENSIONS = [  # cnic, name in pension office, invented monthly amount, status
    ("9000000000011", "Muhammed Aslam", 32000, "active"),
    ("9000000000055", "Abdul Rauf", 28000, "active"),
    ("9000000000066", "Ghulam Haider", 21000, "active"),
    ("9000000000089", "Tariq Mehmood", 25000, "active"),
]
ACCOUNTS = [  # iban, title, owner, bank
    ("PK00MOCK0000000000000001", "ZAINAB BIBI", "9000000000022", "Mock Bank"),
    ("PK00MOCK0000000000000002", "RUKHSANA", "9000000000033", "Mock Bank"),
    ("PK00MOCK0000000000000003", "SAIMA", "9000000000056", "Mock Bank"),
    ("PK00MOCK0000000000000004", "NASREEN", "9000000000057", "Mock Bank"),
    ("PK00MOCK0000000000000005", "BILAL HAIDER", "9000000000068", "Mock Bank"),
    ("PK00MOCK0000000000000006", "HINA HAIDER", "9000000000069", "Mock Bank"),
    ("PK00MOCK0000000000000007", "ZAINAB B", "9000000000022", "Mock Bank"),
    ("PK00MOCK0000000000000008", "KHALID TRADERS", "9000000000077", "Mock Bank"),
    ("PK00MOCK0000000000000009", "KAUSAR PARVEEN", "9000000000088", "Mock Bank"),
]
CITIZENS = [  # phone, person cnic
    ("00000000001", "9000000000022"),
    ("00000000002", "9000000000033"),
    ("00000000003", "9000000000056"),
    ("00000000004", "9000000000057"),
    ("00000000005", "9000000000068"),
    ("00000000006", "9000000000069"),
    ("00000000007", "9000000000077"),
    ("00000000008", "9000000000088"),
]
STAFF = [  # phone, name, role, tenant slug
    ("00000000010", "Ayesha (helper)", "helper", "pension"),
    ("00000000020", "Kamran (officer)", "officer", "pension"),
    ("00000000021", "Sana (officer)", "officer", "pension"),
    ("00000000030", "Admin", "admin", "pension"),
    ("00000000040", "Auditor", "auditor", "pension"),
    ("00000000050", "Farah (welfare officer)", "officer", "welfare"),
]
HELPER_FAMILY_NAMES = [
    "Parveen Akhtar", "Shabana Bibi", "Nusrat Jahan", "Rubina Kausar", "Shahida Begum", "Nasim Akhtar", "Rehana Bibi",
    "Fozia Naz", "Kaneez Fatima", "Sughra Bibi", "Bushra Bibi", "Tahira Yasmin", "Samina Kausar", "Gulnaz Bibi",
    "Razia Sultana", "Amna Bibi", "Hajra Bibi", "Zubaida Khatoon", "Naseem Bano", "Sakina Bibi", "Mumtaz Begum",
    "Jamila Bibi", "Rashida Parveen", "Kishwar Sultana", "Asma Bibi", "Farzana Kausar", "Musarrat Bibi", "Yasmin Akhtar",
    "Sadia Bibi", "Naheed Akhtar", "Tasleem Bibi", "Irshad Begum", "Shamshad Bibi", "Robina Bibi", "Saeeda Bibi",
    "Shaheen Akhtar", "Iqbal Begum", "Nargis Bibi", "Mehrunnisa",
]


def _reset_tables(db: Session) -> None:
    db.execute(text(f"TRUNCATE {', '.join(RESET_TABLES)} RESTART IDENTITY CASCADE"))


def _seed_registry(db: Session) -> None:
    for cnic, name, rel_name, dob, gender, district, marital, disabled in PEOPLE:
        db.add(MockPerson(cnic=cnic, full_name=name, father_or_husband_name=rel_name, dob=dob, gender=gender,
                          district=district, marital_status=marital, disabled=disabled))
    for frc, head, member, relation in FAMILIES:
        db.add(MockFamilyLink(frc_number=frc, head_cnic=head, member_cnic=member, relation=relation))
    for cnic, name, when, cert, uc in DEATHS:
        db.add(MockDeath(cnic=cnic, name_on_certificate=name, date_of_death=when, certificate_no=cert, union_council=uc))
    for cnic, name, amount, status in PENSIONS:
        db.add(MockPension(pensioner_cnic=cnic, name_in_pension_office=name, monthly_amount=amount, status=status))
    db.add(MockFamilyPensionDrawn(cnic="9000000000088", since=date(2019, 6, 1)))
    for iban, title, owner, bank in ACCOUNTS:
        db.add(MockAccount(iban=iban, title=title, owner_cnic=owner, bank=bank))


def _seed_rules(db: Session) -> None:
    for version, status in ((1, "live"), (2, "draft")):
        data = json.loads((RULESET_DIR / f"survivor_pension_v{version}.json").read_text(encoding="utf-8"))
        db.add(RuleVersion(
            ruleset=data["ruleset"], version=version, label=data["label"],
            effective_from=date.fromisoformat(data["effective_from"]),
            rules=data["rules"], thresholds=data["thresholds"], status=status,
            published_at=utcnow() if status == "live" else None,
        ))


def _seed_users(db: Session) -> None:
    tenants = {"pension": Tenant(name="Pension Department (mock)", slug="pension"),
               "welfare": Tenant(name="Social Welfare Department (mock)", slug="welfare")}
    db.add_all(tenants.values())
    db.flush()
    pin = hash_pin(DEMO_PIN)
    names = {p[0]: p[1] for p in PEOPLE}
    persons = {}
    for phone, cnic in CITIZENS:
        persons[cnic] = Person(cnic=cnic, display_name=names[cnic])
        db.add(persons[cnic])
        db.flush()
        db.add(User(tenant_id=tenants["pension"].id, role="citizen", name=names[cnic], phone=phone, pin_hash=pin, person_id=persons[cnic].id))
    staff = {}
    for phone, name, role, slug in STAFF:
        staff[phone] = User(tenant_id=tenants[slug].id, role=role, name=name, phone=phone, pin_hash=pin)
        db.add(staff[phone])
    db.flush()
    helper = staff["00000000010"]
    db.add(HelperAssignment(helper_user_id=helper.id, person_id=persons["9000000000022"].id))
    for i, name in enumerate(HELPER_FAMILY_NAMES, start=1):  # 39 more families: 40 in total for one helper
        person = Person(cnic=f"90000{9000 + i:08d}", display_name=name)
        db.add(person)
        db.flush()
        db.add(HelperAssignment(helper_user_id=helper.id, person_id=person.id))


def reset(db: Session) -> None:
    """Wipe demo data and load the seed. The audit log is never wiped: the reset itself is logged."""
    _reset_tables(db)
    _seed_registry(db)
    _seed_rules(db)
    _seed_users(db)
    db.flush()
    audit.record(db, audit.SYSTEM, "DEMO_RESET", details={"seed": "phase1"})
    db.commit()


if __name__ == "__main__":
    with SessionLocal() as session:
        reset(session)
    print("Seeded demo data. All PINs:", DEMO_PIN)
