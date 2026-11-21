"""Regression tests for the case-lifecycle red-team findings (C1, C2, H1, H5, M8, M9) and
Security review H1 (consent on lists) and M4 (four eyes). Each test was red before its fix."""
import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.security import create_access_token
from app.main import create_app
from app.models.audit import AuditEvent
from app.models.consent import Consent
from app.models.document import CaseDocument
from app.models.platform import Case, CaseEvent, Decision, Tenant, User
from tests.conftest import BASE_CLAIM

from tests.helpers import ALL_DOCS, attach_documents, redecide_case  # noqa: F401 (re-exported)
RUKHSANA = {"claimant_cnic": "9000000000033", "claimant_name": "Rukhsana", "claimant_dob": "1975-01-20",
            "payout_iban": "PK00MOCK0000000000000002"}


def staff_headers(db, role: str, phone: str, tenant_slug: str = "pension") -> tuple[dict, str]:
    tenant = db.execute(select(Tenant).where(Tenant.slug == tenant_slug)).scalar_one()
    user = User(tenant_id=tenant.id, role=role, name=f"Second {role}", phone=phone, pin_hash="unused")
    db.add(user)
    db.commit()
    return {"Authorization": f"Bearer {create_access_token(user.id, role, tenant.id)}"}, user.id


# --- C1: parallel identical claims ------------------------------------------------------------

