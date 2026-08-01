from __future__ import annotations

import threading
from pathlib import Path

from backend.database.sqlite import SQLiteDatabase
from backend.models.task import TaskStatus
from backend.observability.logger import EventType, StructuredLogger
from backend.reliability.workspace_lock_manager import WorkspaceLockManager
from backend.services.task_service import TaskService


class TaskWorker:
    """Poll queued tasks and execute them sequentially on one machine."""

    def __init__(
        self,
        database: SQLiteDatabase,
        task_service: TaskService,
        *,
        lock_manager: WorkspaceLockManager | None = None,
        poll_interval: float = 1.0,
        heartbeat_interval: float = 5.0,
    ) -> None:
        self.database = database
        self.task_service = task_service
        self.lock_manager = lock_manager or WorkspaceLockManager(database)
        self.poll_interval = poll_interval
        self.heartbeat_interval = heartbeat_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._state_lock = threading.Lock()
        self._current_task_id: str | None = None
        self._accepting = False
        self.logger = StructuredLogger(database)

    @property
    def current_task_id(self) -> str | None:
        with self._state_lock:
            return self._current_task_id

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def accepting_tasks(self) -> bool:
        return self._accepting and not self._stop_event.is_set()

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._accepting = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name="auto-dev-task-worker",
            daemon=False,
        )
        self._thread.start()

    def stop(self, timeout: float | None = None) -> bool:
        self._accepting = False
        self._stop_event.set()
        thread = self._thread
        if thread is None:
            return True
        if thread is threading.current_thread():
            return False
        thread.join(timeout=timeout)
        return not thread.is_alive()

    def run_once(self) -> bool:
        if self._stop_event.is_set():
            return False
        self.database.promote_waiting_tasks()
        for task in self.database.list_queued_tasks(limit=100):
            if self._stop_event.is_set():
                return False
            if self._execute_task(
                task_id=task.task_id,
                workspace_path=task.workspace_path,
            ):
                return True
        return False

    def _run_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                self.run_once()
                self._stop_event.wait(self.poll_interval)
        finally:
            self._accepting = False

    def _execute_task(self, *, task_id: str, workspace_path: str) -> bool:
        lock = self.lock_manager.acquire(
            workspace_path=str(
                Path(workspace_path).expanduser().resolve()
            ),
            task_id=task_id,
        )
        if lock is None:
            return False

        heartbeat_done = threading.Event()
        heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(task_id, heartbeat_done),
            name=f"heartbeat-{task_id}",
            daemon=True,
        )
        with self._state_lock:
            self._current_task_id = task_id
        heartbeat_thread.start()
        try:
            self.task_service.run_task(task_id)
        except Exception as exc:
            try:
                current = self.database.get_task(task_id)
                if current is not None and current.status not in {
                    TaskStatus.PAUSED,
                    TaskStatus.CANCELED,
                }:
                    self.database.update_task(
                        task_id,
                        status=TaskStatus.FAILED,
                        blocked_reason=f"Worker execution failed: {exc}",
                        required_action="Review worker logs and retry manually",
                    )
                self.logger.log(
                    task_id=task_id,
                    event_type=EventType.ERROR,
                    level="ERROR",
                    message=f"Worker execution failed: {exc}",
                )
            except Exception:
                pass
        finally:
            heartbeat_done.set()
            heartbeat_thread.join(timeout=self.heartbeat_interval + 1)
            try:
                self.lock_manager.release(task_id=task_id)
            finally:
                with self._state_lock:
                    self._current_task_id = None
        return True

    def _heartbeat_loop(
        self, task_id: str, done: threading.Event
    ) -> None:
        while not done.is_set():
            try:
                self.database.heartbeat_task(task_id)
            except Exception:
                # Lifecycle persistence remains authoritative; a later
                # heartbeat or recovery scan will handle transient failures.
                pass
            done.wait(self.heartbeat_interval)
