"""FastAPI entry point."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.api import admin, audit, auth, cases, consent, me, payout, public, rules
from app.core.config import get_settings
from app.core.envelope import fail, install_error_handlers, ok
from app.core.ratelimit import limiter
from app.db import SessionLocal
from app.mock import router as mock_router

PROTOTYPE_NOTE = (
    "**PROTOTYPE ONLY. Not an official government service.** "
    "All identity, family, death, pension and payment services are simulated with mock data.\n\n"
    "Sign in at `POST /api/v1/auth/login` (demo PIN 1234), then use **Authorize** with the access token. "
    "Outside systems use the `X-API-Key` header on `/api/v1/public/*`."
)


def _rate_limited(_: Request, __: RateLimitExceeded) -> JSONResponse:
    return fail(code="RATE_LIMITED", message="Too many requests. Please wait a minute.", status=429)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.2.0", description=PROTOTYPE_NOTE)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limited)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key", "Idempotency-Key"],
    )
    install_error_handlers(app)
    for router in (auth.router, me.router, consent.router, cases.router, audit.router, admin.router, rules.router, payout.router, public.router, mock_router.router):
        app.include_router(router)

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict:
        return ok({"status": "ok", "prototype": True})

    @app.get("/readyz", tags=["health"])
    def readyz() -> dict:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return ok({"database": "ok"})

    return app


app = create_app()
