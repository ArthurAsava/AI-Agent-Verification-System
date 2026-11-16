"""HTTP boundary protections shared by the FastAPI application."""

from __future__ import annotations

from collections import OrderedDict, deque
from math import ceil
from threading import Lock
from time import monotonic
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp


class SlidingWindowRateLimiter:
    """A bounded, process-local request limiter.

    This gives the API a safe default for a single process. A production
    deployment with multiple API instances must additionally enforce matching
    limits at its reverse proxy or API gateway.
    """

    def __init__(
        self,
        *,
        limit: int,
        window_seconds: int,
        max_clients: int,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self.clock = clock
        self._requests: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        """Return whether a request is permitted and any retry delay."""

        now = self.clock()
        cutoff = now - self.window_seconds

        with self._lock:
            timestamps = self._requests.get(key)
            if timestamps is None:
                if len(self._requests) >= self.max_clients:
                    self._requests.popitem(last=False)
                timestamps = deque()
                self._requests[key] = timestamps
            else:
                self._requests.move_to_end(key)

            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            if len(timestamps) >= self.limit:
                retry_after = max(
                    1,
                    ceil(self.window_seconds - (now - timestamps[0])),
                )
                return False, retry_after

            timestamps.append(now)
            return True, 0


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach headers that are appropriate for JSON API responses."""

    def __init__(self, app: ASGIApp, *, enforce_https: bool) -> None:
        super().__init__(app)
        self.enforce_https = enforce_https

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )

        if self.enforce_https:
            headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

        path = request.url.path
        if path.startswith("/api/") or path.startswith("/verification/"):
            headers.setdefault("Cache-Control", "no-store")
            headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
                "form-action 'none'",
            )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate-limit API requests before they reach authentication or storage."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        limit: int,
        window_seconds: int,
        max_clients: int,
        trust_proxy_headers: bool,
    ) -> None:
        super().__init__(app)
        self.limiter = SlidingWindowRateLimiter(
            limit=limit,
            window_seconds=window_seconds,
            max_clients=max_clients,
        )
        self.trust_proxy_headers = trust_proxy_headers

    def _client_key(self, request: Request) -> str:
        if self.trust_proxy_headers:
            forwarded = request.headers.get("x-forwarded-for", "")
            forwarded_ip = forwarded.split(",", 1)[0].strip()
            if forwarded_ip:
                return forwarded_ip

        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        path = request.url.path
        if not (
            path.startswith("/api/")
            or path.startswith("/verification/")
        ):
            return await call_next(request)

        allowed, retry_after = self.limiter.allow(self._client_key(request))
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please retry shortly."},
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
