import json
import subprocess

from backend.database.sqlite import SQLiteDatabase
from backend.models.task import TaskCreate, TaskStatus
from backend.runtime.agent_runtime import (
    AgentRuntime,
    RuntimeRequest,
    RuntimeResult,
    RuntimeStatus,
)
from backend.safety.workspace_validator import WorkspaceValidator
from backend.services.crew_service import CrewService
from backend.services.task_service import TaskService


def test_valid_git_workspace(tmp_path) -> None:
    workspace = tmp_path / "repository"
    workspace.mkdir()
    subprocess.run(
        ["git", "init", str(workspace)],
        check=True,
        capture_output=True,
    )

    result = WorkspaceValidator().validate(workspace)

    assert result.valid is True
    assert result.is_git_repository is True
    assert result.git_root == str(workspace)


def test_missing_workspace_is_invalid(tmp_path) -> None:
    result = WorkspaceValidator().validate(tmp_path / "missing")

    assert result.valid is False
    assert result.is_git_repository is False
    assert result.error is not None
    assert result.error.startswith("Workspace does not exist:")


def test_non_git_directory_is_invalid(tmp_path) -> None:
    workspace = tmp_path / "plain-directory"
    workspace.mkdir()

    result = WorkspaceValidator().validate(workspace)

    assert result.valid is False
    assert result.error is not None
    assert "not a Git repository" in result.error


def test_production_rejects_workspace_outside_allowed_root(
    tmp_path, monkeypatch
) -> None:
    allowed_root = tmp_path / "production-workspaces"
    allowed_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    subprocess.run(
        ["git", "init", str(outside)],
        check=True,
        capture_output=True,
    )
    monkeypatch.setenv("AUTO_DEV_ENV", "production")
    monkeypatch.setenv(
        "AUTO_DEV_WORKSPACES_ROOT", str(allowed_root)
    )

    result = WorkspaceValidator().validate(outside)

    assert result.valid is False
    assert result.error == (
        f"Workspace is outside allowed root: {allowed_root}"
    )


class FixedRuntime(AgentRuntime):
    def __init__(self, agent_name: str, output: str) -> None:
        self.agent_name = agent_name
        self.output = output
        self.calls = 0

    def run(self, request: RuntimeRequest) -> RuntimeResult:
        self.calls += 1
        return RuntimeResult(
            agent_name=self.agent_name,
            status=RuntimeStatus.COMPLETED,
            output=self.output,
        )


class CodexRuntimeThatMustNotRun(FixedRuntime):
    execution_mode = "codex"


def test_invalid_workspace_blocks_before_developer(tmp_path) -> None:
    workspace = tmp_path / "plain-directory"
    workspace.mkdir()
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    developer = CodexRuntimeThatMustNotRun("developer", "not executed")
    service = TaskService(
        database,
        CrewService(
            database,
            FixedRuntime("supervisor", "plan"),
            developer,
            FixedRuntime("reviewer", "PASS"),
        ),
    )
    task = service.create_task(
        TaskCreate(
            project_name="workspace validation",
            workspace_path=str(workspace),
            goal="validate before execution",
            requirements=[],
            execution_mode="execute",
        )
    )

    finished = service.run_task(task.task_id)

    assert finished.status is TaskStatus.BLOCKED
    assert developer.calls == 0
    artifacts = database.list_task_artifacts(task.task_id)
    validation = next(
        item for item in artifacts
        if item.artifact_type == "workspace_validation"
    )
    assert json.loads(validation.content)["valid"] is False
