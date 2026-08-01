from datetime import UTC, datetime, timedelta

from backend.database.sqlite import SQLiteDatabase
from backend.models.task import TaskCreate, TaskStatus
from backend.reliability.recovery_manager import RecoveryManager
from backend.reliability.workspace_lock_manager import WorkspaceLockManager
from backend.services.task_service import TaskService


def task_input(workspace_path: str, timeout_seconds: int = 3600) -> TaskCreate:
    return TaskCreate(
        project_name="可靠性测试",
        workspace_path=workspace_path,
        goal="验证任务恢复",
        requirements=[],
        priority="normal",
        timeout_seconds=timeout_seconds,
    )


def test_service_restart_cleans_lock_and_recovers_task(tmp_path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    created = database.create_task(
        "task-recover", task_input(str(workspace))
    )
    database.update_task(
        created.task_id, status=TaskStatus.DEVELOPING
    )
    lock_manager = WorkspaceLockManager(database)
    assert lock_manager.acquire(
        workspace_path=str(workspace), task_id=created.task_id
    )
    recovered: list[str] = []

    def runner(task_id: str):
        recovered.append(task_id)
        return database.update_task(task_id, status=TaskStatus.PASSED)

    report = RecoveryManager(
        database, runner, lock_manager=lock_manager
    ).recover_on_startup()

    assert report.cleaned_locks == 1
    assert report.recovered_task_ids == [created.task_id]
    assert recovered == [created.task_id]
    assert database.get_task(created.task_id).status is TaskStatus.PASSED  # type: ignore[union-attr]
    assert database.list_workspace_locks()[0].status == "STALE"


def test_timed_out_task_is_failed_without_execution(tmp_path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    now = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
    created = database.create_task(
        "task-timeout",
        task_input(str(workspace), timeout_seconds=60),
    )
    database.update_task(
        created.task_id,
        status=TaskStatus.RUNNING,
        last_heartbeat=(now - timedelta(minutes=5)).isoformat(),
    )
    called = False

    def runner(task_id: str):
        nonlocal called
        called = True

    report = RecoveryManager(
        database, runner, clock=lambda: now
    ).recover_on_startup()
    task = database.get_task(created.task_id)

    assert called is False
    assert report.failed_task_ids == [created.task_id]
    assert task is not None
    assert task.status is TaskStatus.FAILED
    assert task.blocked_reason == "Task timed out"
    assert task.required_action == "Review task logs and restart manually"


def test_workspace_lock_conflict_allows_only_one_task(tmp_path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    first = database.create_task("task-1", task_input(str(workspace)))
    second = database.create_task("task-2", task_input(str(workspace)))
    locks = WorkspaceLockManager(database)

    first_lock = locks.acquire(
        workspace_path=str(workspace), task_id=first.task_id
    )
    second_lock = locks.acquire(
        workspace_path=str(workspace), task_id=second.task_id
    )

    assert first_lock is not None
    assert second_lock is None


def test_workspace_lock_release_allows_next_task(tmp_path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    first = database.create_task("task-1", task_input(str(workspace)))
    second = database.create_task("task-2", task_input(str(workspace)))
    locks = WorkspaceLockManager(database)
    locks.acquire(workspace_path=str(workspace), task_id=first.task_id)

    locks.release(task_id=first.task_id)
    second_lock = locks.acquire(
        workspace_path=str(workspace), task_id=second.task_id
    )

    assert second_lock is not None
    assert [lock.status for lock in database.list_workspace_locks()] == [
        "RELEASED",
        "ACTIVE",
    ]


def test_blocked_reason_and_required_action_are_saved(tmp_path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    created = database.create_task(
        "task-blocked", task_input(str(workspace))
    )

    task = database.update_task(
        created.task_id,
        status=TaskStatus.BLOCKED,
        blocked_reason="缺少需求信息",
        required_action="人工确认接口范围",
    )

    assert task.status is TaskStatus.BLOCKED
    assert task.blocked_reason == "缺少需求信息"
    assert task.required_action == "人工确认接口范围"


def test_created_task_enters_queued_before_execution(tmp_path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    seen_statuses: list[TaskStatus] = []

    class StubCrewService:
        def run_task(self, task_id: str):
            task = database.get_task(task_id)
            assert task is not None
            seen_statuses.append(task.status)
            return task

    service = TaskService(database, StubCrewService())  # type: ignore[arg-type]
    created = service.create_task(task_input(str(workspace)))

    result = service.run_task(created.task_id)

    assert created.status is TaskStatus.CREATED
    assert seen_statuses == [TaskStatus.QUEUED]
    assert result.status is TaskStatus.QUEUED
