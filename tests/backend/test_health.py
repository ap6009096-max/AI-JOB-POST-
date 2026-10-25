from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ready() -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["service"] == "ai-job-post-backend"


def test_health_returns_service_name() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "ai-job-post-backend"
    assert body["status"] in {"ok", "degraded"}


def test_root_matches_health() -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "ai-job-post-backend"
    assert body["status"] in {"ok", "degraded"}


def test_local_lan_origin_is_allowed() -> None:
    origin = "http://10.239.128.53:3000"
    response = client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
