"""Small ASGI boundary: cap credential bodies and prevent caching account data."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class AuthHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/"):
            await self.app(scope, receive, send)
            return
        if scope["path"].startswith("/api/v1/auth/") and scope["method"] == "POST":
            chunks: list[bytes] = []
            size = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                size += len(chunk)
                if size > 16384:
                    await send(
                        {
                            "type": "http.response.start",
                            "status": 413,
                            "headers": [(b"cache-control", b"no-store")],
                        }
                    )
                    await send({"type": "http.response.body", "body": b"Request too large"})
                    return
                chunks.append(chunk)
                if not message.get("more_body", False):
                    break
            consumed = False
            original = receive

            async def buffered() -> Message:
                nonlocal consumed
                if consumed:
                    return await original()
                consumed = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}

            receive = buffered

        async def secured(message: Message) -> None:
            if message["type"] == "http.response.start":
                if scope["path"] == "/api/v1/auth/google/callback":
                    # Uvicorn formats its access line from the scope at response start.
                    # The handler has consumed the authorization code; keep it out of logs.
                    scope["query_string"] = b""
                headers = [
                    (k, v) for k, v in message.get("headers", []) if k.lower() != b"cache-control"
                ]
                headers.extend(
                    [
                        (b"cache-control", b"private, no-store"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"x-content-type-options", b"nosniff"),
                    ]
                )
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, secured)
