import os,sys
os.environ["JWT_SECRET"]="x"*40
sys.path.insert(0, r"C:\Users\aizag\Desktop\ai hackathon\team-repo\backend")
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from app.core.ratelimit import limiter  # the app's real limiter (get_remote_address)
app=FastAPI(); app.state.limiter=limiter
from fastapi.responses import PlainTextResponse
app.add_exception_handler(RateLimitExceeded, lambda r,e: PlainTextResponse("429",status_code=429))
app.add_middleware(SlowAPIMiddleware)
@app.post("/login")
@limiter.limit("10/minute")
def login(request: Request): return {"ok":1}
wrapped=ProxyHeadersMiddleware(app, trusted_hosts="*")  # same as --forwarded-allow-ips '*'
c=TestClient(wrapped)
plain=[c.post("/login").status_code for _ in range(14)]
print("no XFF  :",plain)
limiter.reset()
spoof=[c.post("/login",headers={"X-Forwarded-For":f"10.9.{i}.1, 203.0.113.7"}).status_code for i in range(14)]
print("spoofed :",spoof)
