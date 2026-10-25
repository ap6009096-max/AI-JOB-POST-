from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.company_scope import (
    can_access_company,
    company_ids,
    is_platform_admin,
    require_current_company_id,
)
from app.core.security import Principal, require_company_member
from app.data.store import store
from app.db.models import Job
from app.db.session import get_db
from app.graphs.job_graph import run_job_graph
from app.schemas.ranking import (
    EmbeddingMetaOut,
    JobCreateIn,
    JobGenerateIn,
    JobGenerateOut,
    JobOut,
    JobPatchIn,
    JobValidateOut,
    RankingRunOut,
    SimilarCandidateHit,
    MatchResultOut,
)
from app.services.embedding_service import job_embedding_text, metadata, retrieve, upsert_for_job
from app.services.gemini_service import (
    GeminiConfigError,
    GeminiError,
    GeminiValidationError,
    embed_text,
    generate_job_from_prompt,
    is_configured,
)
from app.services.job_document import (
    document_from_fields,
    document_from_job,
    fields_from_payload,
    persist_blob,
    ranking_dict,
    reserved_extras,
    validate_for_publish,
)
from app.services.jobs import JobService
from app.services.internet_sourcing import INTERNET_STORE_LIMIT, rank_internet_job, score_internet_candidates
from app.services.match_result import build_match_result, find_result_row
from app.services.matching import MatchingService
from app.services.audit import AuditService
from app.services.portal_ranking import PORTAL_STORE_LIMIT, rank_portal_job
from app.services.reddit_service import search_for_job
from app.services.vector_search import similar_candidates_for_job

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])
ALLOWED_LIMITS = {10, 20, 100}


def _parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


def _job_out(job: dict) -> JobOut:
    return JobOut.model_validate(job)


def _orm_job_dict(job: Job) -> dict[str, Any]:
    doc = document_from_job(job)
    extras = job.requirements if isinstance(job.requirements, dict) else {}
    pipeline = extras.get("job_pipeline")
    if isinstance(pipeline, dict):
        doc["pipeline"] = pipeline
    if job.embedding_id:
        doc["embedding_id"] = str(job.embedding_id)
    job_json = extras.get("job_json")
    doc["has_job_json"] = isinstance(job_json, dict) and bool(job_json)
    return doc


def _list_company_jobs(principal: Principal, db: Session) -> list[Job]:
    ids = company_ids(principal)
    service = JobService(db)
    if is_platform_admin(principal) and not ids:
        return service.list()
    return service.list_by_companies(ids)


def _postgres_job(job_id: str, principal: Principal, db: Session) -> Job | None:
    parsed = _parse_uuid(job_id)
    if parsed is None:
        return None
    job = JobService(db).get(parsed)
    if job is None:
        return None
    if not can_access_company(principal, job.company_id):
        return None
    return job


def resolve_job_dict(job_id: str, principal: Principal, db: Session) -> dict[str, Any]:
    stored = store.get_job(job_id)
    if stored is not None:
        return stored
    job = _postgres_job(job_id, principal, db)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return ranking_dict(job)


