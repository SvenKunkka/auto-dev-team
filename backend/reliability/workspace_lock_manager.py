from __future__ import annotations

from pathlib import Path

from backend.database.sqlite import SQLiteDatabase
from backend.models.task import WorkspaceLockRecord


class WorkspaceLockManager:
    """SQLite-backed exclusive lock for one task per workspace."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def acquire(
        self, *, workspace_path: str, task_id: str
    ) -> WorkspaceLockRecord | None:
        canonical_path = str(
            Path(workspace_path).expanduser().resolve()
        )
        return self.database.acquire_workspace_lock(
            workspace_path=canonical_path,
            task_id=task_id,
        )

    def release(self, *, task_id: str) -> None:
        self.database.release_workspace_lock(task_id=task_id)

    def cleanup_after_restart(self) -> int:
        return self.database.cleanup_active_workspace_locks()
