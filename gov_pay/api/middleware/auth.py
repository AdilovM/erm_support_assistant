"""Authentication and authorization middleware."""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from gov_pay.config.settings import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

api_key_header = APIKeyHeader(name=settings.api_key_header, auto_error=False)


async def verify_api_key(
    request: Request,
    api_key: Optional[str] = Security(api_key_header),
) -> str:
    """Verify API key from request header.

    In production, this would validate against a database of API keys
    associated with specific government entities.
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    # In production: look up api_key in database, verify it's active,
    # and return the associated entity_id / permissions
    # For now, accept any non-empty key in development mode
    if settings.debug:
        return api_key

    # Production validation would go here
    # entity = await db.execute(select(APIKey).where(APIKey.key == api_key, APIKey.is_active == True))
    # if not entity:
    #     raise HTTPException(status_code=403, detail="Invalid API key")

    return api_key


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
