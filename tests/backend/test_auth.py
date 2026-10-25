import time
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core import security
from app.core.security import decode_access_token
from app.main import app
from app.services.auth import AuthService

client = TestClient(app)


class _FakeKey:
    key = "test-secret-key-for-jwt-verification-ok"


class _FakeJwks:
    def get_signing_key_from_jwt(self, _token: str) -> _FakeKey:
        return _FakeKey()


def _token(**claims: object) -> str:
    payload = {
        "sub": str(uuid4()),
        "exp": int(time.time()) + 3600,
        "aud": "authenticated",
        **claims,
    }
    return jwt.encode(payload, "test-secret-key-for-jwt-verification-ok", algorithm="HS256")


def test_decode_access_token_strips_user_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security, "_jwks_client", lambda: _FakeJwks())
    token = _token(user_metadata={"role": "platform_admin"}, app_metadata={"role": "candidate"})
    claims = decode_access_token(token)
    assert "user_metadata" not in claims
    assert claims["app_metadata"]["role"] == "candidate"


def test_decode_access_token_rejects_invalid_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security, "_jwks_client", lambda: _FakeJwks())
    token = jwt.encode(
        {"sub": str(uuid4()), "exp": int(time.time()) + 3600, "aud": "authenticated"},
        "wrong-secret",
        algorithm="HS256",
    )
    with pytest.raises(Exception):
        decode_access_token(token)


def test_me_requires_bearer() -> None:
    response = client.get("/v1/me")
    assert response.status_code == 401


def test_bootstrap_first_write_wins(db_session) -> None:
    auth_id = uuid4()
    service = AuthService(db_session)
    first = service.bootstrap(
        auth_user_id=auth_id,
        email="person@example.com",
        intent="candidate",
        full_name="Pat",
    )
    second = service.bootstrap(
        auth_user_id=auth_id,
        email="person@example.com",
        intent="company",
        company_name="Should Not Apply",
    )
    assert first.role == "candidate"
    assert second.role == "candidate"
    assert second.id == first.id


def test_jobs_without_token_is_unauthorized() -> None:
    response = client.get("/v1/jobs")
    assert response.status_code in {401, 403, 503}
