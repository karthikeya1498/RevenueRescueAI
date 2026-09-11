"""Request observability primitives for RevenueRescue AI.

Author: Karthikeya
"""

from __future__ import annotations

import json
import logging
import time
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestObservabilityMiddleware:
    """Emit one structured access event per HTTP request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = logging.getLogger("revenuerescue.access")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = self._request_id(scope)
        status_code = 500
        started = time.perf_counter()

        async def send_with_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            self.logger.info(
                json.dumps(
                    {
                        "event": "http_request",
                        "request_id": request_id,
                        "method": scope.get("method"),
                        "path": scope.get("path"),
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                    },
                    sort_keys=True,
                )
            )

    @staticmethod
    def _request_id(scope: Scope) -> str:
        """Reuse a valid inbound request ID or generate a new correlation ID."""

        for key, value in scope.get("headers", []):
            if key.lower() == b"x-request-id" and value:
                return value.decode("ascii", errors="ignore")[:128] or str(uuid4())
        return str(uuid4())
