from fastapi.testclient import TestClient

from backend.main import create_app


def test_health_reports_database_worker_and_queue(tmp_path) -> None:
    app = create_app(
        database_path=tmp_path / "platform.db",
        worker_poll_interval=1,
    )

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "database": "healthy",
        "worker": "running",
        "queue_size": 0,
    }


def test_health_is_degraded_when_worker_is_stopped(tmp_path) -> None:
    app = create_app(database_path=tmp_path / "platform.db")

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["worker"] == "stopped"