@router.get("", response_model=list[JobOut])
def list_jobs(
    principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> list[JobOut]:
    return [_job_out(_orm_job_dict(job)) for job in _list_company_jobs(principal, db)]


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(
    body: JobCreateIn,
    principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> JobOut:
    company_id = require_current_company_id(principal)
    fields = fields_from_payload(body.model_dump(exclude_unset=True))
    job = JobService(db).create(
        company_id=company_id,
        title=fields["title"],
        description=fields["description"],
        location=fields["location"],
        status="draft",
        requirements=persist_blob(fields),
    )
    db.commit()
    db.refresh(job)
    return _job_out(_orm_job_dict(job))


@router.post("/generate", response_model=JobGenerateOut)
def generate_job(
    body: JobGenerateIn,
    _principal: Principal = Depends(require_company_member),
) -> JobGenerateOut:
    try:
        generated = generate_job_from_prompt(body.prompt)
    except GeminiConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except GeminiValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except GeminiError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    fields = fields_from_payload(generated.model_dump())
    doc = document_from_fields(fields, status="draft")
    errors = validate_for_publish(doc)
    return JobGenerateOut(job=_job_out(doc), valid=not errors, errors=errors)


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: str,
    principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> JobOut:
    stored = store.get_job(job_id)
    if stored is not None:
        return _job_out(stored)
    job = _postgres_job(job_id, principal, db)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return _job_out(_orm_job_dict(job))


def _require_owned_job(job_id: str, principal: Principal, db: Session) -> Job:
    job = _postgres_job(job_id, principal, db)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


def _require_published_job(job_id: str, principal: Principal, db: Session) -> Job:
    job = _require_owned_job(job_id, principal, db)
    if job.status != "open":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Publish the job first")
    return job


def _job_has_json(job: Job) -> bool:
    extras = job.requirements if isinstance(job.requirements, dict) else {}
    job_json = extras.get("job_json")
    return isinstance(job_json, dict) and bool(job_json)


def _require_searchable_job(job: Job) -> Job:
    if job.status == "open" or _job_has_json(job):
        return job
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run the job pipeline first")


def _require_rank_limit(limit: int) -> int:
    if limit not in ALLOWED_LIMITS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="limit must be 10, 20, or 100",
        )
    return limit


def _match_details(
    job_id: str,
    candidate_id: str,
    track: str,
    principal: Principal,
    db: Session,
) -> MatchResultOut:
    job = _require_owned_job(job_id, principal, db)
    run = MatchingService(db).latest_for_job(job.id, track)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match result not found")
    params = run.params if isinstance(run.params, dict) else {}
    row = find_result_row(list(params.get("results") or []), candidate_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match result not found")
    document = build_match_result(
        job_id=str(job.id),
        matching_run_id=str(run.id),
        source_type=track,  # type: ignore[arg-type]
        row=row,
    )
    if document["source_type"] != track:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match result not found")
    AuditService(db).create(
        action="match_result_viewed",
        entity_type="matching_run",
        actor_user_id=principal.user.id,
        entity_id=run.id,
        metadata={
            "job_id": str(job.id),
            "candidate_id": candidate_id,
            "track": track,
            "source": document["source"],
        },
    )
    db.commit()
    return MatchResultOut.model_validate(document)


@router.patch("/{job_id}", response_model=JobOut)
def patch_job(
    job_id: str,
    body: JobPatchIn,
    principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> JobOut:
    job = _require_owned_job(job_id, principal, db)
    existing = document_from_job(job)
    fields = fields_from_payload(body.model_dump(exclude_unset=True), existing=existing)
    updated = JobService(db).update(
        job,
        title=fields["title"],
        description=fields["description"],
        location=fields["location"],
        requirements=persist_blob(fields, extras=reserved_extras(job.requirements)),
    )
    db.commit()
    db.refresh(updated)
    return _job_out(_orm_job_dict(updated))


@router.post("/{job_id}/pipeline", response_model=JobOut)
def run_job_pipeline(
    job_id: str,
    principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> JobOut:
    job = _require_owned_job(job_id, principal, db)
    run_job_graph(db, job)
    db.commit()
    db.refresh(job)
    return _job_out(_orm_job_dict(job))


@router.get("/{job_id}/embedding", response_model=EmbeddingMetaOut)
def get_job_embedding(
    job_id: str,
    principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> EmbeddingMetaOut:
    job = _require_owned_job(job_id, principal, db)
    if job.embedding_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job embedding not found")
    row = retrieve(db, job.embedding_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job embedding not found")
    return EmbeddingMetaOut.model_validate(metadata(row))


@router.post("/{job_id}/embedding", response_model=EmbeddingMetaOut)
def refresh_job_embedding(
    job_id: str,
    principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> EmbeddingMetaOut:
    job = _require_owned_job(job_id, principal, db)
    result = upsert_for_job(db, job)
    if result.row is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini is not configured. Set GOOGLE_CLOUD_PROJECT for Vertex AI.",
        )
    db.commit()
    db.refresh(job)
    return EmbeddingMetaOut.model_validate(metadata(result.row, cached=result.cached))


@router.post("/{job_id}/similar-candidates", response_model=list[SimilarCandidateHit])
def similar_job_candidates(
    job_id: str,
    limit: int = Query(default=10),
    principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> list[SimilarCandidateHit]:
    job = _require_owned_job(job_id, principal, db)
    if job.embedding_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Create a job embedding before searching.",
        )
    hits = similar_candidates_for_job(db, job, limit=max(1, min(limit, 100)))
    return [SimilarCandidateHit.model_validate(item) for item in hits]


@router.post("/{job_id}/validate", response_model=JobValidateOut)
def validate_job(
    job_id: str,
    principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> JobValidateOut:
    job = _require_owned_job(job_id, principal, db)
    errors = validate_for_publish(document_from_job(job))
    return JobValidateOut(valid=not errors, errors=errors)


@router.post("/{job_id}/publish", response_model=JobOut)
def publish_job(
    job_id: str,
    principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> JobOut:
    job = _require_owned_job(job_id, principal, db)
    errors = validate_for_publish(document_from_job(job))
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"errors": errors})
    extras = job.requirements if isinstance(job.requirements, dict) else {}
    pipeline = extras.get("job_pipeline") if isinstance(extras.get("job_pipeline"), dict) else {}
    if str(pipeline.get("status") or "") == "validation_failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": ["Fix pipeline validation errors before publishing."]},
        )
    job_json = extras.get("job_json")
    if not isinstance(job_json, dict) or not job_json:
        run_job_graph(db, job)
        db.flush()
        extras = job.requirements if isinstance(job.requirements, dict) else {}
        job_json = extras.get("job_json")
        pipeline = extras.get("job_pipeline") if isinstance(extras.get("job_pipeline"), dict) else {}
        if not isinstance(job_json, dict) or not job_json:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errors": ["Run the job pipeline to create job.json before publishing."]},
            )
        if str(pipeline.get("status") or "") == "validation_failed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errors": ["Fix pipeline validation errors before publishing."]},
            )
    if job.embedding_id is None:
        upsert_for_job(db, job)
    updated = JobService(db).update(job, status="open")
    db.commit()
    db.refresh(updated)
    return _job_out(_orm_job_dict(updated))


def _ranking_out_from_store(run: dict) -> RankingRunOut:
    return RankingRunOut.model_validate(run)


def _ranking_out_from_matching(run, results: list[dict], limit: int) -> RankingRunOut:
    params = run.params if isinstance(run.params, dict) else {}
    return RankingRunOut(
        id=str(run.id),
        job_id=str(run.job_id),
        track=run.track,
        limit=limit,
        results=results,
        created_at=run.created_at.isoformat() if run.created_at else "",
        skipped=list(params.get("skipped") or []),
        sources=list(params.get("sources") or []),
    )


def _rank_internet_external(job: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    reddit_hits = search_for_job(job)
    store.merge_reddit_externals(reddit_hits)
    job_vector: list[float] | None = None
    snippet = job_embedding_text(job)
    if snippet.strip() and is_configured():
        try:
            job_vector = embed_text(snippet)
        except Exception:
            job_vector = None
    return score_internet_candidates(job, store.list_external(), limit, job_vector=job_vector)


@router.post("/{job_id}/rank/portal", response_model=RankingRunOut)
def rank_portal(
    job_id: str,
    limit: int = Query(default=10),
    principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> RankingRunOut:
    _require_rank_limit(limit)
    job = _require_published_job(job_id, principal, db)
    results, run = rank_portal_job(db, job)
    AuditService(db).create(
        action="ranking_run_completed",
        entity_type="matching_run",
        actor_user_id=principal.user.id,
        entity_id=run.id,
        metadata={"job_id": str(job.id), "track": "portal"},
    )
    db.commit()
    db.refresh(run)
    return _ranking_out_from_matching(run, results, PORTAL_STORE_LIMIT)


@router.get("/{job_id}/rank/portal/latest", response_model=RankingRunOut)
def get_latest_portal_rank(
    job_id: str,
    principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> RankingRunOut:
    job = _require_owned_job(job_id, principal, db)
    run = MatchingService(db).latest_for_job(job.id, "portal")
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ranking run not found")
    params = run.params if isinstance(run.params, dict) else {}
    return RankingRunOut(
        id=str(run.id),
        job_id=str(run.job_id),
        track="portal",
        limit=int(params.get("limit") or PORTAL_STORE_LIMIT),
        results=params.get("results") or [],
        created_at=run.created_at.isoformat() if run.created_at else "",
        skipped=list(params.get("skipped") or []),
        sources=list(params.get("sources") or []),
    )


@router.post("/{job_id}/rank/internet", response_model=RankingRunOut)
def rank_internet(
    job_id: str,
    limit: int = Query(default=10),
    principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> RankingRunOut:
    _require_rank_limit(limit)
    persisted = _postgres_job(job_id, principal, db)
    if persisted is not None:
        _require_searchable_job(persisted)
        results, run = rank_internet_job(db, persisted)
        AuditService(db).create(
            action="ranking_run_completed",
            entity_type="matching_run",
            actor_user_id=principal.user.id,
            entity_id=run.id,
            metadata={"job_id": str(persisted.id), "track": "internet"},
        )
        db.commit()
        db.refresh(run)
        return _ranking_out_from_matching(run, results, INTERNET_STORE_LIMIT)
    stored = store.get_job(job_id)
    if stored is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    results = _rank_internet_external(stored, INTERNET_STORE_LIMIT)
    run = store.save_run(job_id, "internet", INTERNET_STORE_LIMIT, results)
    return _ranking_out_from_store(run)


@router.get("/{job_id}/rank/internet/latest", response_model=RankingRunOut)
def get_latest_internet_rank(
    job_id: str,
    principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> RankingRunOut:
    job = _require_owned_job(job_id, principal, db)
    run = MatchingService(db).latest_for_job(job.id, "internet")
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ranking run not found")
    params = run.params if isinstance(run.params, dict) else {}
    return RankingRunOut(
        id=str(run.id),
        job_id=str(run.job_id),
        track="internet",
        limit=int(params.get("limit") or INTERNET_STORE_LIMIT),
        results=params.get("results") or [],
        created_at=run.created_at.isoformat() if run.created_at else "",
        skipped=list(params.get("skipped") or []),
        sources=list(params.get("sources") or []),
    )


@router.get("/{job_id}/rank/portal/candidates/{candidate_id}", response_model=MatchResultOut)
def get_portal_match_details(
    job_id: str,
    candidate_id: str,
    principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> MatchResultOut:
    return _match_details(job_id, candidate_id, "portal", principal, db)


@router.get("/{job_id}/rank/internet/candidates/{candidate_id}", response_model=MatchResultOut)
def get_internet_match_details(
    job_id: str,
    candidate_id: str,
    principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> MatchResultOut:
    return _match_details(job_id, candidate_id, "internet", principal, db)


@router.get("/{job_id}/rank/{run_id}", response_model=RankingRunOut)
def get_rank_run(
    job_id: str,
    run_id: str,
    principal: Principal = Depends(require_company_member),
    db: Session = Depends(get_db),
) -> RankingRunOut:
    stored = store.get_run(job_id, run_id)
    if stored is not None:
        return _ranking_out_from_store(stored)
    parsed = _parse_uuid(run_id)
    if parsed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ranking run not found")
    run = MatchingService(db).get(parsed)
    if run is None or str(run.job_id) != job_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ranking run not found")
    job = JobService(db).get(run.job_id)
    if job is None or not can_access_company(principal, job.company_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ranking run not found")
    params = run.params if isinstance(run.params, dict) else {}
    return RankingRunOut(
        id=str(run.id),
        job_id=str(run.job_id),
        track=run.track,  # type: ignore[arg-type]
        limit=int(params.get("limit") or 0),
        results=params.get("results") or [],
        created_at=run.created_at.isoformat() if run.created_at else "",
        skipped=list(params.get("skipped") or []),
        sources=list(params.get("sources") or []),
    )