def test_c1_parallel_identical_claims_create_exactly_one_case(login, db):
    headers = login("zainab")
    statuses: list[int] = []

    def file() -> None:
        statuses.append(TestClient(create_app()).post("/api/v1/cases", json=BASE_CLAIM, headers=headers).status_code)

    threads = [threading.Thread(target=file) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    assert sorted(statuses) == [201, 409, 409, 409, 409, 409]
    count = db.execute(select(func.count(Case.id)).where(Case.deceased_cnic == BASE_CLAIM["deceased_cnic"], ~Case.reference.startswith("SP-0"))).scalar()
    assert count == 1


def test_c1_unique_index_refuses_a_second_open_claim_at_the_database(file_claim, db):
    first = db.get(Case, file_claim("zainab")["data"]["id"])
    db.add(Case(reference="SP-DUP1", tenant_id=first.tenant_id, claimant_person_id=first.claimant_person_id, created_by=first.created_by,
                status="submitted", claim=first.claim, deceased_cnic=first.deceased_cnic, payout_iban=first.payout_iban))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# --- C2: ticked checkboxes are not proof ----------------------------------------------------

def test_c2_ticked_documents_without_uploads_are_never_auto_approved(file_claim):
    data = file_claim("zainab")["data"]
    assert data["status"] == "proof_requested"
    assert data["latest_decision"]["route"] == "ASK_PROOF"


def test_c2_analysed_clean_uploads_are_the_proof(file_claim, db):
    case_id = file_claim("zainab")["data"]["id"]
    attach_documents(db, case_id)
    case = redecide_case(db, case_id)
    assert case.status == "auto_approved"
    decision = db.execute(select(Decision).where(Decision.case_id == case_id).order_by(Decision.created_at.desc())).scalars().first()
    assert decision.signals["facts"]["documents"] == sorted(ALL_DOCS)
    assert decision.signals["facts"]["documents_promised"] == sorted(ALL_DOCS)


@pytest.mark.parametrize("risk", ["high", "mismatch"])
def test_c2_flagged_uploads_do_not_count_as_proof(file_claim, db, risk):
    case_id = file_claim("zainab")["data"]["id"]
    attach_documents(db, case_id, risk=risk)
    case = redecide_case(db, case_id)
    assert case.status != "auto_approved"
    decision = db.execute(select(Decision).where(Decision.case_id == case_id).order_by(Decision.created_at.desc())).scalars().first()
    assert decision.signals["facts"]["documents"] == []


# --- H1: re-decisions never undo a human or guardrail hold ---------------------------------

def test_h1_escalated_case_stays_with_a_human_after_any_redecision(file_claim, client, login, db):
    zainab = login("zainab")
    case_id = file_claim("zainab")["data"]["id"]
    escalated = client.post(f"/api/v1/cases/{case_id}/escalate", json={"reason": "my brother-in-law forced me"}, headers=zainab)
    assert escalated.json()["data"]["status"] == "in_review"

    attach_documents(db, case_id)
    case = redecide_case(db, case_id)

    assert case.status == "in_review"
    decision = db.execute(select(Decision).where(Decision.case_id == case_id).order_by(Decision.created_at.desc())).scalars().first()
    assert decision.rule_result["engine_route"] == "AUTO_APPROVE" and decision.rule_result["human_hold"] is True
    assert decision.route == "UNSURE"


def test_h1_assigned_case_is_never_auto_approved_by_redecision(file_claim, client, login, db):
    case_id = file_claim("zainab")["data"]["id"]
    officer_id = db.execute(select(User.id).where(User.phone == "00000000020")).scalar_one()
    assert client.post(f"/api/v1/cases/{case_id}/assign", json={"officer_id": officer_id}, headers=login("officer")).status_code == 200

    attach_documents(db, case_id)
    assert redecide_case(db, case_id).status == "proof_requested"


def test_h1_related_claim_recheck_cannot_release_a_hold(file_claim, client, login, db):
    case_id = file_claim("zainab")["data"]["id"]
    attach_documents(db, case_id)
    client.post(f"/api/v1/cases/{case_id}/escalate", json={"reason": "please check by a person"}, headers=login("zainab"))
    file_claim("rukhsana", **RUKHSANA)  # triggers recheck_related on Zainab's case
    db.expire_all()
    assert db.get(Case, case_id).status == "in_review"


# --- H5 / M8: duplicate holes --------------------------------------------------------------

def test_h5_claim_without_deceased_cnic_blocks_the_same_claim_with_cnic(client, login):
    zainab = login("zainab")
    first = client.post("/api/v1/cases", json={**BASE_CLAIM, "deceased_cnic": None}, headers=zainab)
    assert first.status_code == 201
    second = client.post("/api/v1/cases", json=BASE_CLAIM, headers=zainab)
    assert second.status_code == 409


def test_h5_officer_approval_rechecks_duplicates(file_claim, client, login, db):
    case_id = file_claim("zainab")["data"]["id"]
    first = db.get(Case, case_id)
    twin = Case(reference="SP-TWIN", tenant_id=first.tenant_id, claimant_person_id=first.claimant_person_id, created_by=first.created_by,
                status="in_review", claim={**first.claim, "deceased_cnic": None}, deceased_cnic=None, payout_iban=first.payout_iban)
    db.add(twin)
    db.commit()
    response = client.post(f"/api/v1/cases/{twin.id}/approve", json={"reason": "looks fine"}, headers=login("officer"))
    assert response.status_code == 409


@pytest.mark.parametrize("status", ["approved", "auto_approved"])
def test_m8_officer_cannot_close_an_approved_case(file_claim, client, login, db, status):
    case_id = file_claim("zainab")["data"]["id"]
    db.get(Case, case_id).status = status
    db.commit()
    response = client.post(f"/api/v1/cases/{case_id}/close", json={"reason": "closing"}, headers=login("officer"))
    assert response.status_code == 409
    db.expire_all()
    assert db.get(Case, case_id).status == status


def test_m8_a_claim_closed_after_approval_still_blocks_a_refile(file_claim, client, login, db):
    case = db.get(Case, file_claim("zainab")["data"]["id"])
    db.add(CaseEvent(case_id=case.id, kind="approved", actor_id=None, note="legacy"))
    case.status = "closed"  # e.g. closed before this fix
    db.commit()
    assert client.post("/api/v1/cases", json=BASE_CLAIM, headers=login("zainab")).status_code == 409


# --- M9: another department's cases are a signal only --------------------------------------

def test_m9_new_claim_never_redecides_or_reveals_another_departments_case(file_claim, db):
    welfare = db.execute(select(Tenant).where(Tenant.slug == "welfare")).scalar_one()
    rukhsana_case = db.get(Case, file_claim("rukhsana", **RUKHSANA)["data"]["id"])
    rukhsana_case.tenant_id = welfare.id  # the competing claim lives in another department
    db.commit()
    decisions_before = db.execute(select(func.count(Decision.id)).where(Decision.case_id == rukhsana_case.id)).scalar()

    body = file_claim("zainab")

    assert body["meta"] == {"rechecked_count": 0}
    assert db.execute(select(func.count(Decision.id)).where(Decision.case_id == rukhsana_case.id)).scalar() == decisions_before
    decision = db.execute(select(Decision).where(Decision.case_id == body["data"]["id"])).scalars().first()
    assert decision.signals["duplicate_claims"] == [{"case": "other-department", "claimant_cnic_last4": "0033"}]
    assert body["data"]["status"] == "in_review"


# --- Security review H1: consent on list endpoints -----------------------------------------

def _withdraw_department_consent(db, case_id: str) -> None:
    person_id = db.get(Case, case_id).claimant_person_id
    for consent in db.execute(select(Consent).where(Consent.subject_person_id == person_id, Consent.grantee_type == "department")).scalars():
        consent.status = "withdrawn"
    db.commit()


@pytest.mark.parametrize("path", ["/api/v1/cases", "/api/v1/queue"])
def test_security_h1_lists_redact_cases_after_consent_withdrawal(file_claim, client, login, db, path):
    body = file_claim("zainab")["data"]
    _withdraw_department_consent(db, body["id"])
    denied_before = db.execute(select(func.count(AuditEvent.seq)).where(AuditEvent.action == "CONSENT_DENIED")).scalar()

    rows = client.get(path, headers=login("officer")).json()["data"]

    row = next(r for r in rows if r["reference"] == body["reference"])
    assert row == {"reference": body["reference"], "status": body["status"], "consent_active": False}
    assert "deceased_cnic" not in row
    assert db.execute(select(func.count(AuditEvent.seq)).where(AuditEvent.action == "CONSENT_DENIED")).scalar() == denied_before + 1


def test_security_h1_list_with_consent_shows_full_rows_and_logs_access(file_claim, client, login, db):
    body = file_claim("zainab")["data"]
    rows = client.get("/api/v1/cases", headers=login("officer")).json()["data"]
    row = next(r for r in rows if r["reference"] == body["reference"])
    assert row["deceased_cnic"] == BASE_CLAIM["deceased_cnic"]
    assert db.execute(select(func.count(AuditEvent.seq)).where(AuditEvent.action == "DATA_ACCESS",
                                                               AuditEvent.resource == f"person:{body['claimant_person_id']}")).scalar() >= 1


# --- Security review M4: four eyes ---------------------------------------------------------

def test_m4_high_risk_case_needs_two_different_officers(file_claim, client, login, db):
    case = file_claim("rukhsana", **RUKHSANA)["data"]
    assert "NOT_IN_FAMILY_RECORD" in case["latest_decision"]["reason_codes"]
    first_officer = login("officer")
    second_officer, _ = staff_headers(db, "officer", "00000000091")
    url = f"/api/v1/cases/{case['id']}/approve"

    first = client.post(url, json={"reason": "checked papers"}, headers=first_officer)
    assert first.status_code == 200 and first.json()["data"]["status"] == "in_review"
    assert client.post(url, json={"reason": "again me"}, headers=first_officer).status_code == 409
    second = client.post(url, json={"reason": "second check"}, headers=second_officer)
    assert second.status_code == 200 and second.json()["data"]["status"] == "approved"


def test_m4_officer_cannot_approve_a_case_they_filed(file_claim, client, login, db):
    headers, officer_id = staff_headers(db, "officer", "00000000092")
    case_id = file_claim("zainab")["data"]["id"]
    db.get(Case, case_id).created_by = officer_id
    db.commit()
    assert client.post(f"/api/v1/cases/{case_id}/approve", json={"reason": "my own"}, headers=headers).status_code == 403
