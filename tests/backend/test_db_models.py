from uuid import UUID

from app.db.models import Candidate, CandidateProfile, Company, Job, User


def test_uuid_primary_keys(db_session) -> None:
    user = User(email="recruiter@example.com", full_name="Rekha")
    db_session.add(user)
    db_session.flush()

    assert isinstance(user.id, UUID)
    assert user.status == "active"


def test_company_job_foreign_key(db_session) -> None:
    company = Company(name="Northwind")
    db_session.add(company)
    db_session.flush()

    job = Job(company_id=company.id, title="Backend Engineer", requirements={"skills": ["python"]})
    db_session.add(job)
    db_session.flush()

    assert isinstance(job.id, UUID)
    assert job.company_id == company.id
    assert job.company.name == "Northwind"
    assert job.requirements["skills"] == ["python"]


def test_candidate_profile_relationship(db_session) -> None:
    candidate = Candidate()
    db_session.add(candidate)
    db_session.flush()

    profile = CandidateProfile(
        candidate_id=candidate.id,
        headline="Full-stack developer",
        extras={"notice_days": 30},
    )
    db_session.add(profile)
    db_session.flush()

    db_session.refresh(candidate)
    assert candidate.profile is not None
    assert candidate.profile.headline == "Full-stack developer"
    assert candidate.profile.extras["notice_days"] == 30
