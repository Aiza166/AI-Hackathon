"""Pure ASGI middleware: security headers on every response, and a request body size cap.

Pure ASGI (not BaseHTTPMiddleware) so streaming responses and uploads are not buffered.
"""
import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# 8 MB photo + multipart overhead. Anything bigger is refused before it is parsed or spooled.
MAX_REQUEST_BYTES = 9 * 1024 * 1024

API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
# Swagger UI / ReDoc load their bundle from jsDelivr and run one inline bootstrap script.
DOCS_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; "
    "worker-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)
DOCS_PATHS = frozenset({"/docs", "/docs/oauth2-redirect", "/redoc"})

BASE_HEADERS = {
    b"x-content-type-options": b"nosniff",
    b"x-frame-options": b"DENY",
    b"referrer-policy": b"no-referrer",
    b"strict-transport-security": b"max-age=31536000; includeSubDomains",
    b"permissions-policy": b"camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    b"cross-origin-opener-policy": b"same-origin",
    b"cross-origin-resource-policy": b"cross-origin",  # the PWA on another Railway domain loads images/audio
}


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")
        csp = DOCS_CSP if path in DOCS_PATHS else API_CSP

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                extra = {**BASE_HEADERS, b"content-security-policy": csp.encode()}
                # Personal data must not sit in shared caches; routes that want caching (TTS) set their own.
                extra[b"cache-control"] = b"no-store"
                headers.extend((k, v) for k, v in extra.items() if k not in present)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


def _too_large_response() -> tuple[Message, Message]:
    body = json.dumps({"success": False, "data": None, "error": {"code": "PAYLOAD_TOO_LARGE",
                       "message": "The request is too large."}, "meta": {}}).encode()
    start = {"type": "http.response.start", "status": 413,
             "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
                         (b"connection", b"close")]}
    return start, {"type": "http.response.body", "body": body}


class BodySizeLimitMiddleware:
    """Refuse bodies over max_bytes: by Content-Length up front, and by counting streamed chunks.

    A chunked body that grows past the cap is cut off (the app sees an end of body) and
    whatever the app answers is replaced by the 413, so nothing past the cap is read.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_REQUEST_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    too_big = int(value) > self.max_bytes
                except ValueError:
                    too_big = True
                if too_big:
                    await self._reject(send)
                    return
        state = {"received": 0, "exceeded": False, "replied": False}

        async def limited_receive() -> Message:
            if state["exceeded"]:
                return {"type": "http.request", "body": b"", "more_body": False}
            message = await receive()
            if message["type"] == "http.request":
                state["received"] += len(message.get("body", b""))
                if state["received"] > self.max_bytes:
                    state["exceeded"] = True
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        async def guarded_send(message: Message) -> None:
            if not state["exceeded"]:
                await send(message)
                return
            if not state["replied"]:
                state["replied"] = True
                await self._reject(send)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if not state["exceeded"]:
                raise
            # The truncated body made the app fail: the answer is still the 413.
        if state["exceeded"] and not state["replied"]:
            state["replied"] = True
            await self._reject(send)

    @staticmethod
    async def _reject(send: Send) -> None:
        start, body = _too_large_response()
        await send(start)
        await send(body)
