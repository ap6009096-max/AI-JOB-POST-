from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import CompanyUser, User
from app.db.repositories.companies import CompanyRepository
from app.db.repositories.users import UserRepository
from app.db.session import get_db

logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)
_jwk_client: PyJWKClient | None = None

COMPANY_ROLES = ("recruiter", "company_admin", "platform_admin")
PRODUCT_ROLES = ("candidate", "recruiter", "company_admin", "platform_admin")


@dataclass
class Principal:
    user: User
    claims: dict[str, Any]
    memberships: list[CompanyUser]

    @property
    def role(self) -> str | None:
        return self.user.role

    @property
    def is_platform_admin(self) -> bool:
        return self.user.role == "platform_admin"


def _jwks_client() -> PyJWKClient:
    global _jwk_client
    if _jwk_client is None:
        jwks_url = settings.resolved_jwks_url
        if not jwks_url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Supabase JWT verification is not configured",
            )
        _jwk_client = PyJWKClient(jwks_url)
    return _jwk_client


def decode_access_token(token: str) -> dict[str, Any]:
    signing_key = _jwks_client().get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["ES256", "RS256", "HS256"],
        audience=settings.supabase_jwt_audience,
        options={"require": ["sub", "exp"]},
    )
    # Never authorize from user_metadata; it is user-editable.
    claims.pop("user_metadata", None)
    return claims


async def get_current_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    try:
        return decode_access_token(credentials.credentials)
    except HTTPException:
        raise
    except Exception:
        logger.warning("jwt_verification_failed")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")


def _auth_user_id(claims: dict[str, Any]) -> UUID:
    try:
        return UUID(str(claims["sub"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token"
        ) from exc


async def get_current_user(
    claims: dict[str, Any] = Depends(get_current_claims),
    db: Session = Depends(get_db),
) -> Principal:
    user = UserRepository(db).get_by_auth_user_id(_auth_user_id(claims))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User profile is not provisioned",
        )
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    memberships = CompanyRepository(db).list_for_user(user.id)
    return Principal(user=user, claims=claims, memberships=memberships)


def require_roles(*roles: str) -> Callable[..., Principal]:
    allowed = set(roles)

    async def dependency(principal: Principal = Depends(get_current_user)) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role for this resource",
            )
        return principal

    return dependency


async def require_company_member(principal: Principal = Depends(get_current_user)) -> Principal:
    if principal.role == "candidate":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Candidates cannot access recruiter dashboards",
        )
    if principal.role not in COMPANY_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role for this resource",
        )
    if principal.is_platform_admin:
        return principal
    if not principal.memberships:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Awaiting company access",
        )
    return principal


async def require_company_admin(principal: Principal = Depends(require_company_member)) -> Principal:
    if principal.is_platform_admin:
        return principal
    if principal.role != "company_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company admin role required",
        )
    if not any(row.role in {"owner", "admin"} for row in principal.memberships):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company admin role required",
        )
    return principal
