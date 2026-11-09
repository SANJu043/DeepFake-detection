"""
FastAPI dependencies for authentication and authorization.

Provides:
- ``get_current_user``: decode JWT and return the User ORM object.
- ``require_role``: closure that restricts endpoints to specific RBAC roles.
"""

from __future__ import annotations

from typing import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.core.database import get_db
from backend.app.core.security import decode_token
from backend.app.models.models import User

import jwt as pyjwt
import structlog

logger = structlog.get_logger(__name__)

_bearer = HTTPBearer()


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decode the Bearer JWT, look up the user, and return the ORM object.

    Raises 401 if the token is invalid, expired, or the user is not found.
    """
    settings = get_settings()
    token = creds.credentials

    try:
        payload = decode_token(
            token,
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token payload")

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")

    return user


def require_role(*roles: str) -> Callable:
    """
    Factory that returns a dependency requiring the user to have one of
    the specified roles.

    Usage::

        @router.get("/admin-only")
        async def admin_endpoint(user: User = Depends(require_role("admin"))):
            ...
    """
    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Requires one of roles: {', '.join(roles)}",
            )
        return user

    return _check
