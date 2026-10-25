from contextlib import contextmanager
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import Principal, get_current_user
from app.db.models import User
from app.db.repositories.companies import CompanyRepository
from app.db.repositories.users import UserRepository
from app.db.session import get_db
from app.main import app

client = TestClient(app)


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


def _user(db_session, *, role: str, email: str | None = None) -> User:
    return UserRepository(db_session).create(
        email=email or f"{role}-{uuid4().hex[:8]}@example.com",
        full_name="Pat Recruiter",
        role=role,
    )


def _company_with_member(db_session, *, role: str, membership_role: str, name: str = "Acme"):
    user = _user(db_session, role=role)
    company = CompanyRepository(db_session).create(name=name)
    CompanyRepository(db_session).add_member(
        company_id=company.id, user_id=user.id, role=membership_role
    )
    db_session.flush()
    return user, company


def test_candidate_forbidden_on_company_jobs_and_runs(db_session) -> None:
    candidate = _user(db_session, role="candidate")
    with acting_as(candidate, db_session):
        profile = client.get("/v1/companies/current")
        patch = client.patch("/v1/companies/current", json={"industry": "Software"})
        created = client.post("/v1/jobs", json={"title": "Engineer"})
        runs = client.get("/v1/companies/current/matching-runs")
        jobs = client.get("/v1/jobs")
        patched_job = client.patch("/v1/jobs/00000000-0000-0000-0000-000000000001", json={"title": "X"})
        validated = client.post("/v1/jobs/00000000-0000-0000-0000-000000000001/validate")
        published = client.post("/v1/jobs/00000000-0000-0000-0000-000000000001/publish")
        generated = client.post(
            "/v1/jobs/generate",
            json={"prompt": "Create a Python Developer position in Patna for 0-2 years."},
        )
    assert profile.status_code == 403
    assert patch.status_code == 403
    assert created.status_code == 403
    assert runs.status_code == 403
    assert jobs.status_code == 403
    assert patched_job.status_code == 403
    assert validated.status_code == 403
    assert published.status_code == 403
    assert generated.status_code == 403
    assert "Candidates cannot access" in profile.json()["detail"]


def test_recruiter_can_get_profile_and_create_job_but_not_patch_profile(db_session) -> None:
    recruiter, company = _company_with_member(
        db_session, role="recruiter", membership_role="recruiter", name="Northwind"
    )
    with acting_as(recruiter, db_session):
        profile = client.get("/v1/companies/current")
        assert profile.status_code == 200
        body = profile.json()
        assert body["name"] == "Northwind"
        assert body["can_edit"] is False

        denied = client.patch("/v1/companies/current", json={"industry": "Software"})
        assert denied.status_code == 403

        created = client.post(
            "/v1/jobs",
            json={
                "title": "Platform Engineer",
                "description": "Build APIs",
                "location": "Bengaluru",
                "status": "open",
                "requirements": {"skills": ["Python"], "experience_years": 4, "keywords": ["api"]},
            },
        )
        assert created.status_code == 201
        job = created.json()
        assert job["title"] == "Platform Engineer"
        assert job["company_id"] == str(company.id)
        assert job["status"] == "draft"
        assert job["required_skills"] == ["Python"]

        listed = client.get("/v1/jobs")
        assert listed.status_code == 200
        assert [row["id"] for row in listed.json()] == [job["id"]]


def test_company_admin_can_patch_profile(db_session) -> None:
    admin, _company = _company_with_member(
        db_session, role="company_admin", membership_role="owner", name="Hire Co"
    )
    with acting_as(admin, db_session):
        patched = client.patch(
            "/v1/companies/current",
            json={
                "industry": "Software",
                "business_domain": "Recruiting",
                "description": "AI hiring",
                "location": "Bengaluru",
                "company_size": "51-200",
                "departments": ["Engineering", "People"],
                "hiring_domains": ["Backend"],
                "technologies": ["Python", "TypeScript"],
            },
        )
    assert patched.status_code == 200
    body = patched.json()
    assert body["can_edit"] is True
    assert body["industry"] == "Software"
    assert body["business_domain"] == "Recruiting"
    assert body["departments"] == ["Engineering", "People"]
    assert body["technologies"] == ["Python", "TypeScript"]


