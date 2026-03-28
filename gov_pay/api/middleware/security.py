"""Security headers and rate limiting middleware."""

import logging
import time
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to all responses.

    Required for PCI DSS compliance and NIST SP 800-53.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "frame-ancestors 'none'"
        )
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter for payment endpoints.

    Limits requests per IP address to prevent card testing attacks
    and brute-force API key attempts.

    In production, use Redis-backed rate limiting for multi-instance deployments.
    """

    def __init__(self, app, payment_limit: int = 30, general_limit: int = 120, window_seconds: int = 60):
        super().__init__(app)
        self.payment_limit = payment_limit  # Max payment requests per window
        self.general_limit = general_limit  # Max general requests per window
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _is_payment_endpoint(self, path: str) -> bool:
        return "/payments" in path and not path.endswith("/search")

    def _clean_old_requests(self, key: str):
        cutoff = time.time() - self.window_seconds
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]

    async def dispatch(self, request: Request, call_next):
        # Extract client IP
        forwarded = request.headers.get("X-Forwarded-For")
        client_ip = forwarded.split(",")[0].strip() if forwarded else (
            request.client.host if request.client else "unknown"
        )

        is_payment = self._is_payment_endpoint(request.url.path)
        limit = self.payment_limit if is_payment else self.general_limit
        rate_key = f"{client_ip}:{'payment' if is_payment else 'general'}"

        self._clean_old_requests(rate_key)

        if len(self._requests[rate_key]) >= limit:
            logger.warning("Rate limit exceeded for %s on %s", client_ip, request.url.path)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": str(self.window_seconds)},
            )

        self._requests[rate_key].append(time.time())
        return await call_next(request)
