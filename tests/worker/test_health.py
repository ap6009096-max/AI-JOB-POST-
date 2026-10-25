from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_worker_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "aether-worker"


def test_worker_accepts_task(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "worker_shared_secret", None)
    response = client.post(
        "/tasks",
        json={"task_type": "parse_resume", "reference_id": "job-1", "payload": {}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_worker_rejects_task_without_secret(monkeypatch) -> None:
    from pydantic import SecretStr

    from app.config import settings

    monkeypatch.setattr(settings, "worker_shared_secret", SecretStr("shared"))
    response = client.post(
        "/tasks",
        json={"task_type": "parse_resume", "reference_id": "job-1", "payload": {}},
    )
    assert response.status_code == 403


def test_worker_accepts_task_with_secret(monkeypatch) -> None:
    from pydantic import SecretStr

    from app.config import settings

    monkeypatch.setattr(settings, "worker_shared_secret", SecretStr("shared"))
    response = client.post(
        "/tasks",
        headers={"X-Worker-Secret": "shared"},
        json={"task_type": "parse_resume", "reference_id": "job-1", "payload": {}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
