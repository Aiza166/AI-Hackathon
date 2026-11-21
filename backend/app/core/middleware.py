"""Pure ASGI middleware: security headers on every response, and a request body size cap."""
import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

SECURITY_HEADERS = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
)


class SecurityHeadersMiddleware:
    """nosniff, no framing, no referrer; JSON responses are never cached (shared phones)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                headers += [(k, v) for k, v in SECURITY_HEADERS if k not in present]
                content_type = dict(headers).get(b"content-type", b"")
                if content_type.startswith(b"application/json") and b"cache-control" not in present:
                    headers.append((b"cache-control", b"no-store"))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


class BodySizeLimitMiddleware:
    """413 for bodies over the limit, by Content-Length or while streaming (chunked)."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        length = dict(scope.get("headers", [])).get(b"content-length")
        if length is not None:
            try:
                too_big = int(length) > self.max_bytes
            except ValueError:
                too_big = True
            if too_big:
                await _reject(send)
                return
            await self.app(scope, receive, send)  # declared size is within the limit
            return
        # No Content-Length (chunked): read up to the limit first, then replay to the app.
        chunks: list[bytes] = []
        received = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                await self.app(scope, _replay([], message), send)
                return
            body = message.get("body", b"")
            received += len(body)
            if received > self.max_bytes:
                await _reject(send)
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break
        await self.app(scope, _replay(chunks, None), send)


def _replay(chunks: list[bytes], final: Message | None) -> Receive:
    pending: list[Message] = [{"type": "http.request", "body": b"".join(chunks), "more_body": False}] if final is None else [final]

    async def receive() -> Message:
        if pending:
            return pending.pop(0)
        return {"type": "http.disconnect"}

    return receive


async def _reject(send: Send) -> None:
    body = json.dumps({"success": False, "data": None, "meta": {},
                       "error": {"code": "PAYLOAD_TOO_LARGE", "message": "The upload is too large."}}).encode()
    await send({"type": "http.response.start", "status": 413,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})
