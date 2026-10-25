from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import _auth_user_id, get_current_claims, get_current_user, Principal
from app.db.repositories.companies import CompanyRepository
from app.db.session import get_db
from app.schemas.auth import BootstrapIn, MeOut, MembershipOut
from app.services.auth import AuthService

router = APIRouter(prefix="/v1", tags=["auth"])


def _me_out(user, memberships) -> MeOut:
    return MeOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        status=user.status,
        memberships=[
            MembershipOut(company_id=row.company_id, role=row.role) for row in memberships
        ],
    )


@router.get("/me", response_model=MeOut)
def me(principal: Principal = Depends(get_current_user)) -> MeOut:
    return _me_out(principal.user, principal.memberships)


@router.post("/auth/bootstrap", response_model=MeOut)
def bootstrap(
    body: BootstrapIn,
    claims: dict = Depends(get_current_claims),
    db: Session = Depends(get_db),
) -> MeOut:
    user = AuthService(db).bootstrap(
        auth_user_id=_auth_user_id(claims),
        email=str(claims.get("email") or ""),
        intent=body.intent,
        full_name=body.full_name,
        company_name=body.company_name,
    )
    memberships = CompanyRepository(db).list_for_user(user.id)
    return _me_out(user, memberships)
