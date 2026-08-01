import threading

from fastapi.testclient import TestClient

from backend.database.sqlite import SQLiteDatabase
from backend.main import create_app
from backend.models.task import TaskCreate, TaskStatus
from backend.runtime.agent_runtime import (
    AgentRuntime,
    RuntimeRequest,
    RuntimeResult,
    RuntimeStatus,
)
from backend.services.crew_service import CrewService
from backend.services.task_service import TaskService


def make_task(app, name: str):
    return app.state.task_service.create_task(
        TaskCreate(
            project_name=name,
            workspace_path="/tmp/control-project",
            goal="控制任务",
            requirements=[],
        )
    )


def test_pause_cancel_and_retry_controls(tmp_path) -> None:
    app = create_app(database_path=tmp_path / "platform.db")
    paused = make_task(app, "pause")
    canceled = make_task(app, "cancel")
    failed = make_task(app, "retry")
    app.state.database.update_task(
        failed.task_id,
        status=TaskStatus.FAILED,
        blocked_reason="failure",
        required_action="retry",
    )

    client = TestClient(app)
    pause_response = client.post(f"/tasks/{paused.task_id}/pause")
    cancel_response = client.post(f"/tasks/{canceled.task_id}/cancel")
    retry_response = client.post(f"/tasks/{failed.task_id}/retry")

    assert pause_response.json()["status"] == "PAUSED"
    assert cancel_response.json()["status"] == "CANCELED"
    assert retry_response.json()["status"] == "QUEUED"
    retried = app.state.database.get_task(failed.task_id)
    assert retried is not None
    assert retried.blocked_reason is None
    assert retried.required_action is None


def test_invalid_control_transition_returns_conflict(tmp_path) -> None:
    app = create_app(database_path=tmp_path / "platform.db")
    task = make_task(app, "passed")
    app.state.database.update_task(
        task.task_id, status=TaskStatus.PASSED
    )

    with TestClient(app) as client:
        response = client.post(f"/tasks/{task.task_id}/pause")

    assert response.status_code == 409


def test_task_detail_contains_control_context(tmp_path) -> None:
    app = create_app(database_path=tmp_path / "platform.db")
    task = make_task(app, "detail")
    app.state.database.create_task_artifact(
        task_id=task.task_id,
        artifact_type="changed_files",
        content='["a.py", "b.py"]',
    )

    response = TestClient(app).get(f"/tasks/{task.task_id}")

    body = response.json()
    assert body["current_agent"] is None
    assert body["iteration"] == 1
    assert body["heartbeat"] is None
    assert body["evidence_summary"]["changed_files_count"] == 2
    assert body["logs"][0]["event_type"] == "TASK_CREATED"


def test_pause_during_runtime_stops_before_next_agent(tmp_path) -> None:
    started = threading.Event()
    release = threading.Event()

    class BlockingSupervisor(AgentRuntime):
        agent_name = "supervisor"

        def run(self, request: RuntimeRequest) -> RuntimeResult:
            started.set()
            release.wait(1)
            return RuntimeResult(
                agent_name=self.agent_name,
                status=RuntimeStatus.COMPLETED,
                output="计划",
            )

    class CountingRuntime(AgentRuntime):
        def __init__(self, agent_name: str) -> None:
            self.agent_name = agent_name
            self.calls = 0

        def run(self, request: RuntimeRequest) -> RuntimeResult:
            self.calls += 1
            return RuntimeResult(
                agent_name=self.agent_name,
                status=RuntimeStatus.COMPLETED,
                output="PASS",
            )

    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    developer = CountingRuntime("developer")
    reviewer = CountingRuntime("reviewer")
    service = TaskService(
        database,
        CrewService(
            database,
            BlockingSupervisor(),
            developer,
            reviewer,
        ),
    )
    task = service.create_task(
        TaskCreate(
            project_name="pause-running",
            workspace_path=str(tmp_path),
            goal="pause",
            requirements=[],
            execution_mode="execute",
        )
    )
    thread = threading.Thread(
        target=service.run_task,
        args=(task.task_id,),
    )
    thread.start()
    assert started.wait(1)

    service.pause_task(task.task_id)
    release.set()
    thread.join(1)

    paused = database.get_task(task.task_id)
    assert paused is not None
    assert paused.status is TaskStatus.PAUSED
    assert developer.calls == 0
    assert reviewer.calls == 0
    assert database.list_workspace_locks()[-1].status == "RELEASED"
