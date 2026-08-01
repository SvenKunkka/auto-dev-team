from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RuntimeStatus(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    REQUIREMENTS_REVISION = "REQUIREMENTS_REVISION"


class RuntimeRequest(BaseModel):
    task_id: str
    project_name: str
    workspace_path: str = ""
    goal: str
    requirements: list[str] = Field(default_factory=list)
    previous_outputs: dict[str, str] = Field(default_factory=dict)


class RuntimeResult(BaseModel):
    agent_name: str
    status: RuntimeStatus
    output: str
    error: str | None = None
    evidence: dict[str, Any] | None = None


class AgentRuntime(ABC):
    """HTTP与持久化无关的单Agent运行接口。"""

    agent_name: str

    @abstractmethod
    def run(self, request: RuntimeRequest) -> RuntimeResult:
        raise NotImplementedError
