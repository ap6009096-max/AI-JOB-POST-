from contextlib import contextmanager
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import Principal, get_current_user
from app.db.models import User
from app.db.repositories.users import UserRepository
from app.db.session import get_db
from app.main import app

client = TestClient(app)


@contextmanager
def acting_as(user: User, db_session):
    def override_user() -> Principal:
        return Principal(user=user, claims={}, memberships=[])

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
        full_name="Pat Candidate",
        role=role,
    )


def test_recruiter_cannot_read_candidate_self_profile(db_session) -> None:
    recruiter = _user(db_session, role="recruiter")
    with acting_as(recruiter, db_session):
        response = client.get("/v1/me/candidate")
    assert response.status_code == 403


def test_candidate_can_crud_own_experience(db_session) -> None:
    candidate = _user(db_session, role="candidate")
    with acting_as(candidate, db_session):
        created = client.post(
            "/v1/me/candidate/experience",
            json={"company_name": "Acme", "title": "Engineer", "description": "Built APIs"},
        )
        assert created.status_code == 200
        row_id = created.json()["id"]

        listed = client.get("/v1/me/candidate")
        assert listed.status_code == 200
        assert len(listed.json()["experience"]) == 1
        assert listed.json()["experience"][0]["title"] == "Engineer"

        patched = client.patch(
            f"/v1/me/candidate/experience/{row_id}",
            json={"title": "Senior Engineer"},
        )
        assert patched.status_code == 200
        assert patched.json()["title"] == "Senior Engineer"

        deleted = client.delete(f"/v1/me/candidate/experience/{row_id}")
        assert deleted.status_code == 204
        empty = client.get("/v1/me/candidate")
        assert empty.json()["experience"] == []


def test_completion_increases_after_profile_and_skill(db_session) -> None:
    candidate = _user(db_session, role="candidate")
    with acting_as(candidate, db_session):
        before = client.get("/v1/me/candidate")
        assert before.status_code == 200
        start = before.json()["completion"]["percent"]
        assert start == 0

        profile = client.patch(
            "/v1/me/candidate/profile",
            json={"headline": "Python developer", "location": "Bengaluru"},
        )
        assert profile.status_code == 200
        after_profile = profile.json()["completion"]["percent"]
        assert after_profile > start

        skill = client.post("/v1/me/candidate/skills", json={"skill": "Python", "years": 4})
        assert skill.status_code == 200
        after_skill = client.get("/v1/me/candidate").json()["completion"]["percent"]
        assert after_skill > after_profile
        assert after_skill == 18


def test_candidate_can_save_personal(db_session) -> None:
    candidate = _user(db_session, role="candidate")
    with acting_as(candidate, db_session):
        response = client.patch(
            "/v1/me/candidate/personal",
            json={
                "given_name": "Pat",
                "family_name": "Kumar",
                "city": "Bengaluru",
                "country": "India",
                "phone": "9999999999",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["personal"]["given_name"] == "Pat"
    assert body["personal"]["family_name"] == "Kumar"
    assert body["personal"]["city"] == "Bengaluru"
    assert body["full_name"] == "Pat Kumar"
    assert body["profile"]["location"] == "Bengaluru, India"


def test_named_linkedin_upsert(db_session) -> None:
    candidate = _user(db_session, role="candidate")
    with acting_as(candidate, db_session):
        response = client.put(
            "/v1/me/candidate/professional-links",
            json={
                "linkedin": "https://linkedin.com/in/pat",
                "github": "",
                "portfolio": "",
                "website": "",
                "other": [],
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["professional_links"]["linkedin"] == "https://linkedin.com/in/pat"
    assert any(row["source"] == "linkedin" for row in body["links"])


def test_technologies_crud(db_session) -> None:
    candidate = _user(db_session, role="candidate")
    with acting_as(candidate, db_session):
        created = client.post("/v1/me/candidate/technologies", json={"name": "Python", "years": 4})
        assert created.status_code == 200
        row_id = created.json()["id"]
        assert created.json()["name"] == "Python"

        patched = client.patch(
            f"/v1/me/candidate/technologies/{row_id}",
            json={"name": "Python 3"},
        )
        assert patched.status_code == 200
        assert patched.json()["name"] == "Python 3"

        deleted = client.delete(f"/v1/me/candidate/technologies/{row_id}")
        assert deleted.status_code == 204
        graph = client.get("/v1/me/candidate")
        assert graph.json()["technologies"] == []
