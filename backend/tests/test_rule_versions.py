"""Rules that change (Challenge 4) and the Digital Twin (bonus)."""
from sqlalchemy import func, select

from app.models.audit import AuditEvent
from app.models.platform import Decision


def _versions(client, headers) -> dict:
    return {r["version"]: r for r in client.get("/api/v1/admin/rules", headers=headers).json()["data"]}


def test_digital_twin_shows_only_post_2024_heirs_change_and_writes_nothing(client, login, db):
    admin = login("admin")
    v2 = _versions(client, admin)[2]
    before = db.execute(select(func.count(Decision.id))).scalar()

    sim = client.post(f"/api/v1/rules/{v2['id']}/simulate", headers=admin).json()["data"]

    assert (sim["checked"], sim["changed"]) == (4, 2)
    changed = {row["case"]: row["after"]["entitlement_end"] for row in sim["cases"] if row["changed"]}
    assert changed == {"SP-0001": "2034-11-01", "SP-0002": "2034-11-01"}
    assert db.execute(select(func.count(Decision.id))).scalar() == before


def _publish_v2(client, admin) -> None:
    v2 = _versions(client, admin)[2]
    assert client.post(f"/api/v1/rules/{v2['id']}/publish", headers=admin).status_code == 200


def _case_versions(client, login) -> dict:
    rows = client.get("/api/v1/cases", headers=login("officer")).json()["data"]
    return {c["reference"]: (c["status"], c["latest_decision"]["rule_version"]) for c in rows if c["reference"].startswith("SP-0")}


def test_seed_haider_heirs_wait_for_an_officer_and_rakha_heirs_are_decided(client, login):
    versions = _case_versions(client, login)
    assert versions == {"SP-0001": ("in_review", 1), "SP-0002": ("in_review", 1),
                        "SP-0003": ("approved", 1), "SP-0004": ("approved", 1)}


def test_publishing_v2_applies_to_new_claims_and_decided_cases_keep_v1(client, login, file_claim):
    admin = login("admin")
    _publish_v2(client, admin)

    after = _versions(client, admin)
    assert (after[1]["status"], after[2]["status"]) == ("retired", "live")
    new_case = file_claim("zainab")["data"]
    assert new_case["latest_decision"]["rule_version"] == 2
    versions = _case_versions(client, login)
    assert versions["SP-0003"] == ("approved", 1)  # Rakha heirs: entitled in 2019, already decided
    assert versions["SP-0004"] == ("approved", 1)


def test_publishing_v2_redecides_pending_heir_cases_entitled_after_its_effective_date(client, login, db):
    start = db.execute(select(func.max(AuditEvent.seq))).scalar() or 0  # the audit log survives resets
    _publish_v2(client, login("admin"))

    versions = _case_versions(client, login)
    assert versions["SP-0001"] == ("in_review", 2)  # still with the officer, now decided under v2
    assert versions["SP-0002"] == ("in_review", 2)
    bilal = login("bilal")
    case = client.get("/api/v1/cases", headers=bilal).json()["data"][0]
    explanation = client.get(f"/api/v1/cases/{case['id']}/explanation", headers=bilal).json()["data"]
    assert explanation["entitlement_end"] == "2034-11-01"
    redecided = db.execute(select(AuditEvent).where(AuditEvent.action == "CASE_REDECIDED", AuditEvent.seq > start)).scalars().all()
    assert sorted(e.resource for e in redecided) == ["case:SP-0001", "case:SP-0002"]
    assert {e.details["from_version"] for e in redecided} == {1}
    assert {e.details["to_version"] for e in redecided} == {2}
    published = db.execute(select(AuditEvent).where(AuditEvent.action == "RULES_PUBLISHED", AuditEvent.seq > start)).scalar_one()
    assert published.details["redecided_cases"] == ["SP-0001", "SP-0002"]


def test_publishing_never_touches_a_case_an_officer_already_decided(client, login):
    officer = login("officer")
    sp1 = next(c for c in client.get("/api/v1/cases", headers=officer).json()["data"] if c["reference"] == "SP-0001")
    assert client.post(f"/api/v1/cases/{sp1['id']}/approve", json={"reason": "Checked in person (mock)"}, headers=officer).status_code == 200

    _publish_v2(client, login("admin"))

    versions = _case_versions(client, login)
    assert versions["SP-0001"] == ("approved", 1)
    assert versions["SP-0002"] == ("in_review", 2)


def test_digital_twin_marks_which_cases_publish_will_redecide(client, login):
    admin = login("admin")
    v2 = _versions(client, admin)[2]
    sim = client.post(f"/api/v1/rules/{v2['id']}/simulate", headers=admin).json()["data"]
    applies = {row["case"]: row["applies_on_publish"] for row in sim["cases"]}
    assert applies == {"SP-0001": True, "SP-0002": True, "SP-0003": False, "SP-0004": False}
    assert sim["will_redecide"] == 2


def test_publishing_twice_is_refused(client, login):
    admin = login("admin")
    v2 = _versions(client, admin)[2]
    client.post(f"/api/v1/rules/{v2['id']}/publish", headers=admin)
    assert client.post(f"/api/v1/rules/{v2['id']}/publish", headers=admin).status_code == 409


def test_malformed_draft_is_rejected(client, login):
    bad = {"label": "broken", "rules": [{"id": "X", "require": [{"fact": "age", "op": "approximately"}], "on_fail": "not_eligible", "reason": "R"}],
           "thresholds": {"t_auto": 0.95, "t_human": 0.7}}
    assert client.post("/api/v1/rules/drafts", json=bad, headers=login("admin")).status_code == 422
    bad_thresholds = {**bad, "rules": [{"id": "Y", "require": [], "on_fail": "not_eligible", "reason": "R"}], "thresholds": {"t_auto": 0.5, "t_human": 0.9}}
    assert client.post("/api/v1/rules/drafts", json=bad_thresholds, headers=login("admin")).status_code == 422


def test_valid_draft_gets_the_next_version_number(client, login):
    admin = login("admin")
    v1 = _versions(client, admin)[1]
    body = {"label": "v3 test", "rules": v1["rules"], "thresholds": v1["thresholds"]}
    created = client.post("/api/v1/rules/drafts", json=body, headers=admin)
    assert created.status_code == 201
    assert created.json()["data"]["version"] == 3


def test_only_admins_can_simulate_or_publish(client, login):
    v2 = _versions(client, login("admin"))[2]
    for who in ("officer", "auditor", "zainab"):
        assert client.post(f"/api/v1/rules/{v2['id']}/publish", headers=login(who)).status_code == 403
