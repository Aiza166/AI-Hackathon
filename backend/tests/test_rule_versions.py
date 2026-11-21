"""Rules that change (Challenge 4) and the Digital Twin (bonus)."""
from sqlalchemy import func, select

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


def test_publishing_v2_applies_to_new_claims_and_old_decisions_keep_v1(client, login, file_claim, db):
    admin = login("admin")
    versions = _versions(client, admin)
    # Red-team H6: a publish needs a Digital Twin run and a second admin's approval.
    from tests.adversarial.test_cases_rules import second_admin
    client.post(f"/api/v1/rules/{versions[2]['id']}/simulate", headers=admin)
    client.post(f"/api/v1/rules/{versions[2]['id']}/approve", headers=second_admin(db))
    assert client.post(f"/api/v1/rules/{versions[2]['id']}/publish", headers=admin).status_code == 200

    after = _versions(client, admin)
    assert (after[1]["status"], after[2]["status"]) == ("retired", "live")
    new_case = file_claim("zainab")["data"]
    assert new_case["latest_decision"]["rule_version"] == 2
    old = client.get("/api/v1/cases", headers=login("officer")).json()["data"]
    old_versions = {c["reference"]: c["latest_decision"]["rule_version"] for c in old if c["reference"].startswith("SP-0")}
    assert set(old_versions.values()) == {1}


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
