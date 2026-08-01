from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from backend.database.sqlite import SQLiteDatabase
from backend.models.task import TaskRecord, TaskStatus
from backend.reliability.workspace_lock_manager import WorkspaceLockManager


class RecoveryReport(BaseModel):
    recovered_task_ids: list[str] = Field(default_factory=list)
    failed_task_ids: list[str] = Field(default_factory=list)
    blocked_task_ids: list[str] = Field(default_factory=list)
    cleaned_locks: int = 0


class RecoveryManager:
    """Recover nonterminal tasks after a single-machine service restart."""

    def __init__(
        self,
        database: SQLiteDatabase,
        task_runner: Callable[[str], TaskRecord],
        *,
        lock_manager: WorkspaceLockManager | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.database = database
        self.task_runner = task_runner
        self.lock_manager = lock_manager or WorkspaceLockManager(database)
        self.clock = clock or (lambda: datetime.now(UTC))

    def recover_on_startup(self) -> RecoveryReport:
        report = RecoveryReport(
            cleaned_locks=self.lock_manager.cleanup_after_restart()
        )
        for task in self.database.list_nonterminal_tasks():
            if self._is_timed_out(task):
                self.database.update_task(
                    task.task_id,
                    status=TaskStatus.FAILED,
                    blocked_reason="Task timed out",
                    required_action="Review task logs and restart manually",
                )
                report.failed_task_ids.append(task.task_id)
                continue

            workspace = Path(task.workspace_path).expanduser().resolve()
            if not workspace.is_dir():
                self.database.update_task(
                    task.task_id,
                    status=TaskStatus.BLOCKED,
                    blocked_reason="Workspace is unavailable",
                    required_action="Restore or correct workspace_path",
                )
                report.blocked_task_ids.append(task.task_id)
                continue

            self.database.update_task(
                task.task_id, status=TaskStatus.QUEUED
            )
            try:
                self.task_runner(task.task_id)
                report.recovered_task_ids.append(task.task_id)
            except Exception as exc:
                self.database.update_task(
                    task.task_id,
                    status=TaskStatus.FAILED,
                    blocked_reason=f"Recovery failed: {exc}",
                    required_action="Review recovery logs and retry manually",
                )
                report.failed_task_ids.append(task.task_id)
        return report

    def _is_timed_out(self, task: TaskRecord) -> bool:
        reference = (
            task.last_heartbeat or task.started_at or task.updated_at
        )
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)
        return (self.clock() - reference).total_seconds() > task.timeout_seconds
