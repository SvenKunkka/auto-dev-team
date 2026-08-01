from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from backend.models.agent import WorkflowStep


class TaskStatus(StrEnum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    WAITING_DEPENDENCY = "WAITING_DEPENDENCY"
    RUNNING = "RUNNING"
    ANALYZING = "ANALYZING"
    RESEARCHING = "RESEARCHING"
    PLANNING = "PLANNING"
    REQUIREMENTS_REVISION = "REQUIREMENTS_REVISION"
    DEVELOPING = "DEVELOPING"
    VERIFYING = "VERIFYING"
    REVIEWING = "REVIEWING"
    REWORKING = "REWORKING"
    PAUSED = "PAUSED"
    CANCELED = "CANCELED"
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class ExecutionMode(StrEnum):
    DRY_RUN = "dry_run"
    EXECUTE = "execute"


class TaskCreate(BaseModel):
    project_name: str = Field(min_length=1)
    workspace_path: str = Field(min_length=1)
    goal: str = ""
    requirements: list[str] = Field(default_factory=list)
    priority: str = Field(default="normal", min_length=1)
    execution_mode: ExecutionMode = ExecutionMode.DRY_RUN
    max_retry: int = Field(default=3, ge=0, le=10)
    timeout_seconds: int = Field(default=3600, ge=1)
    selected_agents: list[str] = Field(
        default_factory=lambda: [
            "requirement_analyst",
            "supervisor",
            "developer",
            "verification_engineer",
            "reviewer",
        ]
    )
    agent_models: dict[str, str] = Field(default_factory=dict)
    workflow_steps: list[WorkflowStep] = Field(
        default_factory=list, max_length=200
    )


class TaskCreated(BaseModel):
    task_id: str
    status: TaskStatus


class TaskRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: str
    project_name: str
    workspace_path: str
    goal: str
    requirements: list[str]
    priority: str
    execution_mode: ExecutionMode
    predecessor_task_id: str | None = None
    sequence_no: int | None = None
    resume_stage: TaskStatus = TaskStatus.ANALYZING
    selected_agents: list[str]
    agent_models: dict[str, str]
    workflow_steps: list[WorkflowStep] = Field(default_factory=list)
    active_agent: str | None = None
    status: TaskStatus
    retry_count: int
    max_retry: int
    started_at: datetime | None = None
    last_heartbeat: datetime | None = None
    timeout_seconds: int
    blocked_reason: str | None = None
    required_action: str | None = None
    requirements_output: str | None = None
    supervisor_output: str | None = None
    developer_output: str | None = None
    verification_output: str | None = None
    reviewer_output: str | None = None
    created_at: datetime
    updated_at: datetime


class AgentRunRecord(BaseModel):
    id: int
    task_id: str
    agent_name: str
    input: str
    output: str | None = None
    status: str
    created_at: datetime


class TaskArtifactRecord(BaseModel):
    id: int
    task_id: str
    artifact_type: str
    content: str
    created_at: datetime


class TaskDocument(BaseModel):
    filename: str
    content_type: str
    size: int
    sha256: str
    storage_path: str


class TaskIterationRecord(BaseModel):
    id: int
    task_id: str
    iteration: int
    supervisor_output: str
    developer_output: str
    verification_output: str
    reviewer_output: str
    status: TaskStatus
    created_at: datetime


class WorkspaceLockRecord(BaseModel):
    id: int
    workspace_path: str
    task_id: str
    locked_at: datetime
    released_at: datetime | None = None
    status: str


class ExecutionLogRecord(BaseModel):
    id: int
    task_id: str
    agent_name: str | None = None
    event_type: str
    level: str
    message: str
    created_at: datetime


class EvidenceSummary(BaseModel):
    artifact_count: int = 0
    artifact_types: list[str] = Field(default_factory=list)
    changed_files_count: int = 0
    test_count: int = 0
    failed_test_count: int = 0


class SpecialistOutput(BaseModel):
    step_id: str = ""
    order: int = 0
    agent_id: str
    agent_name: str
    model: str
    output: str
    evidence: dict = Field(default_factory=dict)


class TaskDetail(TaskRecord):
    current_agent: str | None = None
    iteration: int
    heartbeat: datetime | None = None
    evidence_summary: EvidenceSummary
    documents: list[TaskDocument] = Field(default_factory=list)
    specialist_outputs: list[SpecialistOutput] = Field(default_factory=list)
    logs: list[ExecutionLogRecord] = Field(default_factory=list)
