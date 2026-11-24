"""Per-process request limits for the single-worker API deployment."""

from collections import OrderedDict
from dataclasses import dataclass
from math import ceil
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request

from app.features.auth.common.authentication import verify_request_token
from app.features.auth.common.dependencies import get_auth
from app.features.auth.exceptions import AuthenticationFailed

WINDOW_SECONDS = 60
MAX_ACTIVE_COUNTERS = 10_000


@dataclass
class RequestWindow:
    expires_at: float
    count: int = 0


class RateLimiter:
    def __init__(self) -> None:
        self._windows: OrderedDict[tuple[str, str], RequestWindow] = OrderedDict()
        self._lock = Lock()

    def check(self, key: tuple[str, str], limit: int) -> None:
        with self._lock:
            now = monotonic()
            # Windows retain creation order, so expired counters are always first.
            while self._windows:
                oldest_window = next(iter(self._windows.values()))
                if oldest_window.expires_at > now:
                    break
                self._windows.popitem(last=False)

            window = self._windows.get(key)
            if window is None:
                if len(self._windows) >= MAX_ACTIVE_COUNTERS:
                    oldest_window = next(iter(self._windows.values()))
                    self._reject(oldest_window.expires_at - now)
                window = RequestWindow(expires_at=now + WINDOW_SECONDS)
                self._windows[key] = window

            if window.count >= limit:
                self._reject(window.expires_at - now)
            window.count += 1

    @staticmethod
    def _reject(seconds_remaining: float) -> None:
        raise HTTPException(
            status_code=429,
            detail="Too many requests",
            headers={"Retry-After": str(max(1, ceil(seconds_remaining)))},
        )


async def enforce_rate_limit(request: Request) -> None:
    path = request.scope["route"].path
    if not path.startswith("/api/v1/"):
        return

    client_ip = "unknown"
    if request.client is not None:
        client_ip = request.client.host
    limiter = request.app.state.rate_limiter

    if path == "/api/v1/auth/login":
        limiter.check(("login", client_ip), 10)
        return
    if path == "/api/v1/auth/refresh":
        limiter.check(("refresh", client_ip), 30)
        return

    try:
        user_id, _ = await verify_request_token(request, "access", get_auth())
    except AuthenticationFailed:
        limiter.check(("anonymous", client_ip), 120)
        return

    limiter.check(("user", str(user_id)), 120)
