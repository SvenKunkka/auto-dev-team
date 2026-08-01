import time

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.runtime.agent_runtime import (
    AgentRuntime,
    RuntimeRequest,
    RuntimeResult,
    RuntimeStatus,
)


class FakeRuntime(AgentRuntime):
    def __init__(self, agent_name: str, output: str) -> None:
        self.agent_name = agent_name
        self.output = output

    def run(self, request: RuntimeRequest) -> RuntimeResult:
        return RuntimeResult(
            agent_name=self.agent_name,
            status=RuntimeStatus.COMPLETED,
            output=self.output,
        )


def test_create_and_query_task(tmp_path) -> None:
    app = create_app(
        database_path=tmp_path / "platform.db",
        supervisor_runtime=FakeRuntime("supervisor", "任务规划"),
        developer_runtime=FakeRuntime("developer", "开发结果"),
        reviewer_runtime=FakeRuntime("reviewer", "PASS\n验收通过"),
        worker_poll_interval=0.01,
        heartbeat_interval=0.01,
    )
    payload = {
        "project_name": "产品知识系统",
        "workspace_path": "/tmp/product-knowledge",
        "goal": "实现 Knowledge API",
        "requirements": ["统一查询入口", "支持型号识别"],
        "priority": "high",
        "execution_mode": "execute",
    }

    with TestClient(app) as client:
        create_response = client.post("/tasks", json=payload)
        task_id = create_response.json()["task_id"]
        for _ in range(100):
            detail_response = client.get(f"/tasks/{task_id}")
            if detail_response.json()["status"] == "PASSED":
                break
            time.sleep(0.01)
        list_response = client.get("/tasks")

    assert create_response.status_code == 201
    assert create_response.json()["status"] == "CREATED"
    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "PASSED"
    assert detail_response.json()["supervisor_output"] == "任务规划"
    assert detail_response.json()["developer_output"] == "开发结果"
    assert detail_response.json()["reviewer_output"].startswith("PASS")
    assert len(list_response.json()) == 1


def test_unknown_task_returns_404(tmp_path) -> None:
    app = create_app(database_path=tmp_path / "platform.db")

    with TestClient(app) as client:
        response = client.get("/tasks/not-found")

    assert response.status_code == 404
