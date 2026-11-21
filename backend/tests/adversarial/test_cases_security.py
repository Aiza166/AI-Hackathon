"""Regression tests for the case-lifecycle red-team findings (C1, H1, H5).
Each test was red before its fix."""
import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.main import create_app
from app.models.platform import Case, Decision, User
from tests.conftest import BASE_CLAIM
from tests.helpers import attach_documents, redecide_case

RUKHSANA = {"claimant_cnic": "9000000000033", "claimant_name": "Rukhsana", "claimant_dob": "1975-01-20",
            "payout_iban": "PK00MOCK0000000000000002"}


def _latest(db, case_id: str) -> Decision:
    return db.execute(select(Decision).where(Decision.case_id == case_id).order_by(Decision.created_at.desc())).scalars().first()


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
    zainab_id = db.execute(select(User.person_id).where(User.phone == "00000000001")).scalar()
    count = db.execute(select(func.count(Case.id)).where(Case.deceased_cnic == BASE_CLAIM["deceased_cnic"],
                                                         Case.claimant_person_id == zainab_id,
                                                         Case.status.not_in(("approved",)))).scalar()
    assert count == 1


def test_c1_unique_index_refuses_a_second_open_claim_at_the_database(file_claim, db):
    first = db.get(Case, file_claim("zainab")["data"]["id"])
    db.add(Case(reference="SP-DUP1", tenant_id=first.tenant_id, claimant_person_id=first.claimant_person_id, created_by=first.created_by,
                status="submitted", claim=first.claim, deceased_cnic=first.deceased_cnic, payout_iban=first.payout_iban))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# --- H1: re-decisions never undo a human or guardrail hold ---------------------------------

def test_h1_escalated_case_stays_with_a_human_after_any_redecision(file_claim, client, login, db):
    zainab = login("zainab")
    case_id = file_claim("zainab")["data"]["id"]
    escalated = client.post(f"/api/v1/cases/{case_id}/escalate", json={"reason": "my brother-in-law forced me"}, headers=zainab)
    assert escalated.json()["data"]["status"] == "in_review"

    attach_documents(db, case_id)
    case = redecide_case(db, case_id)

    assert case.status == "in_review"
    decision = _latest(db, case_id)
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
    client.post(f"/api/v1/cases/{case_id}/escalate", json={"reason": "please check by a person"}, headers=login("zainab"))
    file_claim("rukhsana", **RUKHSANA)  # triggers recheck_related on Zainab's case
    db.expire_all()
    assert db.get(Case, case_id).status == "in_review"


def test_h1_unheld_case_is_still_redecided_freely(file_claim, db):
    case_id = file_claim("zainab")["data"]["id"]
    assert redecide_case(db, case_id).status == "auto_approved"
    assert _latest(db, case_id).rule_result["human_hold"] is False


# --- H5: duplicate holes -------------------------------------------------------------------

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
