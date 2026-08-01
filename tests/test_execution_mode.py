import subprocess

from backend.database.sqlite import SQLiteDatabase
from backend.models.task import ExecutionMode, TaskCreate, TaskStatus
from backend.runtime.agent_runtime import (
    AgentRuntime,
    RuntimeRequest,
    RuntimeResult,
    RuntimeStatus,
)
from backend.services.crew_service import CrewService
from backend.services.task_service import TaskService


class CountingRuntime(AgentRuntime):
    def __init__(
        self,
        agent_name: str,
        output: str,
        *,
        evidence=None,
    ) -> None:
        self.agent_name = agent_name
        self.output = output
        self.evidence = evidence
        self.calls = 0

    def run(self, request: RuntimeRequest) -> RuntimeResult:
        self.calls += 1
        return RuntimeResult(
            agent_name=self.agent_name,
            status=RuntimeStatus.COMPLETED,
            output=self.output,
            evidence=self.evidence,
        )


class CodexRuntime(CountingRuntime):
    execution_mode = "codex"


def build_service(tmp_path, developer):
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    supervisor = CountingRuntime("supervisor", "pilot plan")
    reviewer = CountingRuntime("reviewer", "PASS\naccepted")
    service = TaskService(
        database,
        CrewService(database, supervisor, developer, reviewer),
    )
    return database, service, supervisor, reviewer


def test_dry_run_stops_after_supervisor_without_calling_codex(
    tmp_path,
) -> None:
    developer = CodexRuntime("developer", "must not run")
    database, service, supervisor, reviewer = build_service(
        tmp_path, developer
    )
    task = service.create_task(
        TaskCreate(
            project_name="pilot dry run",
            workspace_path=str(tmp_path / "not-created"),
            goal="plan only",
            requirements=[],
        )
    )

    finished = service.run_task(task.task_id)

    assert task.execution_mode is ExecutionMode.DRY_RUN
    assert finished.status is TaskStatus.PASSED
    assert finished.supervisor_output == "pilot plan"
    assert finished.developer_output is None
    assert finished.reviewer_output is None
    assert supervisor.calls == 1
    assert developer.calls == 0
    assert reviewer.calls == 0
    assert [
        run.agent_name for run in database.list_agent_runs(task.task_id)
    ] == ["requirement_analyst", "supervisor"]
    assert database.list_task_artifacts(task.task_id) == []


def test_execute_mode_allows_codex_runtime(tmp_path) -> None:
    workspace = tmp_path / "repository"
    workspace.mkdir()
    subprocess.run(
        ["git", "init", str(workspace)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(workspace),
            "-c",
            "user.name=Auto Dev Test",
            "-c",
            "user.email=autodev@example.invalid",
            "commit",
            "--allow-empty",
            "-m",
            "baseline",
        ],
        check=True,
        capture_output=True,
    )
    developer = CodexRuntime(
        "developer",
        "code complete",
        evidence={
            "git_diff": "+ change",
            "changed_files": ["feature.py"],
            "test_results": [],
            "codex_output": "complete",
        },
    )
    _, service, supervisor, reviewer = build_service(tmp_path, developer)
    task = service.create_task(
        TaskCreate(
            project_name="pilot execute",
            workspace_path=str(workspace),
            goal="execute code change",
            requirements=[],
            execution_mode=ExecutionMode.EXECUTE,
        )
    )

    finished = service.run_task(task.task_id)

    assert finished.execution_mode is ExecutionMode.EXECUTE
    assert finished.status is TaskStatus.PASSED
    assert supervisor.calls == 1
    assert developer.calls == 1
    assert reviewer.calls == 1
