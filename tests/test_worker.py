import threading
import time

from backend.database.sqlite import SQLiteDatabase
from backend.models.task import TaskCreate, TaskStatus
from backend.reliability.workspace_lock_manager import WorkspaceLockManager
from backend.worker.task_worker import TaskWorker


def create_queued_task(
    database: SQLiteDatabase,
    task_id: str,
    workspace_path: str,
):
    task = database.create_task(
        task_id,
        TaskCreate(
            project_name="Worker测试",
            workspace_path=workspace_path,
            goal="执行队列任务",
            requirements=[],
            priority="normal",
        ),
    )
    return database.update_task(task.task_id, status=TaskStatus.QUEUED)


class CompletingTaskService:
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database
        self.called: list[str] = []

    def run_task(self, task_id: str):
        self.called.append(task_id)
        self.database.update_task(task_id, status=TaskStatus.RUNNING)
        return self.database.update_task(
            task_id, status=TaskStatus.PASSED
        )


def test_queued_task_is_executed(tmp_path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    task = create_queued_task(database, "task-1", str(workspace))
    service = CompletingTaskService(database)
    worker = TaskWorker(database, service)  # type: ignore[arg-type]

    assert worker.run_once() is True

    finished = database.get_task(task.task_id)
    assert service.called == [task.task_id]
    assert finished is not None
    assert finished.status is TaskStatus.PASSED


def test_workspace_lock_conflict_leaves_task_queued(tmp_path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    holder = database.create_task(
        "task-holder",
        TaskCreate(
            project_name="Worker测试",
            workspace_path=str(workspace),
            goal="持有锁",
            requirements=[],
            priority="normal",
        ),
    )
    database.update_task(holder.task_id, status=TaskStatus.RUNNING)
    queued = create_queued_task(database, "task-2", str(workspace))
    locks = WorkspaceLockManager(database)
    locks.acquire(workspace_path=str(workspace), task_id=holder.task_id)
    service = CompletingTaskService(database)
    worker = TaskWorker(
        database, service, lock_manager=locks  # type: ignore[arg-type]
    )

    processed = worker.run_once()

    assert processed is False
    assert service.called == []
    assert database.get_task(queued.task_id).status is TaskStatus.QUEUED  # type: ignore[union-attr]


def test_heartbeat_updates_while_task_is_running(tmp_path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    task = create_queued_task(database, "task-1", str(workspace))
    started = threading.Event()
    finish = threading.Event()

    class BlockingService:
        def run_task(self, task_id: str):
            database.update_task(task_id, status=TaskStatus.RUNNING)
            started.set()
            finish.wait(2)
            return database.update_task(
                task_id, status=TaskStatus.PASSED
            )

    worker = TaskWorker(
        database,
        BlockingService(),  # type: ignore[arg-type]
        poll_interval=0.01,
        heartbeat_interval=0.01,
    )
    worker.start()
    assert started.wait(1)
    first_heartbeat = database.get_task(task.task_id).last_heartbeat  # type: ignore[union-attr]
    time.sleep(0.04)
    second_heartbeat = database.get_task(task.task_id).last_heartbeat  # type: ignore[union-attr]
    finish.set()
    assert worker.stop(timeout=1)

    assert first_heartbeat is not None
    assert second_heartbeat is not None
    assert second_heartbeat > first_heartbeat


def test_worker_exception_releases_lock_and_fails_task(tmp_path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    task = create_queued_task(database, "task-1", str(workspace))

    class FailingService:
        def run_task(self, task_id: str):
            database.update_task(task_id, status=TaskStatus.RUNNING)
            raise RuntimeError("worker failed")

    worker = TaskWorker(
        database, FailingService()  # type: ignore[arg-type]
    )
    worker.run_once()

    finished = database.get_task(task.task_id)
    assert finished is not None
    assert finished.status is TaskStatus.FAILED
    assert finished.blocked_reason == "Worker execution failed: worker failed"
    assert database.list_workspace_locks()[-1].status == "RELEASED"


def test_shutdown_stops_polling_and_waits_for_current_task(tmp_path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    task = create_queued_task(database, "task-1", str(workspace))
    started = threading.Event()
    finish = threading.Event()

    class BlockingService:
        def run_task(self, task_id: str):
            database.update_task(task_id, status=TaskStatus.RUNNING)
            started.set()
            finish.wait(2)
            return database.update_task(
                task_id, status=TaskStatus.PASSED
            )

    worker = TaskWorker(
        database,
        BlockingService(),  # type: ignore[arg-type]
        poll_interval=0.01,
        heartbeat_interval=0.01,
    )
    worker.start()
    assert started.wait(1)

    assert worker.stop(timeout=0.02) is False
    assert worker.accepting_tasks is False
    finish.set()
    assert worker.stop(timeout=1) is True

    assert worker.current_task_id is None
    assert database.get_task(task.task_id).status is TaskStatus.PASSED  # type: ignore[union-attr]
    assert database.list_workspace_locks()[-1].status == "RELEASED"
