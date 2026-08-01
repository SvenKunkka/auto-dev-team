import subprocess

from backend.adapters.codex_cli_adapter import (
    CodexExecutionResult,
    CodexExecutionStatus,
)
from backend.database.sqlite import SQLiteDatabase
from backend.evidence.git_committer import GitCommitResult, GitCommitter
from backend.evidence.workspace_cleaner import WorkspaceCleaner
from backend.models.task import TaskCreate, TaskStatus
from backend.runtime.agent_runtime import (
    AgentRuntime,
    RuntimeRequest,
    RuntimeResult,
    RuntimeStatus,
)
from backend.runtime.developer_runtime import DeveloperRuntime
from backend.services.crew_service import CrewService
from backend.services.task_service import TaskService


def initialize_repository(workspace) -> None:
    workspace.mkdir()
    subprocess.run(
        ["git", "init", str(workspace)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(workspace), "config", "user.name", "Auto Dev Test"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(workspace),
            "config",
            "user.email",
            "auto-dev@example.invalid",
        ],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(workspace),
            "commit",
            "--allow-empty",
            "-m",
            "baseline",
        ],
        check=True,
        capture_output=True,
    )


def test_git_commit_is_created(tmp_path) -> None:
    workspace = tmp_path / "repository"
    initialize_repository(workspace)
    (workspace / "feature.py").write_text("enabled = True\n")

    result = GitCommitter().commit(
        workspace_path=workspace,
        task_id="task-commit",
    )

    assert result.created is True
    assert result.commit_hash is not None
    head = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert result.commit_hash == head


def test_workspace_cleaner_removes_only_untracked_cache_artifacts(
    tmp_path,
) -> None:
    workspace = tmp_path / "repository"
    initialize_repository(workspace)
    source = workspace / "feature.py"
    source.write_text("enabled = True\n")
    subprocess.run(
        ["git", "-C", str(workspace), "add", "feature.py"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(workspace), "commit", "-m", "baseline"],
        check=True,
        capture_output=True,
    )
    cache = workspace / "__pycache__"
    cache.mkdir()
    (cache / "feature.cpython-312.pyc").write_bytes(b"cache")
    keep = workspace / "notes.txt"
    keep.write_text("keep me\n")

    removed = WorkspaceCleaner().remove_transient_artifacts(workspace)

    assert removed == ["__pycache__/feature.cpython-312.pyc"]
    assert not cache.exists()
    assert keep.exists()


def test_commit_failure_does_not_fail_developer(tmp_path) -> None:
    workspace = tmp_path / "repository"
    initialize_repository(workspace)

    class FakeCodexAdapter:
        def execute(self, request):
            return CodexExecutionResult(
                status=CodexExecutionStatus.COMPLETED,
                output="development complete",
                commands=[["codex", "exec"]],
            )

    class FailingCommitter:
        def commit(self, **kwargs):
            return GitCommitResult(
                created=False,
                error="nothing to commit",
            )

    result = DeveloperRuntime(
        execution_mode="codex",
        codex_adapter=FakeCodexAdapter(),  # type: ignore[arg-type]
        git_committer=FailingCommitter(),  # type: ignore[arg-type]
    ).run(
        RuntimeRequest(
            task_id="task-commit-failure",
            project_name="commit",
            workspace_path=str(workspace),
            goal="test failure handling",
            requirements=[],
            previous_outputs={"supervisor": "plan"},
        )
    )

    assert result.status is RuntimeStatus.COMPLETED
    assert result.evidence is not None
    assert result.evidence["git_commit_error"] == "nothing to commit"


class FixedRuntime(AgentRuntime):
    def __init__(
        self,
        agent_name: str,
        output: str,
        evidence=None,
    ) -> None:
        self.agent_name = agent_name
        self.output = output
        self.evidence = evidence

    def run(self, request: RuntimeRequest) -> RuntimeResult:
        return RuntimeResult(
            agent_name=self.agent_name,
            status=RuntimeStatus.COMPLETED,
            output=self.output,
            evidence=self.evidence,
        )


class CodexResultRuntime(FixedRuntime):
    execution_mode = "codex"


def test_git_commit_hash_is_saved_as_task_artifact(tmp_path) -> None:
    workspace = tmp_path / "repository"
    initialize_repository(workspace)
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    commit_hash = "a" * 40
    service = TaskService(
        database,
        CrewService(
            database,
            FixedRuntime("supervisor", "plan"),
            CodexResultRuntime(
                "developer",
                "development complete",
                evidence={
                    "git_diff": "+ change",
                    "changed_files": ["feature.py"],
                    "test_results": [],
                    "codex_output": "complete",
                    "git_commit": commit_hash,
                },
            ),
            FixedRuntime("reviewer", "PASS\naccepted"),
        ),
    )
    task = service.create_task(
        TaskCreate(
            project_name="commit artifact",
            workspace_path=str(workspace),
            goal="persist commit",
            requirements=[],
            execution_mode="execute",
        )
    )

    finished = service.run_task(task.task_id)

    assert finished.status is TaskStatus.PASSED
    artifacts = database.list_task_artifacts(task.task_id)
    git_commit = next(
        item for item in artifacts if item.artifact_type == "git_commit"
    )
    assert git_commit.content == commit_hash
    events = [
        item.event_type
        for item in database.list_execution_logs(task.task_id)
    ]
    assert "WORKSPACE_VALIDATED" in events
    assert "CODE_CHANGE_STARTED" in events
    assert "CODE_CHANGE_FINISHED" in events
    assert "GIT_COMMIT_CREATED" in events


def test_commit_failure_is_logged_without_failing_task(tmp_path) -> None:
    workspace = tmp_path / "repository"
    initialize_repository(workspace)
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    service = TaskService(
        database,
        CrewService(
            database,
            FixedRuntime("supervisor", "plan"),
            CodexResultRuntime(
                "developer",
                "development complete",
                evidence={
                    "git_diff": "",
                    "changed_files": [],
                    "test_results": [],
                    "codex_output": "complete",
                    "git_commit_error": "nothing to commit",
                },
            ),
            FixedRuntime("reviewer", "PASS\naccepted"),
        ),
    )
    task = service.create_task(
        TaskCreate(
            project_name="commit failure",
            workspace_path=str(workspace),
            goal="continue after commit failure",
            requirements=[],
            execution_mode="execute",
        )
    )

    finished = service.run_task(task.task_id)

    assert finished.status is TaskStatus.PASSED
    assert all(
        item.artifact_type != "git_commit"
        for item in database.list_task_artifacts(task.task_id)
    )
    errors = [
        item
        for item in database.list_execution_logs(task.task_id)
        if item.event_type == "ERROR"
    ]
    assert errors[-1].message == "Git commit failed: nothing to commit"
