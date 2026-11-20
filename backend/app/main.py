"""FastAPI entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.envelope import install_error_handlers, ok

PROTOTYPE_NOTE = (
    "**PROTOTYPE ONLY. Not an official government service.** "
    "All identity, family, death, pension and payment services are simulated with mock data."
)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", description=PROTOTYPE_NOTE)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict:
        return ok({"status": "ok", "prototype": True})

    return app


app = create_app()
