from uuid import UUID

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.security import Principal, require_roles
from app.db.models import (
    Candidate,
    CandidateCertification,
    CandidateEducation,
    CandidateExperience,
    CandidateProject,
    CandidateSkill,
    CandidateSource,
)
from app.db.session import get_db
from app.schemas.candidate import (
    AchievementIn,
    AchievementOut,
    AchievementPatch,
    CandidateGraphOut,
    CertificationIn,
    CertificationOut,
    CertificationPatch,
    EducationIn,
    EducationOut,
    EducationPatch,
    ExperienceIn,
    ExperienceOut,
    ExperiencePatch,
    JobRecommendationOut,
    LinkIn,
    LinkOut,
    LinkPatch,
    PersonalPatch,
    PreferencesPut,
    ProfessionalLinksPut,
    ProfilePatch,
    ProfileVersionDetailOut,
    ProjectIn,
    ProjectOut,
    ProjectPatch,
    ResumeParseApplyIn,
    ResumePut,
    SettingsPatch,
    SkillIn,
    SkillOut,
    SkillPatch,
    TechnologyIn,
    TechnologyOut,
    TechnologyPatch,
)
from app.db.repositories import ProfileVersionRepository
from app.graphs.candidate_graph import run_candidate_graph
from app.schemas.ranking import EmbeddingMetaOut
from app.services.candidates import CandidateService
from app.services.embedding_service import metadata, retrieve, upsert_for_candidate
from app.services.recommendations import list_job_recommendations
from app.services.resume_files import ResumeFileError
from app.services.resume_jobs import apply_parse_result, parse_pasted_resume, upload_resume
from app.services.resume_storage import ResumeStorageError
from app.services.source_service import analyze_candidate_sources, link_payload

router = APIRouter(prefix="/v1/me/candidate", tags=["candidate-profile"])
require_candidate = require_roles("candidate")


def _own_candidate(
    principal: Principal = Depends(require_candidate),
    db: Session = Depends(get_db),
) -> tuple[Principal, Candidate, CandidateService]:
    service = CandidateService(db)
    candidate = service.ensure_for_user(principal.user.id)
    return principal, candidate, service


def _graph(principal: Principal, candidate: Candidate, service: CandidateService) -> CandidateGraphOut:
    payload = service.graph_payload(candidate, principal.user)
    return CandidateGraphOut.model_validate(payload)


