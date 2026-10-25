from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import Principal, require_company_member
from app.data.store import store
from app.db.session import get_db
from app.schemas.ranking import CandidateOut
from app.services.portal_ranking import get_portal_document, list_portal_documents
from app.services.sourcing import SourcingService

router = APIRouter(prefix="/v1/candidates", tags=["candidates"])


def _parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


@router.get("/portal", response_model=list[CandidateOut])
def list_portal(
    _principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> list[CandidateOut]:
    return [
        CandidateOut(id=item["id"], track="portal", profile=item)
        for item in list_portal_documents(db)
    ]


@router.get("/external", response_model=list[CandidateOut])
def list_external(_principal: Principal = Depends(require_company_member)) -> list[CandidateOut]:
    return [
        CandidateOut(id=item["id"], track="internet", profile=item["profile"])
        for item in store.list_external()
    ]


@router.get("/portal/{candidate_id}", response_model=CandidateOut)
def get_portal(
    candidate_id: str,
    _principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> CandidateOut:
    parsed = _parse_uuid(candidate_id)
    item = get_portal_document(db, parsed) if parsed is not None else None
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portal candidate not found")
    return CandidateOut(id=item["id"], track="portal", profile=item)


@router.get("/external/{candidate_id}", response_model=CandidateOut)
def get_external(
    candidate_id: str,
    _principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> CandidateOut:
    item = store.get_external(candidate_id)
    if item is not None:
        return CandidateOut(id=item["id"], track="internet", profile=item["profile"])
    parsed = _parse_uuid(candidate_id)
    row = SourcingService(db).get_external_candidate(parsed) if parsed is not None else None
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="External candidate not found")
    profile = dict(row.payload or {})
    return CandidateOut(id=str(row.id), track="internet", profile=profile)
