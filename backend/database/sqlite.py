from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.models.task import (
    AgentRunRecord,
    ExecutionLogRecord,
    TaskArtifactRecord,
    TaskCreate,
    TaskIterationRecord,
    TaskRecord,
    TaskStatus,
    WorkspaceLockRecord,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "auto_dev_team.db"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class SQLiteDatabase:
    """Small SQLite repository with one connection per operation."""

    def __init__(self, database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
        self.database_path = Path(database_path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL UNIQUE,
                    project_name TEXT NOT NULL,
                    workspace_path TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    requirements TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    execution_mode TEXT NOT NULL DEFAULT 'dry_run',
                    predecessor_task_id TEXT,
                    sequence_no INTEGER,
                    resume_stage TEXT NOT NULL DEFAULT 'ANALYZING',
                    selected_agents TEXT NOT NULL DEFAULT '["requirement_analyst","supervisor","developer","verification_engineer","reviewer"]',
                    agent_models TEXT NOT NULL DEFAULT '{}',
                    workflow_steps TEXT NOT NULL DEFAULT '[]',
                    active_agent TEXT,
                    status TEXT NOT NULL,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retry INTEGER NOT NULL DEFAULT 3,
                    started_at TEXT,
                    last_heartbeat TEXT,
                    timeout_seconds INTEGER NOT NULL DEFAULT 3600,
                    blocked_reason TEXT,
                    required_action TEXT,
                    requirements_output TEXT,
                    supervisor_output TEXT,
                    developer_output TEXT,
                    verification_output TEXT,
                    reviewer_output TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (predecessor_task_id) REFERENCES tasks(task_id)
                );

                CREATE TABLE IF NOT EXISTS agent_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    input TEXT NOT NULL,
                    output TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                );

                CREATE INDEX IF NOT EXISTS idx_agent_runs_task_id
                    ON agent_runs(task_id);

                CREATE TABLE IF NOT EXISTS task_artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                );

                CREATE INDEX IF NOT EXISTS idx_task_artifacts_task_id
                    ON task_artifacts(task_id);

                CREATE TABLE IF NOT EXISTS task_iterations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    iteration INTEGER NOT NULL,
                    supervisor_output TEXT NOT NULL,
                    developer_output TEXT NOT NULL,
                    verification_output TEXT NOT NULL DEFAULT '',
                    reviewer_output TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id),
                    UNIQUE (task_id, iteration)
                );

                CREATE INDEX IF NOT EXISTS idx_task_iterations_task_id
                    ON task_iterations(task_id);

                CREATE TABLE IF NOT EXISTS workspace_locks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_path TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    locked_at TEXT NOT NULL,
                    released_at TEXT,
                    status TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                );

                CREATE UNIQUE INDEX IF NOT EXISTS
                    idx_workspace_locks_active_workspace
                    ON workspace_locks(workspace_path)
                    WHERE status = 'ACTIVE';

                CREATE TABLE IF NOT EXISTS execution_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    agent_name TEXT,
                    event_type TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                );

                CREATE INDEX IF NOT EXISTS idx_execution_logs_task_id
                    ON execution_logs(task_id, id);

                CREATE TABLE IF NOT EXISTS model_configs (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    base_url TEXT NOT NULL DEFAULT '',
                    api_style TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    capabilities TEXT NOT NULL DEFAULT '[]',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    credential_ref TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            self._ensure_task_columns(connection)

    def create_task(self, task_id: str, task: TaskCreate) -> TaskRecord:
        timestamp = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            predecessor = connection.execute(
                """
                SELECT task_id, sequence_no
                FROM tasks
                WHERE workspace_path = ? AND sequence_no IS NOT NULL
                ORDER BY sequence_no DESC, id DESC
                LIMIT 1
                """,
                (task.workspace_path,),
            ).fetchone()
            predecessor_task_id = (
                str(predecessor["task_id"])
                if predecessor is not None
                else None
            )
            sequence_no = (
                int(predecessor["sequence_no"]) + 1
                if predecessor is not None
                else 1
            )
            connection.execute(
                """
                INSERT INTO tasks (
                    task_id, project_name, workspace_path, goal, requirements,
                    priority, execution_mode, predecessor_task_id, sequence_no,
                    resume_stage, selected_agents, agent_models,
                    workflow_steps, active_agent,
                    status, retry_count, max_retry,
                    timeout_seconds, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    task.project_name,
                    task.workspace_path,
                    task.goal,
                    json.dumps(task.requirements, ensure_ascii=False),
                    task.priority,
                    task.execution_mode.value,
                    predecessor_task_id,
                    sequence_no,
                    TaskStatus.ANALYZING.value,
                    json.dumps(task.selected_agents, ensure_ascii=False),
                    json.dumps(task.agent_models, ensure_ascii=False),
                    json.dumps(
                        [
                            step.model_dump(mode="json")
                            for step in task.workflow_steps
                        ],
                        ensure_ascii=False,
                    ),
                    None,
                    TaskStatus.CREATED.value,
                    0,
                    task.max_retry,
                    task.timeout_seconds,
                    timestamp,
                    timestamp,
                ),
            )
        created = self.get_task(task_id)
        if created is None:
            raise RuntimeError(f"任务创建后无法读取：{task_id}")
        return created

    def get_task(self, task_id: str) -> TaskRecord | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
        return self._task_from_row(row) if row else None

    def list_tasks(self) -> list[TaskRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [self._task_from_row(row) for row in rows]

    def update_task(
        self,
        task_id: str,
        *,
        status: TaskStatus | None = None,
        retry_count: int | None = None,
        resume_stage: TaskStatus | None = None,
        started_at: str | None = None,
        last_heartbeat: str | None = None,
        blocked_reason: str | None = None,
        required_action: str | None = None,
        requirements_output: str | None = None,
        supervisor_output: str | None = None,
        developer_output: str | None = None,
        verification_output: str | None = None,
        reviewer_output: str | None = None,
        active_agent: str | None = None,
    ) -> TaskRecord:
        heartbeat = utc_now()
        updates: dict[str, Any] = {
            "updated_at": heartbeat,
            "last_heartbeat": heartbeat,
        }
        if status is not None:
            updates["status"] = status.value
        if retry_count is not None:
            updates["retry_count"] = retry_count
        if resume_stage is not None:
            updates["resume_stage"] = resume_stage.value
        if started_at is not None:
            updates["started_at"] = started_at
        if last_heartbeat is not None:
            updates["last_heartbeat"] = last_heartbeat
        if blocked_reason is not None:
            updates["blocked_reason"] = blocked_reason
        if required_action is not None:
            updates["required_action"] = required_action
        if requirements_output is not None:
            updates["requirements_output"] = requirements_output
        if supervisor_output is not None:
            updates["supervisor_output"] = supervisor_output
        if developer_output is not None:
            updates["developer_output"] = developer_output
        if verification_output is not None:
            updates["verification_output"] = verification_output
        if reviewer_output is not None:
            updates["reviewer_output"] = reviewer_output
        if active_agent is not None:
            updates["active_agent"] = active_agent

        assignments = ", ".join(f"{column} = ?" for column in updates)
        values = [*updates.values(), task_id]
        with self.connect() as connection:
            cursor = connection.execute(
                f"UPDATE tasks SET {assignments} WHERE task_id = ?", values
            )
            if cursor.rowcount == 0:
                raise KeyError(f"任务不存在：{task_id}")

        updated = self.get_task(task_id)
        if updated is None:
            raise RuntimeError(f"任务更新后无法读取：{task_id}")
        return updated

    def transition_task_status(
        self,
        task_id: str,
        *,
        status: TaskStatus,
        allowed_from: set[TaskStatus],
        started_at: str | None = None,
    ) -> TaskRecord:
        """Atomically transition a task without overriding human control."""
        timestamp = utc_now()
        allowed_values = tuple(item.value for item in allowed_from)
        placeholders = ", ".join("?" for _ in allowed_values)
        assignments = [
            "status = ?",
            "updated_at = ?",
            "last_heartbeat = ?",
        ]
        values: list[Any] = [status.value, timestamp, timestamp]
        if started_at is not None:
            assignments.append("started_at = ?")
            values.append(started_at)
        values.extend([task_id, *allowed_values])
        with self.connect() as connection:
            connection.execute(
                f"""
                UPDATE tasks SET {", ".join(assignments)}
                WHERE task_id = ? AND status IN ({placeholders})
                """,
                values,
            )
        task = self.get_task(task_id)
        if task is None:
            raise KeyError(f"任务不存在：{task_id}")
        return task

    def create_agent_run(
        self,
        *,
        task_id: str,
        agent_name: str,
        input_text: str,
        output: str | None,
        status: str,
    ) -> AgentRunRecord:
        timestamp = utc_now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO agent_runs (
                    task_id, agent_name, input, output, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, agent_name, input_text, output, status, timestamp),
            )
            row = connection.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        if row is None:
            raise RuntimeError("Agent运行记录创建失败")
        return AgentRunRecord(**dict(row))

    def list_agent_runs(self, task_id: str) -> list[AgentRunRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM agent_runs WHERE task_id = ? ORDER BY id",
                (task_id,),
            ).fetchall()
        return [AgentRunRecord(**dict(row)) for row in rows]

    def count_agent_runs(
        self, *, task_id: str | None = None
    ) -> dict[str, int]:
        query = "SELECT agent_name, COUNT(*) AS count FROM agent_runs"
        parameters: tuple[str, ...] = ()
        if task_id is not None:
            query += " WHERE task_id = ?"
            parameters = (task_id,)
        query += " GROUP BY agent_name"
        with self.connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return {str(row["agent_name"]): int(row["count"]) for row in rows}

    def create_task_artifact(
        self,
        *,
        task_id: str,
        artifact_type: str,
        content: str,
    ) -> TaskArtifactRecord:
        timestamp = utc_now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO task_artifacts (
                    task_id, artifact_type, content, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (task_id, artifact_type, content, timestamp),
            )
            row = connection.execute(
                "SELECT * FROM task_artifacts WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        if row is None:
            raise RuntimeError("任务证据创建失败")
        return TaskArtifactRecord(**dict(row))

    def list_task_artifacts(self, task_id: str) -> list[TaskArtifactRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM task_artifacts WHERE task_id = ? ORDER BY id",
                (task_id,),
            ).fetchall()
        return [TaskArtifactRecord(**dict(row)) for row in rows]

    def create_task_iteration(
        self,
        *,
        task_id: str,
        iteration: int,
        supervisor_output: str,
        developer_output: str,
        reviewer_output: str,
        status: TaskStatus,
        verification_output: str = "",
    ) -> TaskIterationRecord:
        timestamp = utc_now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO task_iterations (
                    task_id, iteration, supervisor_output, developer_output,
                    verification_output, reviewer_output, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    iteration,
                    supervisor_output,
                    developer_output,
                    verification_output,
                    reviewer_output,
                    status.value,
                    timestamp,
                ),
            )
            row = connection.execute(
                "SELECT * FROM task_iterations WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        if row is None:
            raise RuntimeError("任务迭代记录创建失败")
        return TaskIterationRecord(**dict(row))

    def list_task_iterations(self, task_id: str) -> list[TaskIterationRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM task_iterations WHERE task_id = ? "
                "ORDER BY iteration",
                (task_id,),
            ).fetchall()
        return [TaskIterationRecord(**dict(row)) for row in rows]

    def list_nonterminal_tasks(self) -> list[TaskRecord]:
        recoverable = (
            TaskStatus.CREATED.value,
            TaskStatus.QUEUED.value,
            TaskStatus.RUNNING.value,
            TaskStatus.ANALYZING.value,
            TaskStatus.RESEARCHING.value,
            TaskStatus.PLANNING.value,
            TaskStatus.DEVELOPING.value,
            TaskStatus.VERIFYING.value,
            TaskStatus.REVIEWING.value,
            TaskStatus.REWORKING.value,
        )
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM tasks WHERE status IN (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ORDER BY created_at, id",
                recoverable,
            ).fetchall()
        return [self._task_from_row(row) for row in rows]

    def list_queued_tasks(self, *, limit: int = 1) -> list[TaskRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT child.*
                FROM tasks child
                LEFT JOIN tasks predecessor
                  ON predecessor.task_id = child.predecessor_task_id
                WHERE child.status = ?
                  AND (
                    child.predecessor_task_id IS NULL
                    OR predecessor.status IN (?, ?)
                  )
                ORDER BY child.created_at, child.id
                LIMIT ?
                """,
                (
                    TaskStatus.QUEUED.value,
                    TaskStatus.PASSED.value,
                    TaskStatus.CANCELED.value,
                    limit,
                ),
            ).fetchall()
        return [self._task_from_row(row) for row in rows]

    def enqueue_task_in_order(self, task_id: str) -> TaskRecord:
        """Queue a task only when its recorded predecessor is complete."""
        timestamp = utc_now()
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT child.predecessor_task_id,
                       predecessor.status AS predecessor_status
                FROM tasks child
                LEFT JOIN tasks predecessor
                  ON predecessor.task_id = child.predecessor_task_id
                WHERE child.task_id = ?
                """,
                (task_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"任务不存在：{task_id}")
            ready = (
                row["predecessor_task_id"] is None
                or row["predecessor_status"]
                in {TaskStatus.PASSED.value, TaskStatus.CANCELED.value}
            )
            status = (
                TaskStatus.QUEUED
                if ready
                else TaskStatus.WAITING_DEPENDENCY
            )
            connection.execute(
                """
                UPDATE tasks
                SET status = ?, last_heartbeat = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (status.value, timestamp, timestamp, task_id),
            )
        task = self.get_task(task_id)
        if task is None:
            raise RuntimeError(f"任务入队后无法读取：{task_id}")
        return task

    def promote_waiting_tasks(self) -> int:
        timestamp = utc_now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE tasks
                SET status = ?, last_heartbeat = ?, updated_at = ?
                WHERE status = ?
                  AND (
                    predecessor_task_id IS NULL
                    OR EXISTS (
                        SELECT 1
                        FROM tasks predecessor
                        WHERE predecessor.task_id = tasks.predecessor_task_id
                          AND predecessor.status IN (?, ?)
                    )
                  )
                """,
                (
                    TaskStatus.QUEUED.value,
                    timestamp,
                    timestamp,
                    TaskStatus.WAITING_DEPENDENCY.value,
                    TaskStatus.PASSED.value,
                    TaskStatus.CANCELED.value,
                ),
            )
        return cursor.rowcount

    def heartbeat_task(self, task_id: str) -> bool:
        timestamp = utc_now()
        active_statuses = (
            TaskStatus.RUNNING.value,
            TaskStatus.ANALYZING.value,
            TaskStatus.RESEARCHING.value,
            TaskStatus.PLANNING.value,
            TaskStatus.DEVELOPING.value,
            TaskStatus.VERIFYING.value,
            TaskStatus.REVIEWING.value,
            TaskStatus.REWORKING.value,
        )
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE tasks
                SET last_heartbeat = ?, updated_at = ?
                WHERE task_id = ? AND status IN (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (timestamp, timestamp, task_id, *active_statuses),
            )
        return cursor.rowcount > 0

    def acquire_workspace_lock(
        self, *, workspace_path: str, task_id: str
    ) -> WorkspaceLockRecord | None:
        timestamp = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM workspace_locks "
                "WHERE workspace_path = ? AND status = 'ACTIVE'",
                (workspace_path,),
            ).fetchone()
            if existing is not None:
                if existing["task_id"] == task_id:
                    return WorkspaceLockRecord(**dict(existing))
                return None
            cursor = connection.execute(
                """
                INSERT INTO workspace_locks (
                    workspace_path, task_id, locked_at, status
                ) VALUES (?, ?, ?, 'ACTIVE')
                """,
                (workspace_path, task_id, timestamp),
            )
            row = connection.execute(
                "SELECT * FROM workspace_locks WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        if row is None:
            raise RuntimeError("工作区锁创建失败")
        return WorkspaceLockRecord(**dict(row))

    def release_workspace_lock(self, *, task_id: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE workspace_locks
                SET status = 'RELEASED', released_at = ?
                WHERE task_id = ? AND status = 'ACTIVE'
                """,
                (utc_now(), task_id),
            )

    def cleanup_active_workspace_locks(self) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE workspace_locks
                SET status = 'STALE', released_at = ?
                WHERE status = 'ACTIVE'
                """,
                (utc_now(),),
            )
        return cursor.rowcount

    def list_workspace_locks(self) -> list[WorkspaceLockRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM workspace_locks ORDER BY id"
            ).fetchall()
        return [WorkspaceLockRecord(**dict(row)) for row in rows]

    def create_execution_log(
        self,
        *,
        task_id: str,
        event_type: str,
        level: str,
        message: str,
        agent_name: str | None = None,
    ) -> ExecutionLogRecord:
        timestamp = utc_now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO execution_logs (
                    task_id, agent_name, event_type, level, message, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    agent_name,
                    event_type,
                    level,
                    message,
                    timestamp,
                ),
            )
            row = connection.execute(
                "SELECT * FROM execution_logs WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        if row is None:
            raise RuntimeError("执行日志创建失败")
        return ExecutionLogRecord(**dict(row))

    def list_execution_logs(
        self, task_id: str
    ) -> list[ExecutionLogRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM execution_logs WHERE task_id = ? ORDER BY id",
                (task_id,),
            ).fetchall()
        return [ExecutionLogRecord(**dict(row)) for row in rows]

    def count_queued_tasks(self) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM tasks WHERE status IN (?, ?)",
                (
                    TaskStatus.QUEUED.value,
                    TaskStatus.WAITING_DEPENDENCY.value,
                ),
            ).fetchone()
        return int(row["count"])

    def health_check(self) -> bool:
        try:
            with self.connect() as connection:
                return connection.execute("SELECT 1").fetchone()[0] == 1
        except sqlite3.Error:
            return False

    def reset_task_for_retry(self, task_id: str) -> TaskRecord:
        timestamp = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                """
                SELECT workspace_path, sequence_no, status
                FROM tasks WHERE task_id = ?
                """,
                (task_id,),
            ).fetchone()
            if current is None:
                raise KeyError(f"任务不存在：{task_id}")
            if current["sequence_no"] is None:
                predecessor = connection.execute(
                    """
                    SELECT task_id, sequence_no
                    FROM tasks
                    WHERE workspace_path = ? AND sequence_no IS NOT NULL
                      AND task_id != ?
                    ORDER BY sequence_no DESC, id DESC
                    LIMIT 1
                    """,
                    (current["workspace_path"], task_id),
                ).fetchone()
                predecessor_task_id = (
                    str(predecessor["task_id"])
                    if predecessor is not None
                    else None
                )
                sequence_no = (
                    int(predecessor["sequence_no"]) + 1
                    if predecessor is not None
                    else 1
                )
                connection.execute(
                    """
                    UPDATE tasks
                    SET predecessor_task_id = ?, sequence_no = ?
                    WHERE task_id = ?
                    """,
                    (predecessor_task_id, sequence_no, task_id),
                )
            cursor = connection.execute(
                """
                UPDATE tasks
                SET retry_count = 0, started_at = NULL,
                    blocked_reason = NULL, required_action = NULL,
                    resume_stage = CASE
                        WHEN ? = ? THEN ?
                        ELSE resume_stage
                    END,
                    last_heartbeat = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (
                    current["status"],
                    TaskStatus.REQUIREMENTS_REVISION.value,
                    TaskStatus.ANALYZING.value,
                    timestamp,
                    timestamp,
                    task_id,
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"任务不存在：{task_id}")
            if (
                current["status"]
                == TaskStatus.REQUIREMENTS_REVISION.value
            ):
                connection.execute(
                    """
                    DELETE FROM task_artifacts
                    WHERE task_id = ? AND artifact_type = 'specialist_output'
                    """,
                    (task_id,),
                )
                connection.execute(
                    """
                    UPDATE tasks
                    SET requirements_output = NULL,
                        supervisor_output = NULL,
                        active_agent = NULL
                    WHERE task_id = ?
                    """,
                    (task_id,),
                )
        return self.enqueue_task_in_order(task_id)

    @staticmethod
    def _ensure_task_columns(connection: sqlite3.Connection) -> None:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(tasks)")
        }
        if "retry_count" not in columns:
            connection.execute(
                "ALTER TABLE tasks ADD COLUMN "
                "retry_count INTEGER NOT NULL DEFAULT 0"
            )
        if "max_retry" not in columns:
            connection.execute(
                "ALTER TABLE tasks ADD COLUMN "
                "max_retry INTEGER NOT NULL DEFAULT 3"
            )
        additions = {
            "started_at": "TEXT",
            "last_heartbeat": "TEXT",
            "timeout_seconds": "INTEGER NOT NULL DEFAULT 3600",
            "blocked_reason": "TEXT",
            "required_action": "TEXT",
            "requirements_output": "TEXT",
            "verification_output": "TEXT",
            "predecessor_task_id": "TEXT",
            "sequence_no": "INTEGER",
            "resume_stage": "TEXT NOT NULL DEFAULT 'ANALYZING'",
            "selected_agents": (
                "TEXT NOT NULL DEFAULT "
                """'["requirement_analyst","supervisor","developer","verification_engineer","reviewer"]'"""
            ),
            "agent_models": "TEXT NOT NULL DEFAULT '{}'",
            "workflow_steps": "TEXT NOT NULL DEFAULT '[]'",
            "active_agent": "TEXT",
        }
        for column, definition in additions.items():
            if column not in columns:
                connection.execute(
                    f"ALTER TABLE tasks ADD COLUMN {column} {definition}"
                )
        if "execution_mode" not in columns:
            connection.execute(
                "ALTER TABLE tasks ADD COLUMN execution_mode "
                "TEXT NOT NULL DEFAULT 'dry_run'"
            )
            # Tasks created before Phase 7 belonged to the former
            # execute-only system and must retain their original semantics.
            connection.execute(
                "UPDATE tasks SET execution_mode = 'execute'"
            )
        iteration_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(task_iterations)"
            )
        }
        if "verification_output" not in iteration_columns:
            connection.execute(
                "ALTER TABLE task_iterations ADD COLUMN "
                "verification_output TEXT NOT NULL DEFAULT ''"
            )

    @staticmethod
    def _task_from_row(row: sqlite3.Row) -> TaskRecord:
        values = dict(row)
        values["requirements"] = json.loads(values["requirements"])
        values["selected_agents"] = json.loads(values["selected_agents"])
        values["agent_models"] = json.loads(values["agent_models"])
        values["workflow_steps"] = json.loads(
            values.get("workflow_steps") or "[]"
        )
        return TaskRecord(**values)
