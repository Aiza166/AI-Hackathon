"""Server-side duplicate protection for POST /api/v1/cases.

Weak connections retry. The same Idempotency-Key must never file a second claim,
and leaving the deceased CNIC blank must not get around the duplicate check.
"""
from sqlalchemy import func, select

from app.models.platform import Case
from tests.conftest import BASE_CLAIM

RUKHSANA_CLAIM = {**BASE_CLAIM, "claimant_cnic": "9000000000033", "claimant_name": "Rukhsana", "payout_iban": "PK00MOCK0000000000000002"}


def _cases(db) -> int:
    db.rollback()  # fresh snapshot
    return db.execute(select(func.count(Case.id))).scalar_one()


def test_same_key_and_body_replays_first_response_and_files_one_case(client, login, db):
    before = _cases(db)
    headers = {**login("zainab"), "Idempotency-Key": "outbox-row-1"}

    first = client.post("/api/v1/cases", json=BASE_CLAIM, headers=headers)
    second = client.post("/api/v1/cases", json=BASE_CLAIM, headers=headers)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert second.json()["data"]["id"] == first.json()["data"]["id"]
    assert second.json()["data"]["reference"] == first.json()["data"]["reference"]
    assert second.json()["meta"]["idempotent_replay"] is True
    assert "idempotent_replay" not in first.json()["meta"]
    assert _cases(db) == before + 1


def test_same_key_with_different_body_is_refused(client, login, db):
    before = _cases(db)
    headers = {**login("zainab"), "Idempotency-Key": "outbox-row-2"}
    assert client.post("/api/v1/cases", json=BASE_CLAIM, headers=headers).status_code == 201

    changed = client.post("/api/v1/cases", json={**BASE_CLAIM, "deceased_name": "Someone Else"}, headers=headers)

    assert changed.status_code == 422
    assert changed.json()["success"] is False
    assert _cases(db) == before + 1


def test_keys_are_scoped_per_principal(client, login, db):
    before = _cases(db)
    key = {"Idempotency-Key": "shared-key"}
    zainab = client.post("/api/v1/cases", json=BASE_CLAIM, headers={**login("zainab"), **key})
    rukhsana = client.post("/api/v1/cases", json=RUKHSANA_CLAIM, headers={**login("rukhsana"), **key})

    assert zainab.status_code == 201, zainab.text
    assert rukhsana.status_code == 201, rukhsana.text
    assert rukhsana.json()["data"]["id"] != zainab.json()["data"]["id"]
    assert "idempotent_replay" not in rukhsana.json()["meta"]
    assert _cases(db) == before + 2


def test_failed_request_releases_the_key_for_a_retry(client, login, db):
    before = _cases(db)
    headers = {**login("zainab"), "Idempotency-Key": "outbox-row-3"}
    someone_else = {**BASE_CLAIM, "claimant_cnic": "9000000000033"}  # not Zainab: refused with 403
    assert client.post("/api/v1/cases", json=someone_else, headers=headers).status_code == 403

    retry = client.post("/api/v1/cases", json=someone_else, headers=headers)

    assert retry.status_code == 403  # processed again, not "in flight" or a replay
    assert _cases(db) == before


def test_blank_key_is_rejected(client, login):
    response = client.post("/api/v1/cases", json=BASE_CLAIM, headers={**login("zainab"), "Idempotency-Key": "   "})
    assert response.status_code == 400


def test_second_open_claim_without_deceased_cnic_is_refused(client, login, db):
    before = _cases(db)
    no_cnic = {**BASE_CLAIM, "deceased_cnic": None}
    first = client.post("/api/v1/cases", json=no_cnic, headers=login("zainab"))
    assert first.status_code == 201, first.text

    # Same person written differently: honorific and spelling variant.
    again = client.post("/api/v1/cases", json={**no_cnic, "deceased_name": "Haji Mohd. Aslam"}, headers=login("zainab"))

    assert again.status_code == 409
    assert first.json()["data"]["reference"] in again.json()["error"]["message"]
    assert _cases(db) == before + 1


def test_claim_for_a_different_deceased_without_cnic_is_allowed(client, login, db):
    before = _cases(db)
    no_cnic = {**BASE_CLAIM, "deceased_cnic": None}
    assert client.post("/api/v1/cases", json=no_cnic, headers=login("zainab")).status_code == 201

    other = client.post("/api/v1/cases", json={**no_cnic, "deceased_name": "Ghulam Rasool"}, headers=login("zainab"))

    assert other.status_code == 201, other.text
    assert _cases(db) == before + 2
