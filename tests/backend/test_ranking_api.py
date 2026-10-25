from fastapi.testclient import TestClient
import pytest

from app.core.security import require_company_member
from app.data.seed import DEMO_JOB_ID
from app.db.repositories.users import UserRepository
from app.db.session import get_db
from app.main import app
from app.services.candidates import CandidateService

client = TestClient(app)


@pytest.fixture(autouse=True)
def company_staff_auth(db_session) -> None:
    def override_db():
        yield db_session

    app.dependency_overrides[require_company_member] = lambda: object()
    app.dependency_overrides[get_db] = override_db
    yield
    app.dependency_overrides.pop(require_company_member, None)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def skip_reddit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.jobs.search_for_job", lambda _job: [])


def test_list_jobs_is_company_scoped() -> None:
    response = client.get("/v1/jobs")
    assert response.status_code == 200
    assert response.json() == []


def test_portal_rank_demo_job_not_found() -> None:
    response = client.post(f"/v1/jobs/{DEMO_JOB_ID}/rank/portal?limit=10")
    assert response.status_code == 404


def test_internet_rank_persists_top_100() -> None:
    response = client.post(f"/v1/jobs/{DEMO_JOB_ID}/rank/internet?limit=20")
    assert response.status_code == 200
    body = response.json()
    assert body["track"] == "internet"
    assert body["limit"] == 100
    assert len(body["results"]) == 20
    assert all("Ranking engine" in row["reasons"][0] for row in body["results"])
    assert all(not str(row["candidate_id"]).startswith("pc-") for row in body["results"])


def test_portal_rank_rejects_invalid_limit() -> None:
    response = client.post(f"/v1/jobs/{DEMO_JOB_ID}/rank/portal?limit=15")
    assert response.status_code == 422


def test_get_rank_run() -> None:
    created = client.post(f"/v1/jobs/{DEMO_JOB_ID}/rank/internet?limit=10")
    run_id = created.json()["id"]
    fetched = client.get(f"/v1/jobs/{DEMO_JOB_ID}/rank/{run_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == run_id
    assert fetched.json()["track"] == "internet"


def test_portal_candidate_list_is_registered(db_session) -> None:
    user = UserRepository(db_session).create(
        email="asha@example.com",
        full_name="Asha Menon",
        role="candidate",
    )
    CandidateService(db_session).ensure_for_user(user.id)
    db_session.flush()
    listed = client.get("/v1/candidates/portal")
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert body[0]["id"] != "pc-01"
    assert body[0]["profile"]["name"] == "Asha Menon"
    details = client.get(f"/v1/candidates/portal/{body[0]['id']}")
    assert details.status_code == 200
    missing = client.get("/v1/candidates/portal/pc-01")
    assert missing.status_code == 404
