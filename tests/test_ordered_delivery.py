from backend.database.sqlite import SQLiteDatabase
from backend.models.task import TaskCreate, TaskStatus
from backend.worker.task_worker import TaskWorker


def task(workspace: str, name: str) -> TaskCreate:
    return TaskCreate(
        project_name=name,
        workspace_path=workspace,
        goal=name,
        execution_mode="dry_run",
    )


class CompletingService:
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database
        self.called: list[str] = []

    def run_task(self, task_id: str):
        self.called.append(task_id)
        return self.database.update_task(task_id, status=TaskStatus.PASSED)


def test_same_workspace_tasks_wait_for_predecessor(tmp_path) -> None:
    workspace = str(tmp_path / "project")
    (tmp_path / "project").mkdir()
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    first = database.create_task("first", task(workspace, "first"))
    second = database.create_task("second", task(workspace, "second"))

    first = database.enqueue_task_in_order(first.task_id)
    second = database.enqueue_task_in_order(second.task_id)

    assert first.status is TaskStatus.QUEUED
    assert second.status is TaskStatus.WAITING_DEPENDENCY
    assert second.predecessor_task_id == first.task_id
    assert second.sequence_no == 2


def test_worker_promotes_next_task_only_after_predecessor_passes(
    tmp_path,
) -> None:
    workspace_path = tmp_path / "project"
    workspace_path.mkdir()
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    first = database.create_task(
        "first", task(str(workspace_path), "first")
    )
    second = database.create_task(
        "second", task(str(workspace_path), "second")
    )
    database.enqueue_task_in_order(first.task_id)
    database.enqueue_task_in_order(second.task_id)
    service = CompletingService(database)
    worker = TaskWorker(database, service)  # type: ignore[arg-type]

    assert worker.run_once() is True
    assert service.called == ["first"]
    assert database.get_task("second").status is TaskStatus.WAITING_DEPENDENCY  # type: ignore[union-attr]

    assert worker.run_once() is True
    assert service.called == ["first", "second"]
    assert database.get_task("second").status is TaskStatus.PASSED  # type: ignore[union-attr]


def test_failed_predecessor_holds_next_task_until_explicit_cancel(
    tmp_path,
) -> None:
    workspace = str(tmp_path / "project")
    (tmp_path / "project").mkdir()
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    first = database.create_task("first", task(workspace, "first"))
    second = database.create_task("second", task(workspace, "second"))
    database.enqueue_task_in_order(first.task_id)
    database.enqueue_task_in_order(second.task_id)
    database.update_task(first.task_id, status=TaskStatus.FAILED)

    assert database.promote_waiting_tasks() == 0
    assert database.get_task(second.task_id).status is TaskStatus.WAITING_DEPENDENCY  # type: ignore[union-attr]

    database.update_task(first.task_id, status=TaskStatus.CANCELED)
    assert database.promote_waiting_tasks() == 1
    assert database.get_task(second.task_id).status is TaskStatus.QUEUED  # type: ignore[union-attr]
