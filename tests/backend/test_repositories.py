from uuid import UUID

from app.db.repositories import (
    AuditRepository,
    CandidateRepository,
    CompanyRepository,
    EmbeddingRepository,
    JobRepository,
    MatchingRepository,
    SourcingRepository,
    UserRepository,
)
from app.db.session import get_db
from app.services.audit import AuditService
from app.services.candidates import CandidateService
from app.services.jobs import JobService


def test_user_company_job_create_and_list(db_session) -> None:
    users = UserRepository(db_session)
    companies = CompanyRepository(db_session)
    jobs = JobRepository(db_session)

    user = users.create(email="owner@example.com", full_name="Owner")
    company = companies.create(name="Acme")
    companies.add_member(company_id=company.id, user_id=user.id, role="owner")
    job = jobs.create(company_id=company.id, title="Platform Engineer")

    assert users.get(user.id) is not None
    assert companies.get(company.id).name == "Acme"
    assert jobs.get(job.id).company_id == company.id
    assert len(jobs.list_by_company(company.id)) == 1
    assert len(companies.list_members(company.id)) == 1


def test_candidate_and_matching_repositories(db_session) -> None:
    users = UserRepository(db_session)
    companies = CompanyRepository(db_session)
    jobs = JobRepository(db_session)
    candidates = CandidateRepository(db_session)
    matching = MatchingRepository(db_session)

    user = users.create(email="candidate@example.com")
    candidate = candidates.create(user_id=user.id)
    candidates.create_profile(candidate_id=candidate.id, headline="Python developer")

    company = companies.create(name="Hire Co")
    job = jobs.create(company_id=company.id, title="Python Engineer")
    run = matching.create(job_id=job.id, track="portal")
    score = matching.create_score(run_id=run.id, candidate_id=candidate.id, score=0.91, parts={"skills": 0.9})
    result = matching.create_result(run_id=run.id, rank=1, score=0.91, candidate_id=candidate.id)

    assert candidates.get(candidate.id).user_id == user.id
    assert matching.get(run.id).track == "portal"
    assert score.candidate_id == candidate.id
    assert result.rank == 1
    assert len(matching.list(job_id=job.id)) == 1


def test_sourcing_embedding_and_audit_repositories(db_session) -> None:
    companies = CompanyRepository(db_session)
    jobs = JobRepository(db_session)
    sourcing = SourcingRepository(db_session)
    embeddings = EmbeddingRepository(db_session)
    audit = AuditRepository(db_session)
    users = UserRepository(db_session)

    actor = users.create(email="auditor@example.com")
    company = companies.create(name="Search Co")
    job = jobs.create(company_id=company.id, title="SRE")
    run = sourcing.create(job_id=job.id, query={"q": "site:linkedin.com SRE"})
    external = sourcing.create_external_candidate(
        sourcing_run_id=run.id,
        source="web",
        url="https://example.com/c",
        display_name="Pat",
        payload={"title": "SRE"},
    )
    evidence = sourcing.create_evidence(
        external_candidate_id=external.id,
        kind="page",
        body={"snippet": "SRE at Example"},
    )
    embedding = embeddings.create(
        owner_type="job",
        owner_id=job.id,
        model="test-model",
        embedding=[0.1, 0.2, 0.3],
    )
    log = audit.create(
        actor_user_id=actor.id,
        action="job.create",
        entity_type="job",
        entity_id=job.id,
        metadata={"title": job.title},
    )

    assert sourcing.get(run.id) is not None
    assert evidence.external_candidate_id == external.id
    assert embeddings.get(embedding.id).owner_id == job.id
    assert audit.get(log.id).action == "job.create"
    assert log.metadata_["title"] == "SRE"


def test_services_delegate_to_repositories(db_session) -> None:
    companies = CompanyRepository(db_session)
    company = companies.create(name="Service Co")

    jobs = JobService(db_session)
    job = jobs.create(company_id=company.id, title="Data Engineer")
    assert jobs.get(job.id).title == "Data Engineer"

    candidates = CandidateService(db_session)
    candidate = candidates.create()
    assert candidates.get(candidate.id) is not None

    audit = AuditService(db_session)
    log = audit.create(action="candidate.create", entity_type="candidate", entity_id=candidate.id)
    assert audit.get(log.id).entity_id == candidate.id


def test_get_db_closes_session(sqlite_engine, monkeypatch) -> None:
    from sqlalchemy.orm import Session, sessionmaker

    from app.db import session as session_module

    TestSession = sessionmaker(bind=sqlite_engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(session_module, "SessionLocal", TestSession)

    closed: list[Session] = []
    original_close = Session.close

    def tracking_close(self: Session) -> None:
        closed.append(self)
        original_close(self)

    monkeypatch.setattr(Session, "close", tracking_close)

    generator = get_db()
    db = next(generator)
    assert db.is_active
    generator.close()
    assert db in closed


def test_uuid_ids_from_repositories(db_session) -> None:
    user = UserRepository(db_session).create(email="uuid@example.com")
    assert isinstance(user.id, UUID)
