from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.core.security import require_company_member
from app.data.seed import DEMO_JOB_ID
from app.db.session import get_db
from app.main import app

client = TestClient(app)


def test_candidate_forbidden_on_jobs_and_ranking(db_session) -> None:
    def deny_candidate() -> None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Candidates cannot access recruiter dashboards",
        )

    def override_db():
        yield db_session

    app.dependency_overrides[require_company_member] = deny_candidate
    app.dependency_overrides[get_db] = override_db
    try:
        jobs = client.get("/v1/jobs")
        rank = client.post(f"/v1/jobs/{DEMO_JOB_ID}/rank/portal?limit=10")
        portal = client.get("/v1/candidates/portal/pc-01")
        assert jobs.status_code == 403
        assert rank.status_code == 403
        assert portal.status_code == 403
        assert "Candidates cannot access" in jobs.json()["detail"]
    finally:
        app.dependency_overrides.pop(require_company_member, None)
        app.dependency_overrides.pop(get_db, None)


def test_company_member_can_list_jobs(db_session) -> None:
    def override_db():
        yield db_session

    app.dependency_overrides[require_company_member] = lambda: object()
    app.dependency_overrides[get_db] = override_db
    try:
        response = client.get("/v1/jobs")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    finally:
        app.dependency_overrides.pop(require_company_member, None)
        app.dependency_overrides.pop(get_db, None)


def test_recruiter_without_override_cannot_use_demo_principal() -> None:
    app.dependency_overrides.pop(require_company_member, None)
    response = client.get("/v1/jobs")
    assert response.status_code != 200
