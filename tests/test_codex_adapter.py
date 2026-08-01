import json
from types import SimpleNamespace

from backend.adapters.codex_cli_adapter import (
    PLATFORM_ROOT,
    CodexCLIAdapter,
    CodexExecutionRequest,
    CodexExecutionStatus,
)


def request(workspace_path: str) -> CodexExecutionRequest:
    return CodexExecutionRequest(
        task_id="task-001",
        workspace_path=workspace_path,
        goal="实现 Knowledge API",
        requirements=["统一查询入口", "支持型号识别"],
        acceptance_criteria="接口测试必须通过",
    )


def test_codex_adapter_passes_complete_task_and_captures_result(
    tmp_path,
) -> None:
    workspace = tmp_path / "target"
    workspace.mkdir()
    calls = []

    def process_runner(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout="实现完成",
            stderr="",
        )

    def git_runner(command, **kwargs):
        if "--is-inside-work-tree" in command:
            return SimpleNamespace(returncode=0, stdout="true\n", stderr="")
        if "--show-toplevel" in command:
            return SimpleNamespace(
                returncode=0, stdout=f"{workspace}\n", stderr=""
            )
        return SimpleNamespace(
            returncode=0,
            stdout=" M src/api.py\n?? tests/test_api.py\n",
            stderr="",
        )

    adapter = CodexCLIAdapter(
        codex_path="/mock/codex",
        process_runner=process_runner,
        git_runner=git_runner,
    )
    result = adapter.execute(request(str(workspace)))

    assert result.status is CodexExecutionStatus.COMPLETED
    assert result.output == "实现完成"
    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.error is None
    assert result.changed_files == ["src/api.py", "tests/test_api.py"]
    assert result.commands[0][0:2] == ["/mock/codex", "exec"]
    command, kwargs = calls[0]
    assert command[-1] == "-"
    assert "--ignore-user-config" in command
    assert kwargs["cwd"] == workspace
    assert kwargs["shell"] is False
    assert "task-001" in kwargs["input"]
    assert "实现 Knowledge API" in kwargs["input"]
    assert "统一查询入口" in kwargs["input"]
    assert "接口测试必须通过" in kwargs["input"]


def test_codex_adapter_handles_nonzero_exit_code(tmp_path) -> None:
    workspace = tmp_path / "target"
    workspace.mkdir()

    def git_runner(command, **kwargs):
        if "--is-inside-work-tree" in command:
            return SimpleNamespace(returncode=0, stdout="true\n", stderr="")
        if "--show-toplevel" in command:
            return SimpleNamespace(
                returncode=0, stdout=f"{workspace}\n", stderr=""
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    adapter = CodexCLIAdapter(
        process_runner=lambda *args, **kwargs: SimpleNamespace(
            returncode=7,
            stdout="部分输出",
            stderr="codex failed",
        ),
        git_runner=git_runner,
    )
    result = adapter.execute(request(str(workspace)))

    assert result.status is CodexExecutionStatus.FAILED
    assert result.output == "部分输出"
    assert result.exit_code == 7
    assert result.stderr == "codex failed"
    assert result.error == "codex failed"


def test_codex_adapter_rejects_missing_workspace(tmp_path) -> None:
    called = False

    def process_runner(*args, **kwargs):
        nonlocal called
        called = True

    result = CodexCLIAdapter(process_runner=process_runner).execute(
        request(str(tmp_path / "missing"))
    )

    assert result.status is CodexExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.startswith("Workspace does not exist:")
    assert called is False


def test_codex_adapter_protects_platform_workspace() -> None:
    result = CodexCLIAdapter().execute(request(str(PLATFORM_ROOT)))

    assert result.status is CodexExecutionStatus.FAILED
    assert result.error == "Refusing to modify Auto Dev Platform workspace"


def test_codex_adapter_allows_managed_workspace_directory() -> None:
    managed_workspace = PLATFORM_ROOT / "workspaces" / "task-001"

    assert (
        CodexCLIAdapter._is_protected_platform_path(managed_workspace)
        is False
    )
    assert (
        CodexCLIAdapter._is_protected_platform_path(
            PLATFORM_ROOT / "backend" / "task-001"
        )
        is True
    )


def test_codex_adapter_keeps_only_final_jsonl_message_and_usage(
    tmp_path,
) -> None:
    workspace = tmp_path / "target"
    workspace.mkdir()
    events = [
        {"type": "item.completed", "item": {"type": "command_execution"}},
        {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": "最终交付摘要"},
        },
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 1200, "output_tokens": 80},
        },
    ]

    def git_runner(command, **kwargs):
        if "--is-inside-work-tree" in command:
            return SimpleNamespace(returncode=0, stdout="true\n", stderr="")
        if "--show-toplevel" in command:
            return SimpleNamespace(
                returncode=0, stdout=f"{workspace}\n", stderr=""
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    result = CodexCLIAdapter(
        process_runner=lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="\n".join(json.dumps(event) for event in events),
            stderr="",
        ),
        git_runner=git_runner,
    ).execute(request(str(workspace)))

    assert result.output == "最终交付摘要"
    assert result.usage == {"input_tokens": 1200, "output_tokens": 80}


def test_codex_adapter_bounds_large_diagnostics() -> None:
    diagnostics = "a" * 20_000

    bounded = CodexCLIAdapter._bounded_diagnostics(diagnostics)

    assert len(bounded) < len(diagnostics)
    assert "omitted 4000 diagnostic characters" in bounded
