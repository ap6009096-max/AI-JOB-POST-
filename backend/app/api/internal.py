from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Environment, settings
from app.db.session import get_db
from app.schemas.candidate import ResumeCompleteIn
from app.services.candidates import CandidateService
from app.services.resume_jobs import complete_resume_job

router = APIRouter(prefix="/v1/internal", tags=["internal"])


def require_worker_secret(x_worker_secret: str = Header(default="", alias="X-Worker-Secret")) -> None:
    expected = settings.worker_shared_secret
    if expected is None:
        if settings.environment is Environment.LOCAL:
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Worker callback is not configured",
        )
    if x_worker_secret != expected.get_secret_value():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid worker secret")


@router.post("/worker/resume-complete")
def resume_complete(
    body: ResumeCompleteIn,
    db: Session = Depends(get_db),
    _: None = Depends(require_worker_secret),
) -> dict[str, str]:
    service = CandidateService(db)
    row = service.get(body.candidate_id)
    if row is None or row.user_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    candidate = service.get_by_user_id(row.user_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    complete_resume_job(
        service,
        candidate,
        status=body.status,
        text=body.text,
        parse_result=body.parse_result,
        error=body.error,
    )
    service.session.commit()
    return {"status": body.status}
