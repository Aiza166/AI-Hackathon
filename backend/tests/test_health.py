from fastapi.testclient import TestClient

from app.main import create_app


def test_healthz_returns_envelope_and_prototype_flag():
    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {"status": "ok", "prototype": True}
    assert body["error"] is None


def test_unknown_route_uses_error_envelope():
    client = TestClient(create_app())

    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "HTTP_404"


def test_openapi_marks_project_as_prototype():
    client = TestClient(create_app())

    description = client.get("/openapi.json").json()["info"]["description"]

    assert "PROTOTYPE" in description
