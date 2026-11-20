"""One response envelope for every API response: success, data, error, meta."""
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


def ok(data: Any = None, meta: dict | None = None) -> dict:
    return {"success": True, "data": data, "error": None, "meta": meta or {}}


def fail(code: str, message: str, status: int) -> JSONResponse:
    body = {"success": False, "data": None, "error": {"code": code, "message": message}, "meta": {}}
    return JSONResponse(status_code=status, content=body)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return fail(code=f"HTTP_{exc.status_code}", message=str(exc.detail), status=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Field names only: never echo submitted values back (they may be personal data).
        fields = [".".join(str(p) for p in err["loc"]) for err in exc.errors()]
        return fail(code="VALIDATION_ERROR", message=f"Invalid fields: {', '.join(fields)}", status=422)

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        # Details go to server logs, never to the client.
        import logging

        logging.getLogger("sahara").exception("Unhandled error", exc_info=exc)
        return fail(code="INTERNAL_ERROR", message="Something went wrong. Please try again.", status=500)
