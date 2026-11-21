import conftest as c
from app.models.platform import Case
from app.documents.service import redecide

def test_d2(client, login, db):
    z = login("zainab")
    cid = client.post("/api/v1/cases", json=c.BASE_CLAIM, headers=z).json()["data"]["id"]
    client.post(f"/api/v1/cases/{cid}/escalate", json={"reason": "please human check"}, headers=z)
    case = db.get(Case, cid); print("D2 before", case.status, case.assigned_officer_id is not None)
    redecide(db, case); db.commit()
    print("D2 after redecide (what any doc upload/confirm triggers):", db.get(Case, cid).status)

def test_g_race_count(login, db):
    import threading
    from fastapi.testclient import TestClient
    from app.main import create_app
    z = login("zainab"); out=[]
    def go(): out.append(TestClient(create_app()).post("/api/v1/cases", json=c.BASE_CLAIM, headers=z).json())
    ts=[threading.Thread(target=go) for _ in range(5)]; [t.start() for t in ts]; [t.join() for t in ts]
    print("G", [(o["data"]["reference"], o["data"]["status"]) for o in out if o.get("data")])
