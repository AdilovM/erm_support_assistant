"""Authentication and authorization middleware."""

import hashlib
import hmac
import logging
import time
from typing import Optional

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from gov_pay.config.settings import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

api_key_header = APIKeyHeader(name=settings.api_key_header, auto_error=False)

# Parse configured API keys into a set for O(1) lookup
_valid_api_keys: set[str] = set()
if settings.api_keys:
    _valid_api_keys = {k.strip() for k in settings.api_keys.split(",") if k.strip()}


async def verify_api_key(
    request: Request,
    api_key: Optional[str] = Security(api_key_header),
) -> str:
    """Verify API key from request header.

    Validates the API key against configured keys. Uses constant-time
    comparison to prevent timing attacks.
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    if not _valid_api_keys:
        logger.error("No API keys configured — all requests will be rejected. Set APP_API_KEYS.")
        raise HTTPException(status_code=503, detail="Service not configured")

    # Constant-time comparison to prevent timing attacks
    is_valid = any(
        hmac.compare_digest(api_key, valid_key)
        for valid_key in _valid_api_keys
    )

    if not is_valid:
        logger.warning(
            "Invalid API key attempt from %s",
            get_client_ip(request),
        )
        raise HTTPException(status_code=403, detail="Invalid API key")

    return api_key


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
