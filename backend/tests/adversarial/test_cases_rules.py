"""Regression tests for rule publishing (red team H6) and rule validation (Security review L2)."""
from datetime import date, timedelta

from sqlalchemy import select

from app.core.security import create_access_token
from app.models.platform import Case, Decision, RuleVersion, Tenant, User
from app.services.cases import live_ruleset
from tests.helpers import attach_documents, redecide_case


def _versions(client, headers) -> dict:
    return {r["version"]: r for r in client.get("/api/v1/admin/rules", headers=headers).json()["data"]}


def second_admin(db) -> dict:
    tenant = db.execute(select(Tenant).where(Tenant.slug == "pension")).scalar_one()
    user = User(tenant_id=tenant.id, role="admin", name="Second admin", phone="00000000093", pin_hash="unused")
    db.add(user)
    db.commit()
    return {"Authorization": f"Bearer {create_access_token(user.id, 'admin', tenant.id)}"}


def test_h6_publish_without_simulation_or_second_admin_is_refused(client, login, db):
    admin = login("admin")
    v2 = _versions(client, admin)[2]["id"]
    assert client.post(f"/api/v1/rules/{v2}/publish", headers=admin).status_code == 409  # no Digital Twin run
    client.post(f"/api/v1/rules/{v2}/simulate", headers=admin)
    assert client.post(f"/api/v1/rules/{v2}/publish", headers=admin).status_code == 409  # no second admin
    client.post(f"/api/v1/rules/{v2}/approve", headers=admin)  # self-approval does not count
    assert client.post(f"/api/v1/rules/{v2}/publish", headers=admin).status_code == 409
    assert client.post(f"/api/v1/rules/{v2}/approve", headers=second_admin(db)).status_code == 200
    assert client.post(f"/api/v1/rules/{v2}/publish", headers=admin).status_code == 200


def test_h6_future_effective_from_is_not_live_before_that_date(client, login, db):
    admin = login("admin")
    v1 = _versions(client, admin)[1]
    future = (date.today() + timedelta(days=30)).isoformat()
    draft = client.post("/api/v1/rules/drafts", json={"label": "future rules", "rules": v1["rules"], "thresholds": v1["thresholds"],
                                                     "effective_from": future}, headers=admin).json()["data"]
    client.post(f"/api/v1/rules/{draft['id']}/simulate", headers=admin)
    client.post(f"/api/v1/rules/{draft['id']}/approve", headers=second_admin(db))
    published = client.post(f"/api/v1/rules/{draft['id']}/publish", headers=admin).json()["data"]

    assert published["status"] == "scheduled"
    db.expire_all()
    assert live_ruleset(db).version == 1
    assert live_ruleset(db, date.today() + timedelta(days=31)).version == draft["version"]


def test_h6_redecision_stays_on_the_cases_original_rule_version(client, login, db, file_claim):
    case_id = file_claim("zainab")["data"]["id"]
    admin = login("admin")
    v2 = _versions(client, admin)[2]["id"]
    client.post(f"/api/v1/rules/{v2}/simulate", headers=admin)
    client.post(f"/api/v1/rules/{v2}/approve", headers=second_admin(db))
    assert client.post(f"/api/v1/rules/{v2}/publish", headers=admin).status_code == 200

    attach_documents(db, case_id)
    redecide_case(db, case_id)
    latest = db.execute(select(Decision).where(Decision.case_id == case_id).order_by(Decision.created_at.desc())).scalars().first()
    assert db.get(RuleVersion, latest.rule_version_id).version == 1
    assert db.get(Case, case_id).status == "auto_approved"


def _nested(depth: int) -> dict:
    condition: dict = {"fact": "age", "op": "is_true"}
    for _ in range(depth):
        condition = {"any_of": [condition]}
    return condition


def _draft(condition) -> dict:
    return {"label": "deep", "rules": [{"id": "D", "require": [condition], "on_fail": "missing_info", "reason": "MISSING_INFO"}],
            "thresholds": {"t_auto": 0.95, "t_human": 0.7}}


def test_l2_deeply_nested_conditions_are_422_not_500(client, login):
    admin = login("admin")
    assert client.post("/api/v1/rules/drafts", json=_draft(_nested(4)), headers=admin).status_code == 201
    assert client.post("/api/v1/rules/drafts", json=_draft(_nested(5)), headers=admin).status_code == 422
    raw = '{"label":"deep","thresholds":{},"rules":[' + '{"any_of":[' * 5000 + ']}' * 5000 + ']}'
    response = client.post("/api/v1/rules/drafts", content=raw, headers={**admin, "Content-Type": "application/json"})
    assert response.status_code == 422


def test_l2_malformed_condition_types_and_huge_drafts_are_422(client, login):
    admin = login("admin")
    assert client.post("/api/v1/rules/drafts", json=_draft("not-an-object"), headers=admin).status_code == 422
    assert client.post("/api/v1/rules/drafts", json=_draft({"any_of": "x"}), headers=admin).status_code == 422
    huge = _draft({"fact": "age", "op": "in", "value": ["x" * 1000] * 200})
    assert client.post("/api/v1/rules/drafts", json=huge, headers=admin).status_code == 422
