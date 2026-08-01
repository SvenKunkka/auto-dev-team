from fastapi.testclient import TestClient

from backend.database.sqlite import SQLiteDatabase
from backend.main import create_app
from backend.models.task import TaskCreate


def test_statistics_separate_goal_and_cumulative_role_counts(tmp_path) -> None:
    database_path = tmp_path / "platform.db"
    database = SQLiteDatabase(database_path)
    database.initialize()
    first = database.create_task(
        "task-001",
        TaskCreate(
            project_name="项目一",
            workspace_path="/tmp/project-one",
            goal="目标一",
        ),
    )
    database.create_task(
        "task-002",
        TaskCreate(
            project_name="项目二",
            workspace_path="/tmp/project-two",
            goal="目标二",
        ),
    )
    for agent_name in ("supervisor", "developer", "reviewer"):
        database.create_agent_run(
            task_id=first.task_id,
            agent_name=agent_name,
            input_text="{}",
            output="完成",
            status="COMPLETED",
        )
    database.create_agent_run(
        task_id=first.task_id,
        agent_name="developer",
        input_text="{}",
        output="返工完成",
        status="COMPLETED",
    )
    database.create_agent_run(
        task_id="task-002",
        agent_name="supervisor",
        input_text="{}",
        output="完成",
        status="COMPLETED",
    )

    app = create_app(database_path=database_path)
    with TestClient(app) as client:
        response = client.get(
            "/departments/statistics", params={"task_id": first.task_id}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["department_name"] == "任务统计部"
    assert body["selected_goal"]["task_id"] == first.task_id
    roles = {item["agent_name"]: item for item in body["roles"]}
    assert roles["requirement_analyst"]["goal_execution_count"] == 0
    assert roles["verification_engineer"]["goal_execution_count"] == 0
    assert roles["supervisor"]["goal_execution_count"] == 1
    assert roles["supervisor"]["cumulative_execution_count"] == 2
    assert roles["developer"]["goal_execution_count"] == 2
    assert roles["developer"]["cumulative_execution_count"] == 2
    assert roles["reviewer"]["goal_execution_count"] == 1
    assert roles["reviewer"]["cumulative_execution_count"] == 1


def test_statistics_unknown_goal_returns_404(tmp_path) -> None:
    app = create_app(database_path=tmp_path / "platform.db")
    with TestClient(app) as client:
        response = client.get(
            "/departments/statistics", params={"task_id": "missing"}
        )

    assert response.status_code == 404
