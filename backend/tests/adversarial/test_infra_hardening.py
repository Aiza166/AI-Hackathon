"""Security review H3 (XFF), M3 (headers), M5 (audit anchor log), M6 (body size)."""
import logging

from starlette.requests import Request

from app.core.ratelimit import client_ip, rate_limit_key

WRONG = {"phone": "00000000099", "pin": "0000"}  # unknown phone: no lockout, only the IP limit


def test_spoofed_forwarded_for_does_not_reset_login_limit(client):
    codes = [
        client.post("/api/v1/auth/login", json=WRONG, headers={"X-Forwarded-For": f"203.0.113.{i}"}).status_code
        for i in range(14)
    ]
    assert codes.count(429) >= 4, codes


def _request(peer: str, xff: str | None = None, auth: str | None = None) -> Request:
    headers = []
    if xff:
        headers.append((b"x-forwarded-for", xff.encode()))
    if auth:
        headers.append((b"authorization", auth.encode()))
    return Request({"type": "http", "client": (peer, 1), "headers": headers, "method": "GET", "path": "/"})


def test_client_ip_uses_rightmost_untrusted_hop(monkeypatch):
    from app.core import ratelimit

    monkeypatch.setattr(ratelimit, "_trusted", ratelimit._parse_trusted("10.0.0.0/8,127.0.0.1"))
    assert client_ip(_request("10.1.2.3", "1.1.1.1, 198.51.100.7, 10.9.9.9")) == "198.51.100.7"
    assert client_ip(_request("198.51.100.8", "1.1.1.1")) == "198.51.100.8"  # untrusted peer: header ignored
    assert client_ip(_request("10.1.2.3", "garbage, 10.2.2.2")) == "10.1.2.3"


def test_key_is_user_id_for_valid_bearer(login):
    headers = login("zainab")
    assert rate_limit_key(_request("1.2.3.4", auth=headers["Authorization"])).startswith("user:")
    assert rate_limit_key(_request("1.2.3.4", auth="Bearer not-a-jwt")) == "ip:1.2.3.4"


def test_security_headers_on_api_responses(client, login):
    response = client.get("/api/v1/me", headers=login("zainab"))
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store"
    assert client.get("/healthz").headers["X-Content-Type-Options"] == "nosniff"


def test_oversized_body_rejected_by_content_length(client):
    big = b"x" * (10 * 1024 * 1024 + 10)
    response = client.post("/api/v1/auth/login", content=big, headers={"Content-Type": "application/json"})
    assert response.status_code == 413


def test_oversized_streamed_body_rejected(client):
    def chunks():
        for _ in range(11):
            yield b"x" * (1024 * 1024)

    response = client.post("/api/v1/auth/login", content=chunks(), headers={"Content-Type": "application/json"})
    assert response.status_code == 413


def test_audit_verify_logs_head_anchor(client, login, caplog):
    auditor = login("auditor")
    with caplog.at_level(logging.INFO, logger="sahara.audit"):
        body = client.get("/api/v1/audit/verify", headers=auditor).json()["data"]
    assert any("AUDIT_ANCHOR" in r.getMessage() and body["head_hash"] in r.getMessage() for r in caplog.records)
