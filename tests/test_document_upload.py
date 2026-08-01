import time

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.runtime.agent_runtime import (
    AgentRuntime,
    RuntimeRequest,
    RuntimeResult,
    RuntimeStatus,
)


class CapturingSupervisor(AgentRuntime):
    agent_name = "supervisor"

    def __init__(self) -> None:
        self.requests: list[RuntimeRequest] = []

    def run(self, request: RuntimeRequest) -> RuntimeResult:
        self.requests.append(request)
        return RuntimeResult(
            agent_name=self.agent_name,
            status=RuntimeStatus.COMPLETED,
            output="任务规划",
        )


class CapturingRequirementAnalyst(AgentRuntime):
    agent_name = "requirement_analyst"

    def __init__(self) -> None:
        self.requests: list[RuntimeRequest] = []

    def run(self, request: RuntimeRequest) -> RuntimeResult:
        self.requests.append(request)
        return RuntimeResult(
            agent_name=self.agent_name,
            status=RuntimeStatus.COMPLETED,
            output='{"requirements":["必须支持批量查询"]}',
        )


def test_create_task_with_document_saves_and_passes_context(tmp_path) -> None:
    supervisor = CapturingSupervisor()
    analyst = CapturingRequirementAnalyst()
    app = create_app(
        database_path=tmp_path / "platform.db",
        supervisor_runtime=supervisor,
        requirement_analyst_runtime=analyst,
        worker_poll_interval=0.01,
        heartbeat_interval=0.01,
    )
    form = {
        "project_name": "文档任务",
        "workspace_path": "/tmp/document-task",
        "goal": "",
        "requirements": "[]",
        "priority": "normal",
        "execution_mode": "dry_run",
    }

    with TestClient(app) as client:
        response = client.post(
            "/tasks/with-documents",
            data=form,
            files={
                "documents": (
                    "spec.md",
                    "# 接口规格\n必须支持批量查询。",
                    "text/markdown",
                )
            },
        )
        task_id = response.json()["task_id"]
        for _ in range(100):
            detail = client.get(f"/tasks/{task_id}").json()
            if detail["status"] == "PASSED":
                break
            time.sleep(0.01)

    assert response.status_code == 201
    assert detail["status"] == "PASSED"
    assert detail["documents"][0]["filename"] == "spec.md"
    assert detail["documents"][0]["size"] > 0
    assert detail["evidence_summary"]["artifact_types"] == [
        "input_document"
    ]
    assert "必须支持批量查询" in analyst.requests[0].requirements[-1]
    assert supervisor.requests[0].requirements == []
    assert (
        "必须支持批量查询"
        in supervisor.requests[0].previous_outputs["requirement_analyst"]
    )
    stored_path = detail["documents"][0]["storage_path"]
    assert stored_path.startswith(str(tmp_path / "uploads" / task_id))


def test_rejects_task_without_text_or_requirement_document(tmp_path) -> None:
    app = create_app(database_path=tmp_path / "platform.db")

    with TestClient(app) as client:
        response = client.post(
            "/tasks",
            json={
                "project_name": "空任务",
                "workspace_path": "/tmp/empty-task",
                "goal": "",
                "requirements": [],
            },
        )
        tasks = client.get("/tasks").json()

    assert response.status_code == 422
    assert "需求文档至少需要提供一项" in response.json()["detail"]
    assert tasks == []


def test_rejects_unsupported_document_without_creating_task(tmp_path) -> None:
    app = create_app(database_path=tmp_path / "platform.db")

    with TestClient(app) as client:
        response = client.post(
            "/tasks/with-documents",
            data={
                "project_name": "非法附件",
                "workspace_path": "/tmp/document-task",
                "goal": "测试校验",
                "requirements": "[]",
            },
            files={
                "documents": (
                    "script.sh",
                    "echo unsafe",
                    "text/x-shellscript",
                )
            },
        )
        tasks = client.get("/tasks").json()

    assert response.status_code == 400
    assert "不支持的文档格式" in response.json()["detail"]
    assert tasks == []
