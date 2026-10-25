from typing import Any
from uuid import UUID

from fastapi import HTTPException, status


def company_ids(principal: Any) -> list[UUID]:
    memberships = getattr(principal, "memberships", None) or []
    return [row.company_id for row in memberships]


def primary_company_id(principal: Any) -> UUID | None:
    ids = company_ids(principal)
    return ids[0] if ids else None


def is_platform_admin(principal: Any) -> bool:
    return bool(getattr(principal, "is_platform_admin", False))


def can_access_company(principal: Any, company_id: UUID) -> bool:
    if is_platform_admin(principal):
        return True
    return company_id in company_ids(principal)


def is_company_admin(principal: Any) -> bool:
    if is_platform_admin(principal):
        return True
    if getattr(principal, "role", None) != "company_admin":
        return False
    memberships = getattr(principal, "memberships", None) or []
    return any(row.role in {"owner", "admin"} for row in memberships)


def require_current_company_id(principal: Any) -> UUID:
    company_id = primary_company_id(principal)
    if company_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="company_id is required",
        )
    return company_id
