"""FastAPI entry point."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.api import admin, audit, auth, cases, consent, documents, evaluation, me, payout, public, rules, scam, speech
from app.core.config import get_settings
from app.core.envelope import fail, install_error_handlers, ok
from app.core.middleware import BodySizeLimitMiddleware, SecurityHeadersMiddleware
from app.core.ratelimit import limiter
from app.db import SessionLocal
from app.decision.jev_client import JevClient
from app.mock import router as mock_router

PROTOTYPE_NOTE = (
    "**PROTOTYPE ONLY. Not an official government service.** "
    "All identity, family, death, pension and payment services are simulated with mock data.\n\n"
    "Sign in at `POST /api/v1/auth/login`, then use **Authorize** with the access token. "
    "Outside systems use the `X-API-Key` header on `/api/v1/public/*`."
)


def _rate_limited(_: Request, __: RateLimitExceeded) -> JSONResponse:
    return fail(code="RATE_LIMITED", message="Too many requests. Please wait a minute.", status=429)


def create_app() -> FastAPI:
    settings = get_settings()
    # Production: no public API explorer unless ALLOW_DOCS=true.
    docs_on = not settings.is_production or settings.allow_docs
    app = FastAPI(title=settings.app_name, version="0.2.0", description=PROTOTYPE_NOTE,
                  docs_url="/docs" if docs_on else None, redoc_url="/redoc" if docs_on else None,
                  openapi_url="/openapi.json" if docs_on else None)
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
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)  # outermost: before any parsing
    install_error_handlers(app)
    for router in (auth.router, me.router, consent.router, cases.router, audit.router, admin.router, rules.router, payout.router, scam.router, documents.router, speech.router, evaluation.router, public.router, mock_router.router):
        app.include_router(router)

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict:
        return ok({"status": "ok", "prototype": True})

    @app.get("/readyz", tags=["health"])
    def readyz() -> dict:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        jev = JevClient()
        try:
            jev_ok = jev.reachable()
        finally:
            jev.close()
        return ok({"database": "ok", "jev_reachable": jev_ok, "jev_model": get_settings().jev_model})

    return app


app = create_app()