def test_company_cannot_read_another_company_job_or_runs(db_session) -> None:
    owner_a, company_a = _company_with_member(
        db_session, role="company_admin", membership_role="owner", name="Alpha"
    )
    owner_b, company_b = _company_with_member(
        db_session, role="company_admin", membership_role="owner", name="Beta"
    )

    with acting_as(owner_a, db_session):
        created = client.post(
            "/v1/jobs",
            json={
                "title": "Alpha Role",
                "description": "Build hiring APIs for the Alpha recruiting team with Python.",
                "location": "Bengaluru",
                "required_skills": ["Python"],
                "employment_type": "full_time",
            },
        )
        assert created.status_code == 201
        job_a = created.json()["id"]
        published = client.post(f"/v1/jobs/{job_a}/publish")
        assert published.status_code == 200
        ranked = client.post(f"/v1/jobs/{job_a}/rank/portal?limit=10")
        assert ranked.status_code == 200
        runs_a = client.get("/v1/companies/current/matching-runs")
        assert runs_a.status_code == 200
        assert len(runs_a.json()) == 1
        assert runs_a.json()[0]["job_id"] == job_a

    with acting_as(owner_b, db_session):
        listed = client.get("/v1/jobs")
        assert listed.status_code == 200
        assert listed.json() == []
        missing = client.get(f"/v1/jobs/{job_a}")
        assert missing.status_code == 404
        rank = client.post(f"/v1/jobs/{job_a}/rank/portal?limit=10")
        assert rank.status_code == 404
        runs = client.get("/v1/companies/current/matching-runs")
        assert runs.status_code == 200
        assert runs.json() == []
        created_b = client.post("/v1/jobs", json={"title": "Beta Role"})
        assert created_b.status_code == 201
        assert created_b.json()["company_id"] == str(company_b.id)

    with acting_as(owner_a, db_session):
        listed = client.get("/v1/jobs")
        assert listed.status_code == 200
        assert [row["id"] for row in listed.json()] == [job_a]
        assert all(row["company_id"] == str(company_a.id) for row in listed.json())


def test_recruiter_can_list_members_but_cannot_invite(db_session) -> None:
    recruiter, _company = _company_with_member(
        db_session, role="recruiter", membership_role="recruiter"
    )
    with acting_as(recruiter, db_session):
        members = client.get("/v1/companies/current/members")
        assert members.status_code == 200
        assert len(members.json()) == 1
        invite = client.post(
            "/v1/companies/current/members",
            json={"email": "new@example.com"},
        )
        assert invite.status_code == 403


def test_create_always_draft_even_if_client_sends_open(db_session) -> None:
    recruiter, _company = _company_with_member(db_session, role="recruiter", membership_role="recruiter")
    with acting_as(recruiter, db_session):
        created = client.post("/v1/jobs", json={"title": "Draft Role", "status": "open"})
    assert created.status_code == 201
    assert created.json()["status"] == "draft"


def test_recruiter_can_patch_own_job_other_company_gets_404(db_session) -> None:
    recruiter_a, _company_a = _company_with_member(
        db_session, role="recruiter", membership_role="recruiter", name="Alpha"
    )
    recruiter_b, _company_b = _company_with_member(
        db_session, role="recruiter", membership_role="recruiter", name="Beta"
    )
    with acting_as(recruiter_a, db_session):
        created = client.post("/v1/jobs", json={"title": "Alpha Role"})
        job_id = created.json()["id"]
        patched = client.patch(
            f"/v1/jobs/{job_id}",
            json={"description": "Own APIs", "required_skills": ["Python"]},
        )
        assert patched.status_code == 200
        assert patched.json()["description"] == "Own APIs"
        assert patched.json()["required_skills"] == ["Python"]
        assert patched.json()["status"] == "draft"
        assert patched.json()["requirements"]["skills"] == ["Python"]

    with acting_as(recruiter_b, db_session):
        missing = client.patch(f"/v1/jobs/{job_id}", json={"title": "Hijack"})
        assert missing.status_code == 404
        validate = client.post(f"/v1/jobs/{job_id}/validate")
        assert validate.status_code == 404
        publish = client.post(f"/v1/jobs/{job_id}/publish")
        assert publish.status_code == 404


