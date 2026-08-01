import sqlite3

from backend.database.sqlite import SQLiteDatabase
from backend.models.task import TaskCreate, TaskStatus


def sample_task() -> TaskCreate:
    return TaskCreate(
        project_name="产品知识系统",
        workspace_path="/tmp/product-knowledge",
        goal="实现 Knowledge API",
        requirements=["统一查询入口", "支持型号识别"],
        priority="high",
    )


def test_sqlite_initializes_required_tables(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()

    with sqlite3.connect(database.database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {
        "tasks",
        "agent_runs",
        "task_artifacts",
        "task_iterations",
        "workspace_locks",
    } <= tables


def test_task_and_agent_run_are_persisted(tmp_path) -> None:
    database_path = tmp_path / "platform.db"
    database = SQLiteDatabase(database_path)
    database.initialize()

    created = database.create_task("task-001", sample_task())
    assert created.status is TaskStatus.CREATED
    assert created.execution_mode.value == "dry_run"
    assert created.requirements == ["统一查询入口", "支持型号识别"]

    database.update_task(
        "task-001",
        status=TaskStatus.PLANNING,
        supervisor_output="任务规划",
    )
    database.create_agent_run(
        task_id="task-001",
        agent_name="supervisor",
        input_text="用户需求",
        output="任务规划",
        status="COMPLETED",
    )

    reopened = SQLiteDatabase(database_path)
    task = reopened.get_task("task-001")
    runs = reopened.list_agent_runs("task-001")

    assert task is not None
    assert task.status is TaskStatus.PLANNING
    assert task.supervisor_output == "任务规划"
    assert len(runs) == 1
    assert runs[0].agent_name == "supervisor"


def test_task_artifact_is_persisted(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    database.create_task("task-002", sample_task())

    database.create_task_artifact(
        task_id="task-002",
        artifact_type="git_diff",
        content="diff --git a/app.py b/app.py",
    )

    artifacts = database.list_task_artifacts("task-002")
    assert len(artifacts) == 1
    assert artifacts[0].artifact_type == "git_diff"
    assert artifacts[0].content.startswith("diff --git")


def test_task_iteration_and_retry_fields_are_persisted(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    created = database.create_task("task-003", sample_task())
    database.update_task("task-003", retry_count=1)
    database.create_task_iteration(
        task_id="task-003",
        iteration=1,
        supervisor_output="任务计划",
        developer_output="开发结果",
        verification_output="验证通过",
        reviewer_output="FAIL",
        status=TaskStatus.FAILED,
    )

    task = database.get_task("task-003")
    iterations = database.list_task_iterations("task-003")

    assert created.max_retry == 3
    assert task is not None
    assert task.retry_count == 1
    assert len(iterations) == 1
    assert iterations[0].verification_output == "验证通过"
    assert iterations[0].status is TaskStatus.FAILED


def test_existing_database_receives_retry_columns(tmp_path) -> None:
    database_path = tmp_path / "legacy.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL UNIQUE,
                project_name TEXT NOT NULL,
                workspace_path TEXT NOT NULL,
                goal TEXT NOT NULL,
                requirements TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                supervisor_output TEXT,
                developer_output TEXT,
                reviewer_output TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO tasks (
                task_id, project_name, workspace_path, goal, requirements,
                priority, status, created_at, updated_at
            ) VALUES (
                'legacy-task', 'legacy', '/tmp/legacy', 'legacy goal', '[]',
                'normal', 'PASSED', '2026-07-27T00:00:00+00:00',
                '2026-07-27T00:00:00+00:00'
            )
            """
        )

    SQLiteDatabase(database_path).initialize()

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(tasks)")
        }
        legacy_mode = connection.execute(
            "SELECT execution_mode FROM tasks WHERE task_id = 'legacy-task'"
        ).fetchone()[0]
    assert {
        "retry_count",
        "max_retry",
        "started_at",
        "last_heartbeat",
        "timeout_seconds",
        "blocked_reason",
        "required_action",
        "execution_mode",
    } <= columns
    assert legacy_mode == "execute"