def _owned_or_404(service: CandidateService, model: type, row_id: UUID, candidate_id: UUID):
    row = service.get_owned(model, row_id, candidate_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return row


@router.get("", response_model=CandidateGraphOut)
def get_candidate_graph(
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> CandidateGraphOut:
    principal, candidate, service = ctx
    return _graph(principal, candidate, service)


@router.patch("/profile", response_model=CandidateGraphOut)
def patch_profile(
    body: ProfilePatch,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> CandidateGraphOut:
    principal, candidate, service = ctx
    service.update_profile(candidate, **body.model_dump(exclude_unset=True))
    service.session.commit()
    return _graph(principal, service.ensure_for_user(principal.user.id), service)


@router.patch("/personal", response_model=CandidateGraphOut)
def patch_personal(
    body: PersonalPatch,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> CandidateGraphOut:
    principal, candidate, service = ctx
    service.update_personal(principal.user, candidate, body.model_dump(exclude_unset=True))
    service.session.commit()
    return _graph(principal, service.ensure_for_user(principal.user.id), service)


@router.put("/resume", response_model=CandidateGraphOut)
def put_resume(
    body: ResumePut,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> CandidateGraphOut:
    principal, candidate, service = ctx
    service.update_resume(candidate, text=body.text, url=body.url)
    parse_pasted_resume(service, candidate, body.text)
    service.session.commit()
    return _graph(principal, service.ensure_for_user(principal.user.id), service)


@router.post("/resume/upload", response_model=CandidateGraphOut)
async def upload_resume_file(
    file: UploadFile = File(...),
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> CandidateGraphOut:
    principal, candidate, service = ctx
    data = await file.read()
    try:
        upload_resume(
            service,
            candidate,
            data=data,
            filename=file.filename,
            declared_type=file.content_type,
        )
    except ResumeFileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ResumeStorageError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    service.session.commit()
    return _graph(principal, service.ensure_for_user(principal.user.id), service)


@router.post("/resume/apply", response_model=CandidateGraphOut)
def apply_resume_parse(
    body: ResumeParseApplyIn | None = Body(default=None),
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> CandidateGraphOut:
    principal, candidate, service = ctx
    try:
        apply_parse_result(
            service,
            principal.user,
            candidate,
            approved=None if body is None else body.model_dump(),
        )
    except ResumeFileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    service.session.commit()
    return _graph(principal, service.ensure_for_user(principal.user.id), service)


@router.put("/preferences", response_model=CandidateGraphOut)
def put_preferences(
    body: PreferencesPut,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> CandidateGraphOut:
    principal, candidate, service = ctx
    service.update_preferences(candidate, body.model_dump(exclude_none=True))
    service.session.commit()
    return _graph(principal, service.ensure_for_user(principal.user.id), service)


@router.patch("/settings", response_model=CandidateGraphOut)
def patch_settings(
    body: SettingsPatch,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> CandidateGraphOut:
    principal, candidate, service = ctx
    service.update_settings(
        principal.user,
        candidate,
        full_name=body.full_name,
        status=body.status,
    )
    service.session.commit()
    return _graph(principal, service.ensure_for_user(principal.user.id), service)


@router.put("/professional-links", response_model=CandidateGraphOut)
def put_professional_links(
    body: ProfessionalLinksPut,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> CandidateGraphOut:
    principal, candidate, service = ctx
    service.upsert_professional_links(
        candidate,
        linkedin=body.linkedin,
        github=body.github,
        portfolio=body.portfolio,
        website=body.website,
        other=[item.model_dump() for item in body.other],
    )
    service.session.commit()
    return _graph(principal, service.ensure_for_user(principal.user.id), service)


@router.post("/sources/analyze", response_model=CandidateGraphOut)
def analyze_professional_sources(
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> CandidateGraphOut:
    principal, candidate, service = ctx
    if not any((row.url or "").strip() for row in candidate.sources):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Save professional links before analyzing them.",
        )
    analyze_candidate_sources(candidate)
    service.session.commit()
    return _graph(principal, service.ensure_for_user(principal.user.id), service)


@router.post("/pipeline", response_model=CandidateGraphOut)
def run_profile_pipeline(
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> CandidateGraphOut:
    principal, candidate, service = ctx
    run_candidate_graph(service.session, candidate)
    service.session.commit()
    return _graph(principal, service.ensure_for_user(principal.user.id), service)


@router.post("/finalize", response_model=CandidateGraphOut)
def finalize_candidate_profile(
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> CandidateGraphOut:
    principal, candidate, service = ctx
    if any((row.url or "").strip() for row in candidate.sources):
        analyze_candidate_sources(candidate)
    run_candidate_graph(service.session, candidate)
    service.session.commit()
    return _graph(principal, service.ensure_for_user(principal.user.id), service)


@router.get("/recommendations", response_model=list[JobRecommendationOut])
def list_candidate_recommendations(
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> list[JobRecommendationOut]:
    _principal, candidate, service = ctx
    rows = list_job_recommendations(service.session, candidate)
    return [JobRecommendationOut.model_validate(row) for row in rows]


@router.get("/embedding", response_model=EmbeddingMetaOut)
def get_candidate_embedding(
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> EmbeddingMetaOut:
    _principal, candidate, service = ctx
    profile = candidate.profile
    if profile is None or profile.embedding_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate embedding not found")
    row = retrieve(service.session, profile.embedding_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate embedding not found")
    return EmbeddingMetaOut.model_validate(metadata(row))


@router.post("/embedding", response_model=EmbeddingMetaOut)
def refresh_candidate_embedding(
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> EmbeddingMetaOut:
    _principal, candidate, service = ctx
    profile = candidate.profile
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate embedding not found")
    extras = profile.extras if isinstance(profile.extras, dict) else {}
    master = extras.get("master_candidate") if isinstance(extras.get("master_candidate"), dict) else {}
    result = upsert_for_candidate(service.session, profile, master)
    if result.row is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini is not configured. Set GOOGLE_CLOUD_PROJECT for Vertex AI.",
        )
    service.session.commit()
    return EmbeddingMetaOut.model_validate(metadata(result.row, cached=result.cached))


@router.get("/profile-versions/{version}", response_model=ProfileVersionDetailOut)
def get_profile_version(
    version: int,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> ProfileVersionDetailOut:
    _principal, candidate, service = ctx
    row = ProfileVersionRepository(service.session).get(candidate.id, version)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile version not found")
    return ProfileVersionDetailOut(
        id=row.id,
        version=row.version,
        source=row.source,
        change_summary=row.change_summary or {},
        created_at=row.created_at.isoformat() if row.created_at else "",
        snapshot=row.snapshot or {},
    )


@router.post("/experience", response_model=ExperienceOut)
def add_experience(
    body: ExperienceIn,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> ExperienceOut:
    _principal, candidate, service = ctx
    row = service.create_experience(candidate.id, **body.model_dump())
    service.session.commit()
    return ExperienceOut.model_validate(row)


@router.patch("/experience/{row_id}", response_model=ExperienceOut)
def patch_experience(
    row_id: UUID,
    body: ExperiencePatch,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> ExperienceOut:
    _principal, candidate, service = ctx
    row = _owned_or_404(service, CandidateExperience, row_id, candidate.id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    service.session.commit()
    return ExperienceOut.model_validate(row)


@router.delete("/experience/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experience(
    row_id: UUID,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> None:
    _principal, candidate, service = ctx
    if not service.delete_owned(CandidateExperience, row_id, candidate.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    service.session.commit()


@router.post("/education", response_model=EducationOut)
def add_education(
    body: EducationIn,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> EducationOut:
    _principal, candidate, service = ctx
    row = service.create_education(candidate.id, **body.model_dump())
    service.session.commit()
    return EducationOut.model_validate(row)


@router.patch("/education/{row_id}", response_model=EducationOut)
def patch_education(
    row_id: UUID,
    body: EducationPatch,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> EducationOut:
    _principal, candidate, service = ctx
    row = _owned_or_404(service, CandidateEducation, row_id, candidate.id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    service.session.commit()
    return EducationOut.model_validate(row)


@router.delete("/education/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_education(
    row_id: UUID,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> None:
    _principal, candidate, service = ctx
    if not service.delete_owned(CandidateEducation, row_id, candidate.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    service.session.commit()


@router.post("/skills", response_model=SkillOut)
def add_skill(
    body: SkillIn,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> SkillOut:
    _principal, candidate, service = ctx
    row = service.create_skill(candidate.id, **body.model_dump())
    service.session.commit()
    return SkillOut.model_validate(row)


@router.patch("/skills/{row_id}", response_model=SkillOut)
def patch_skill(
    row_id: UUID,
    body: SkillPatch,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> SkillOut:
    _principal, candidate, service = ctx
    row = _owned_or_404(service, CandidateSkill, row_id, candidate.id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    service.session.commit()
    return SkillOut.model_validate(row)


@router.delete("/skills/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(
    row_id: UUID,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> None:
    _principal, candidate, service = ctx
    if not service.delete_owned(CandidateSkill, row_id, candidate.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    service.session.commit()


@router.post("/projects", response_model=ProjectOut)
def add_project(
    body: ProjectIn,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> ProjectOut:
    _principal, candidate, service = ctx
    row = service.create_project(candidate.id, **body.model_dump())
    service.session.commit()
    return ProjectOut.model_validate(row)


@router.patch("/projects/{row_id}", response_model=ProjectOut)
def patch_project(
    row_id: UUID,
    body: ProjectPatch,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> ProjectOut:
    _principal, candidate, service = ctx
    row = _owned_or_404(service, CandidateProject, row_id, candidate.id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    service.session.commit()
    return ProjectOut.model_validate(row)


@router.delete("/projects/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    row_id: UUID,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> None:
    _principal, candidate, service = ctx
    if not service.delete_owned(CandidateProject, row_id, candidate.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    service.session.commit()


@router.post("/certifications", response_model=CertificationOut)
def add_certification(
    body: CertificationIn,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> CertificationOut:
    _principal, candidate, service = ctx
    row = service.create_certification(candidate.id, **body.model_dump())
    service.session.commit()
    return CertificationOut.model_validate(row)


@router.patch("/certifications/{row_id}", response_model=CertificationOut)
def patch_certification(
    row_id: UUID,
    body: CertificationPatch,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> CertificationOut:
    _principal, candidate, service = ctx
    row = _owned_or_404(service, CandidateCertification, row_id, candidate.id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    service.session.commit()
    return CertificationOut.model_validate(row)


@router.delete("/certifications/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_certification(
    row_id: UUID,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> None:
    _principal, candidate, service = ctx
    if not service.delete_owned(CandidateCertification, row_id, candidate.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    service.session.commit()


@router.post("/links", response_model=LinkOut)
def add_link(
    body: LinkIn,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> LinkOut:
    _principal, candidate, service = ctx
    row = service.create_link(candidate.id, **body.model_dump())
    service.session.commit()
    return LinkOut.model_validate(link_payload(row))


@router.patch("/links/{row_id}", response_model=LinkOut)
def patch_link(
    row_id: UUID,
    body: LinkPatch,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> LinkOut:
    _principal, candidate, service = ctx
    row = _owned_or_404(service, CandidateSource, row_id, candidate.id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    service.session.commit()
    return LinkOut.model_validate(link_payload(row))


@router.delete("/links/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(
    row_id: UUID,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> None:
    _principal, candidate, service = ctx
    if not service.delete_owned(CandidateSource, row_id, candidate.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    service.session.commit()


@router.post("/technologies", response_model=TechnologyOut)
def add_technology(
    body: TechnologyIn,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> TechnologyOut:
    _principal, candidate, service = ctx
    row = service.create_technology(candidate, **body.model_dump())
    service.session.commit()
    return TechnologyOut.model_validate(row)


@router.patch("/technologies/{row_id}", response_model=TechnologyOut)
def patch_technology(
    row_id: UUID,
    body: TechnologyPatch,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> TechnologyOut:
    _principal, candidate, service = ctx
    row = service.update_technology(candidate, row_id, body.model_dump(exclude_unset=True))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    service.session.commit()
    return TechnologyOut.model_validate(row)


@router.delete("/technologies/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_technology(
    row_id: UUID,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> None:
    _principal, candidate, service = ctx
    if not service.delete_technology(candidate, row_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    service.session.commit()


@router.post("/achievements", response_model=AchievementOut)
def add_achievement(
    body: AchievementIn,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> AchievementOut:
    _principal, candidate, service = ctx
    row = service.create_achievement(candidate, **body.model_dump())
    service.session.commit()
    return AchievementOut.model_validate(row)


@router.patch("/achievements/{row_id}", response_model=AchievementOut)
def patch_achievement(
    row_id: UUID,
    body: AchievementPatch,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> AchievementOut:
    _principal, candidate, service = ctx
    row = service.update_achievement(candidate, row_id, body.model_dump(exclude_unset=True))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    service.session.commit()
    return AchievementOut.model_validate(row)


@router.delete("/achievements/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_achievement(
    row_id: UUID,
    ctx: tuple[Principal, Candidate, CandidateService] = Depends(_own_candidate),
) -> None:
    _principal, candidate, service = ctx
    if not service.delete_achievement(candidate, row_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    service.session.commit()
