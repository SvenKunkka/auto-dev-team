from __future__ import annotations

import logging
from enum import StrEnum

from backend.database.sqlite import SQLiteDatabase
from backend.models.task import ExecutionLogRecord


class EventType(StrEnum):
    TASK_CREATED = "TASK_CREATED"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    TASK_STARTED = "TASK_STARTED"
    REQUIREMENT_ANALYSIS_STARTED = "REQUIREMENT_ANALYSIS_STARTED"
    REQUIREMENT_ANALYSIS_FINISHED = "REQUIREMENT_ANALYSIS_FINISHED"
    SPECIALIST_STARTED = "SPECIALIST_STARTED"
    SPECIALIST_FINISHED = "SPECIALIST_FINISHED"
    SUPERVISOR_STARTED = "SUPERVISOR_STARTED"
    SUPERVISOR_FINISHED = "SUPERVISOR_FINISHED"
    DEVELOPER_STARTED = "DEVELOPER_STARTED"
    CODEX_STARTED = "CODEX_STARTED"
    WORKSPACE_VALIDATED = "WORKSPACE_VALIDATED"
    TASK_WORKSPACE_PREPARED = "TASK_WORKSPACE_PREPARED"
    TASK_WORKSPACE_PRESERVED = "TASK_WORKSPACE_PRESERVED"
    TASK_COMMIT_INTEGRATED = "TASK_COMMIT_INTEGRATED"
    REQUIREMENTS_REVISION_REQUIRED = "REQUIREMENTS_REVISION_REQUIRED"
    CODE_CHANGE_STARTED = "CODE_CHANGE_STARTED"
    CODE_CHANGE_FINISHED = "CODE_CHANGE_FINISHED"
    GIT_COMMIT_CREATED = "GIT_COMMIT_CREATED"
    TEST_STARTED = "TEST_STARTED"
    VERIFICATION_STARTED = "VERIFICATION_STARTED"
    VERIFICATION_FINISHED = "VERIFICATION_FINISHED"
    REVIEW_STARTED = "REVIEW_STARTED"
    REWORK_STARTED = "REWORK_STARTED"
    TASK_FINISHED = "TASK_FINISHED"
    TASK_PAUSED = "TASK_PAUSED"
    TASK_CANCELED = "TASK_CANCELED"
    TASK_RETRIED = "TASK_RETRIED"
    ERROR = "ERROR"


class StructuredLogger:
    """Persist task lifecycle events and mirror them to Python logging."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database
        self._logger = logging.getLogger("auto_dev_platform.execution")

    def log(
        self,
        *,
        task_id: str,
        event_type: EventType | str,
        message: str,
        agent_name: str | None = None,
        level: str = "INFO",
    ) -> ExecutionLogRecord:
        event = (
            event_type.value
            if isinstance(event_type, EventType)
            else event_type
        )
        normalized_level = level.upper()
        record = self.database.create_execution_log(
            task_id=task_id,
            agent_name=agent_name,
            event_type=event,
            level=normalized_level,
            message=message,
        )
        self._logger.log(
            getattr(logging, normalized_level, logging.INFO),
            "%s task_id=%s agent=%s %s",
            event,
            task_id,
            agent_name or "-",
            message,
        )
        return record
