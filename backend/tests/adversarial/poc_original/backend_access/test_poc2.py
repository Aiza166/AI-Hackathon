import io, conftest as c
from PIL import Image, ImageDraw

def _png():
    im = Image.new("RGB", (1400, 900), "white"); d = ImageDraw.Draw(im)
    for i in range(20): d.text((50, 40*i+20), "DEATH CERTIFICATE Muhammad Aslam 9000000000011 14-08-2026", fill="black")
    b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()

def test_d_escalation_undone_by_upload(client, login):
    z = login("zainab")
    cid = client.post("/api/v1/cases", json=c.BASE_CLAIM, headers=z).json()["data"]["id"]
    r = client.post(f"/api/v1/cases/{cid}/escalate", json={"reason": "please human check, my brother-in-law forced me"}, headers=z)
    print("D after escalate:", r.json()["data"]["status"])
    r = client.post(f"/api/v1/cases/{cid}/documents", data={"kind": "death_certificate"}, files={"file": ("a.png", _png(), "image/png")}, headers=z)
    print("D upload:", r.status_code, r.json()["data"].get("status"), r.json()["data"].get("case_status"))

def test_f_close_approved_then_refile(client, login):
    z = login("zainab"); o = login("officer")
    cid = client.post("/api/v1/cases", json=c.BASE_CLAIM, headers=z).json()["data"]["id"]
    r = client.post(f"/api/v1/cases/{cid}/escalate", json={"reason": "xxx"}, headers=z)
    r = client.post(f"/api/v1/cases/{cid}/approve", json={"reason": "ok fine"}, headers=o)
    print("F approve", r.status_code, r.json().get("data",{}).get("status"), r.text[:150] if r.status_code!=200 else "")
    r = client.post(f"/api/v1/cases/{cid}/close", json={"reason": "closing"}, headers=o)
    print("F close approved", r.status_code, r.json().get("data",{}).get("status"))
    r = client.post(f"/api/v1/cases/{cid}/approve", json={"reason": "again"}, headers=o)
    print("F re-approve closed", r.status_code)
