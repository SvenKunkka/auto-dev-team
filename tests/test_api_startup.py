from fastapi.testclient import TestClient

from backend.main import create_app


def test_fastapi_starts_and_reports_status(tmp_path) -> None:
    app = create_app(
        database_path=tmp_path / "platform.db",
        worker_poll_interval=0.01,
        heartbeat_interval=0.01,
    )

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "Auto Dev Platform",
        "status": "RUNNING",
        "phase": "5",
        "environment": "development",
    }
    assert app.state.recovery_manager is not None
    assert app.state.task_worker is not None
