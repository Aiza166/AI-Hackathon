"""Security review M1 + M2 and L1: one PIN failure counter, lockout per (user, IP), unlock, sessions."""
from tests.conftest import BASE_CLAIM, PHONES

ZAINAB = PHONES["zainab"]


def _login(client, pin: str, ip: str | None = None):
    headers = {"X-Test-Client-IP": ip} if ip else {}
    return client.post("/api/v1/auth/login", json={"phone": ZAINAB, "pin": pin}, headers=headers)


def _change(client, login) -> tuple[dict, str]:
    zainab = login("zainab")
    case = client.post("/api/v1/cases", json=BASE_CLAIM, headers=zainab).json()["data"]
    change = client.post(f"/api/v1/cases/{case['id']}/payout-change", json={"new_iban": "PK00MOCK0000000000000009"}, headers=zainab)
    assert change.status_code == 201, change.text
    return zainab, change.json()["data"]["id"]


def test_login_lock_is_per_ip_so_a_stranger_cannot_lock_zainab_out(client, monkeypatch):
    from app.core import lockout

    monkeypatch.setattr(lockout, "client_ip", lambda request: request.headers.get("X-Test-Client-IP", "testclient"))
    for _ in range(5):
        assert _login(client, "0000", ip="198.51.100.66").status_code == 401
    assert _login(client, "1234", ip="198.51.100.66").status_code == 429
    assert _login(client, "1234", ip="203.0.113.5").status_code == 200  # Zainab on her own phone


def test_payout_confirm_failures_share_the_login_counter(client, login):
    zainab, change_id = _change(client, login)
    for _ in range(3):
        assert _login(client, "0000").status_code == 401
    for _ in range(2):
        response = client.post(f"/api/v1/payout-changes/{change_id}/confirm", json={"pin": "9999"}, headers=zainab)
        assert response.status_code == 401
    assert _login(client, "1234").status_code == 429


def test_five_wrong_payout_pins_end_the_session(client, login):
    zainab, change_id = _change(client, login)
    from app.core.ratelimit import limiter

    for i in range(5):
        limiter.reset()  # the 5/minute route limit is not what is under test here
        response = client.post(f"/api/v1/payout-changes/{change_id}/confirm", json={"pin": "9999"}, headers=zainab)
        assert response.status_code == 401, (i, response.text)
    assert client.get("/api/v1/me", headers=zainab).status_code == 401
    limiter.reset()
    assert client.post(f"/api/v1/payout-changes/{change_id}/confirm", json={"pin": "1234"}, headers=zainab).status_code == 401


def test_admin_unlock_is_audited_and_clears_the_lock(client, login):
    for _ in range(5):
        _login(client, "0000")
    assert _login(client, "1234").status_code == 429
    admin = login("admin")
    users = client.get("/api/v1/admin/users", headers=admin).json()["data"]
    zainab_id = next(u["id"] for u in users if u["phone_last4"] == ZAINAB[-4:])
    assert client.post(f"/api/v1/admin/users/{zainab_id}/unlock", headers=admin).status_code == 200
    assert _login(client, "1234").status_code == 200
    events = client.get("/api/v1/audit?action=PIN_UNLOCKED", headers=login("auditor")).json()["data"]
    assert events and events[0]["resource"] == f"user:{zainab_id}"


def test_helper_can_unlock_assigned_family_only(client, login):
    for _ in range(5):
        _login(client, "0000")
    helper = login("helper")
    families = client.get("/api/v1/helper/families", headers=helper).json()["data"]
    zainab_person = next(f["id"] for f in families if f["name"] == "Zainab Bibi")
    assert client.post(f"/api/v1/helper/families/{zainab_person}/unlock", headers=helper).status_code == 200
    assert _login(client, "1234").status_code == 200
    me = client.get("/api/v1/me", headers=login("rukhsana")).json()["data"]
    assert client.post(f"/api/v1/helper/families/{me['person']['id']}/unlock", headers=helper).status_code == 403


def test_login_response_has_no_refresh_token(client):
    body = _login(client, "1234").json()["data"]
    assert "refresh_token" not in body
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": "x" * 20}).status_code in (404, 405)


def test_logout_revokes_the_token(client, login):
    zainab = login("zainab")
    assert client.post("/api/v1/auth/logout", headers=zainab).status_code == 200
    assert client.get("/api/v1/me", headers=zainab).status_code == 401
    fresh = login("zainab")
    assert client.get("/api/v1/me", headers=fresh).status_code == 200
