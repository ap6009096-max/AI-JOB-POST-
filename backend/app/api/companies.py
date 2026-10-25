from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.company_scope import (
    can_access_company,
    company_ids,
    is_company_admin,
    is_platform_admin,
    require_current_company_id,
)
from app.core.security import Principal, require_company_admin, require_company_member
from app.db.repositories.users import UserRepository
from app.db.session import get_db
from app.schemas.auth import AddMemberIn, MemberOut
from app.schemas.company import CompanyProfileOut, CompanyProfilePatch, extras_patch, profile_from_company
from app.schemas.ranking import MatchingRunListOut
from app.services.auth import AuthService
from app.services.companies import CompanyService
from app.services.matching import MatchingService

router = APIRouter(prefix="/v1/companies", tags=["companies"])


def _current_company(principal: Principal, db: Session):
    company_id = require_current_company_id(principal)
    if not can_access_company(principal, company_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    company = CompanyService(db).get(company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


@router.get("/current", response_model=CompanyProfileOut)
def get_current_company(
    principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> CompanyProfileOut:
    company = _current_company(principal, db)
    return profile_from_company(company, can_edit=is_company_admin(principal))


@router.patch("/current", response_model=CompanyProfileOut)
def patch_current_company(
    body: CompanyProfilePatch,
    principal: Principal = Depends(require_company_admin),
    db: Session = Depends(get_db),
) -> CompanyProfileOut:
    company = _current_company(principal, db)
    updated = CompanyService(db).update(
        company,
        name=body.name,
        extras_patch=extras_patch(body),
    )
    db.commit()
    db.refresh(updated)
    return profile_from_company(updated, can_edit=True)


@router.get("/current/members", response_model=list[MemberOut])
def list_current_company_members(
    principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> list[MemberOut]:
    company = _current_company(principal, db)
    users = UserRepository(db)
    members: list[MemberOut] = []
    for row in CompanyService(db).list_members(company.id):
        member = users.get(row.user_id)
        members.append(
            MemberOut(
                user_id=row.user_id,
                email=member.email if member else "",
                role=row.role,
                company_id=row.company_id,
            )
        )
    return members


@router.post("/current/members", response_model=MemberOut)
def add_current_company_member(
    body: AddMemberIn,
    principal: Principal = Depends(require_company_admin),
    db: Session = Depends(get_db),
) -> MemberOut:
    admin_ids = [
        row.company_id
        for row in principal.memberships
        if principal.is_platform_admin or row.role in {"owner", "admin"}
    ]
    company_id = body.company_id or (admin_ids[0] if admin_ids else None)
    if company_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="company_id is required")
    if not principal.is_platform_admin and company_id not in admin_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of that company")
    membership = AuthService(db).add_company_member(
        admin=principal.user,
        email=body.email,
        company_id=company_id,
    )
    member = UserRepository(db).get(membership.user_id)
    return MemberOut(
        user_id=membership.user_id,
        email=member.email if member else body.email,
        role=membership.role,
        company_id=membership.company_id,
    )


@router.get("/current/matching-runs", response_model=list[MatchingRunListOut])
def list_current_matching_runs(
    principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> list[MatchingRunListOut]:
    ids = company_ids(principal)
    service = MatchingService(db)
    if is_platform_admin(principal) and not ids:
        runs = service.list(limit=100)
    else:
        runs = service.list_for_companies(ids)
    items: list[MatchingRunListOut] = []
    for run in runs:
        params = run.params if isinstance(run.params, dict) else {}
        job = run.job
        items.append(
            MatchingRunListOut(
                id=str(run.id),
                job_id=str(run.job_id),
                job_title=job.title if job is not None else "",
                track=run.track,  # type: ignore[arg-type]
                status=run.status,
                limit=int(params.get("limit") or 0),
                created_at=run.created_at.isoformat() if run.created_at else "",
            )
        )
    return items