def test_validate_and_publish_require_complete_job(db_session) -> None:
    recruiter, _company = _company_with_member(db_session, role="recruiter", membership_role="recruiter")
    with acting_as(recruiter, db_session):
        created = client.post("/v1/jobs", json={"title": "Incomplete"})
        job_id = created.json()["id"]
        invalid = client.post(f"/v1/jobs/{job_id}/validate")
        assert invalid.status_code == 200
        body = invalid.json()
        assert body["valid"] is False
        assert any("Description" in error for error in body["errors"])
        assert any("skill" in error.lower() for error in body["errors"])

        denied = client.post(f"/v1/jobs/{job_id}/publish")
        assert denied.status_code == 400
        still_draft = client.get(f"/v1/jobs/{job_id}")
        assert still_draft.json()["status"] == "draft"

        patched = client.patch(
            f"/v1/jobs/{job_id}",
            json={
                "description": "Build hiring APIs",
                "location": "Bengaluru",
                "required_skills": ["Python", "FastAPI"],
                "employment_type": "full_time",
                "technologies": ["PostgreSQL"],
                "seniority": "senior",
            },
        )
        assert patched.status_code == 200
        valid = client.post(f"/v1/jobs/{job_id}/validate")
        assert valid.status_code == 200
        assert valid.json()["valid"] is True
        assert valid.json()["errors"] == []

        published = client.post(f"/v1/jobs/{job_id}/publish")
        assert published.status_code == 200
        assert published.json()["status"] == "open"
        assert published.json()["requirements"]["skills"] == ["Python", "FastAPI"]
        assert "PostgreSQL" in published.json()["requirements"]["keywords"]


EXAMPLE_JOB_PROMPT = (
    "Create a Python Developer position in Patna for 0–2 years of experience "
    "requiring Python, Django, SQL and basic AWS."
)


def _generated_python_job():
    from app.schemas.gemini import GeneratedJob, GeneratedJobExperience

    return GeneratedJob(
        title="Python Developer",
        description="Build backend services with Python and Django in Patna.",
        required_skills=["Python", "Django", "SQL", "AWS"],
        preferred_skills=["REST APIs"],
        experience=GeneratedJobExperience(years=2, text="0-2 years"),
        education="Bachelor's in Computer Science or equivalent",
        technologies=["Python", "Django", "SQL", "AWS"],
        responsibilities=["Build APIs", "Write tests"],
        location="Patna",
        salary_range="₹4–8 LPA",
        employment_type="full_time",
        seniority="junior",
        certifications=[],
        openings=1,
        deadline="",
    )


def test_generate_job_returns_draft_json_without_persisting(db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.api.jobs.generate_job_from_prompt", lambda _prompt: _generated_python_job())
    recruiter, _company = _company_with_member(db_session, role="recruiter", membership_role="recruiter")
    with acting_as(recruiter, db_session):
        before = client.get("/v1/jobs")
        response = client.post("/v1/jobs/generate", json={"prompt": EXAMPLE_JOB_PROMPT})
        after = client.get("/v1/jobs")
    assert response.status_code == 200
    body = response.json()
    job = body["job"]
    assert job["status"] == "draft"
    assert job["id"] == ""
    assert "Python Developer" in job["title"]
    assert job["location"] == "Patna"
    assert "Python" in job["required_skills"]
    assert "Django" in job["required_skills"]
    assert "SQL" in job["required_skills"]
    assert job["experience"]["years"] == 2
    assert job["requirements"]["skills"] == job["required_skills"]
    assert body["valid"] is True
    assert before.json() == after.json() == []


def test_generate_job_unconfigured_gemini_is_503(db_session, monkeypatch) -> None:
    from app.services.gemini_service import GeminiConfigError

    def boom(_prompt: str):
        raise GeminiConfigError("Gemini is not configured. Set GEMINI_API_KEY for local development")

    monkeypatch.setattr("app.api.jobs.generate_job_from_prompt", boom)
    recruiter, _company = _company_with_member(db_session, role="recruiter", membership_role="recruiter")
    with acting_as(recruiter, db_session):
        response = client.post("/v1/jobs/generate", json={"prompt": EXAMPLE_JOB_PROMPT})
    assert response.status_code == 503


def test_generate_job_quota_exceeded_is_503(db_session, monkeypatch) -> None:
    from app.services.gemini_service import GeminiQuotaError

    def boom(_prompt: str):
        raise GeminiQuotaError()

    monkeypatch.setattr("app.api.jobs.generate_job_from_prompt", boom)
    recruiter, _company = _company_with_member(db_session, role="recruiter", membership_role="recruiter")
    with acting_as(recruiter, db_session):
        response = client.post("/v1/jobs/generate", json={"prompt": EXAMPLE_JOB_PROMPT})
    assert response.status_code == 503
    assert response.json()["detail"] == "Gemini quota exceeded. Switch to Manual, or try again later."
