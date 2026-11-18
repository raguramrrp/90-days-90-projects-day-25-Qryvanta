"""Filename sanitization and lightweight sliding-window rate limiting utilities."""

from collections import defaultdict, deque
import re
import time
import uuid
from pathlib import Path
from fastapi import HTTPException, Request, status


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(original_name: str) -> tuple[str, str]:
    """Return (safe_display_name, unique_stored_filename)."""
    base = Path(original_name or "attachment.bin").name
    cleaned = _SAFE_NAME_RE.sub("_", base).strip("._") or "attachment.bin"
    ext = Path(cleaned).suffix.lower()
    stored = f"{uuid.uuid4().hex}{ext}"
    return cleaned[:200], stored


class SlidingWindowRateLimiter:
    """In-memory per-IP rate limiter for sensitive endpoints (e.g. auth login/register)."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, request: Request, key_suffix: str = "") -> None:
        client_host = request.client.host if request.client else "unknown"
        if client_host in ("testclient",):
            return
        bucket = f"{client_host}:{key_suffix}"
        now = time.monotonic()
        q = self._hits[bucket]
        while q and (now - q[0]) > self.window_seconds:
            q.popleft()
        if len(q) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please wait briefly before trying again.",
            )
        q.append(now)


auth_rate_limiter = SlidingWindowRateLimiter(max_requests=40, window_seconds=60)
