from contextlib import contextmanager
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import Principal, get_current_user
from app.db.models import AuditLog, User
from app.db.repositories.companies import CompanyRepository
from app.db.repositories.users import UserRepository
from app.db.session import get_db
from app.main import app
from app.schemas.gemini import MatchExplanation
from app.services.candidates import CandidateService
from app.services.embedding_service import candidate_embedding_text, job_embedding_text
from app.services.gemini_service import generate_match_explanation
from app.services.portal_ranking import portal_document

client = TestClient(app)

PUBLISHABLE_JOB = {
    "title": "Python Developer",
    "description": "Build hiring APIs with Python and FastAPI for recruiters in Bengaluru.",
    "location": "Bengaluru",
    "required_skills": ["Python"],
    "employment_type": "full_time",
    "technologies": ["FastAPI"],
    "education": "Bachelor in Computer Science",
    "salary_range": "12 LPA - 18 LPA",
}


@contextmanager
def acting_as(user: User, db_session):
    memberships = CompanyRepository(db_session).list_for_user(user.id)

    def override_user() -> Principal:
        return Principal(user=user, claims={}, memberships=memberships)

    def override_db():
        yield db_session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def _user(db_session, *, role: str, full_name: str = "Pat Recruiter") -> User:
    return UserRepository(db_session).create(
        email=f"{role}-{uuid4().hex[:8]}@example.com",
        full_name=full_name,
        role=role,
    )


def _company_with_member(db_session, *, role: str = "recruiter", membership_role: str = "recruiter", name: str = "Acme"):
    user = _user(db_session, role=role)
    company = CompanyRepository(db_session).create(name=name)
    CompanyRepository(db_session).add_member(company_id=company.id, user_id=user.id, role=membership_role)
    db_session.flush()
    return user, company


def _registered_candidate(db_session, *, name: str = "Asha Menon", skill: str = "Python"):
    user = _user(db_session, role="candidate", full_name=name)
    service = CandidateService(db_session)
    candidate = service.ensure_for_user(user.id)
    candidate.profile.headline = "Software Engineer"
    candidate.profile.summary = "Built FastAPI hiring tools with Python."
    extras = dict(candidate.profile.extras or {})
    extras["gender"] = "female"
    extras["race"] = "prefer_not_to_say"
    master = dict(extras.get("master_candidate") or {})
    master["gender"] = "female"
    master["summary"] = "Built FastAPI hiring tools with Python."
    extras["master_candidate"] = master
    candidate.profile.extras = extras
    if skill:
        service.create_skill(candidate.id, skill=skill)
    db_session.flush()
    return candidate


def _publish_job(http: TestClient) -> dict:
    created = http.post("/v1/jobs", json=PUBLISHABLE_JOB)
    assert created.status_code == 201
    published = http.post(f"/v1/jobs/{created.json()['id']}/publish")
    assert published.status_code == 200
    return published.json()


def test_portal_match_details_schema_and_audit(db_session) -> None:
    recruiter, _company = _company_with_member(db_session)
    asha = _registered_candidate(db_session)
    with acting_as(recruiter, db_session):
        job = _publish_job(client)
        ranked = client.post(f"/v1/jobs/{job['id']}/rank/portal?limit=10")
        details = client.get(f"/v1/jobs/{job['id']}/rank/portal/candidates/{asha.id}")
        internet = client.get(f"/v1/jobs/{job['id']}/rank/internet/candidates/{asha.id}")
    assert ranked.status_code == 200
    assert details.status_code == 200
    body = details.json()
    assert body["job_id"] == job["id"]
    assert body["candidate_id"] == str(asha.id)
    assert body["matching_run_id"] == ranked.json()["id"]
    assert body["source_type"] == "portal"
    assert body["source"] == "AI Job Post Portal"
    assert "skill_match_score" in body
    assert "project_match_score" in body
    assert "confidence_score" in body
    assert "gender" not in body
    assert "race" not in str(body)
    assert internet.status_code == 404
    actions = [row.action for row in db_session.scalars(select(AuditLog))]
    assert "ranking_run_completed" in actions
    assert "match_result_viewed" in actions


def test_internet_match_details_keeps_stub_reasoning(db_session) -> None:
    recruiter, _company = _company_with_member(db_session)
    asha = _registered_candidate(db_session)
    with acting_as(recruiter, db_session):
        job = _publish_job(client)
        ranked = client.post(f"/v1/jobs/{job['id']}/rank/internet?limit=10")
        candidate_id = ranked.json()["results"][0]["candidate_id"]
        details = client.get(f"/v1/jobs/{job['id']}/rank/internet/candidates/{candidate_id}")
        portal = client.get(f"/v1/jobs/{job['id']}/rank/portal/candidates/{candidate_id}")
    assert ranked.status_code == 200
    assert details.status_code == 200
    body = details.json()
    assert body["source_type"] == "internet"
    assert body["source_type"] != "portal"
    assert "Ranking engine" in body["match_reasoning"]
    assert body["candidate_id"] != str(asha.id)
    assert portal.status_code == 404


def test_match_details_candidate_403_and_other_company_404(db_session) -> None:
    recruiter, _company = _company_with_member(db_session)
    asha = _registered_candidate(db_session)
    with acting_as(recruiter, db_session):
        job = _publish_job(client)
        client.post(f"/v1/jobs/{job['id']}/rank/portal?limit=10")
    candidate = _user(db_session, role="candidate")
    with acting_as(candidate, db_session):
        forbidden = client.get(f"/v1/jobs/{job['id']}/rank/portal/candidates/{asha.id}")
    assert forbidden.status_code == 403
    other, _other_company = _company_with_member(
        db_session, role="company_admin", membership_role="owner", name="Beta"
    )
    with acting_as(other, db_session):
        missing = client.get(f"/v1/jobs/{job['id']}/rank/portal/candidates/{asha.id}")
    assert missing.status_code == 404


def test_match_details_missing_run_404(db_session) -> None:
    recruiter, _company = _company_with_member(db_session)
    asha = _registered_candidate(db_session)
    with acting_as(recruiter, db_session):
        job = _publish_job(client)
        missing = client.get(f"/v1/jobs/{job['id']}/rank/portal/candidates/{asha.id}")
    assert missing.status_code == 404


def test_protected_disclosures_stripped_from_embeddings_and_portal_document(db_session) -> None:
    asha = _registered_candidate(db_session)
    document = portal_document(asha)
    assert "gender" not in document
    assert "race" not in document
    assert "prefer_not_to_say" not in str(document)
    text = candidate_embedding_text(asha.profile.extras.get("master_candidate"))
    assert "female" not in text.lower()
    assert "prefer_not_to_say" not in text
    job_text = job_embedding_text(
        {
            "title": "Python Developer",
            "description": "Build APIs",
            "required_skills": ["Python"],
            "gender": "any",
            "race": "hidden",
        }
    )
    assert "any" not in job_text
    assert "hidden" not in job_text


def test_match_explanation_strips_demographics(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_generate(_model, prompt: str):
        captured["prompt"] = prompt
        return MatchExplanation()

    monkeypatch.setattr("app.services.gemini_service._generate", fake_generate)
    generate_match_explanation(
        {"title": "Python Developer", "gender": "female"},
        {"name": "Asha", "race": "prefer_not_to_say", "skills": ["Python"]},
        {"score": 0.8, "ethnicity": "hidden"},
    )
    prompt = captured["prompt"]
    assert "female" not in prompt
    assert "prefer_not_to_say" not in prompt
    assert "ethnicity" not in prompt
    assert "Python Developer" in prompt
