import threading
from fastapi.testclient import TestClient
from app.main import create_app
from app.models.platform import Case
from sqlalchemy import select
from conftest import BASE_CLAIM  # noqa

def _claim(**kw):
    import copy; c = copy.deepcopy(BASE); c.update(kw); return c

BASE = None

def test_a_auto_approve_no_uploads(client, login, db):
    global BASE
    import conftest as c; BASE = c.BASE_CLAIM
    z = login("zainab")
    r = client.post("/api/v1/cases", json=BASE, headers=z)
    print("A status", r.status_code, r.json()["data"]["status"], r.json()["data"]["latest_decision"]["route"])
    cid = r.json()["data"]["id"]
    docs = client.get(f"/api/v1/cases/{cid}/documents", headers=z).json()["data"]
    print("A uploaded docs:", docs)

def test_b_dup_bypass_null_cnic(client, login):
    import conftest as c
    z = login("zainab")
    first = dict(c.BASE_CLAIM); first["deceased_cnic"] = None
    r1 = client.post("/api/v1/cases", json=first, headers=z)
    r2 = client.post("/api/v1/cases", json=c.BASE_CLAIM, headers=z)
    print("B", r1.status_code, r1.json()["data"]["status"], r2.status_code, r2.json().get("data", {}).get("status"))
    r3 = client.post("/api/v1/cases", json=c.BASE_CLAIM, headers=z)
    print("B third (control)", r3.status_code)

def test_c_race_double_claim(login):
    import conftest as c
    z = login("zainab")
    out = []
    def go(i):
        cl = TestClient(create_app())
        out.append(cl.post("/api/v1/cases", json=c.BASE_CLAIM, headers=z).status_code)
    ts = [threading.Thread(target=go, args=(i,)) for i in range(6)]
    [t.start() for t in ts]; [t.join() for t in ts]
    print("C race statuses", out)
