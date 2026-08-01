from types import SimpleNamespace

import pytest

from backend.adapters.claude_code_adapter import (
    ClaudeAgentRequest,
    ClaudeAgentStatus,
    ClaudeCodeAdapter,
    ClaudeReviewRequest,
    ClaudeReviewStatus,
)


def request(workspace_path: str) -> ClaudeReviewRequest:
    return ClaudeReviewRequest(
        task_id="task-001",
        workspace_path=workspace_path,
        goal="实现 Knowledge API",
        requirements=["统一查询入口", "支持型号识别"],
        requirement_spec="结构化需求规格",
        acceptance_criteria="所有required_tests必须通过",
        verification_report="独立复验通过",
        developer_evidence={"changed_files": ["src/api.py"]},
        git_diff="+def search(): pass",
        test_results=[
            {
                "command": ["pytest", "-q"],
                "stdout": "3 passed",
                "stderr": "",
                "exit_code": 0,
            }
        ],
    )


def test_claude_adapter_passes_complete_context_read_only(tmp_path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout="代码符合要求\nFINAL_RESULT: PASS",
            stderr="",
        )

    result = ClaudeCodeAdapter(
        claude_path="/mock/claude",
        process_runner=runner,
    ).review(request(str(workspace)))

    assert result.status is ClaudeReviewStatus.PASS
    assert result.output.startswith("PASS\n")
    assert result.raw_output.startswith("代码符合要求")
    assert result.exit_code == 0
    command, kwargs = calls[0]
    assert command[0] == "/mock/claude"
    assert command[command.index("--permission-mode") + 1] == "plan"
    assert command[command.index("--tools") + 1] == "Read,Grep,Glob"
    assert "Edit,Write,NotebookEdit,Bash" in command
    assert kwargs["cwd"] == workspace
    assert kwargs["shell"] is False
    assert "实现 Knowledge API" in kwargs["input"]
    assert "所有required_tests必须通过" in kwargs["input"]
    assert "结构化需求规格" in kwargs["input"]
    assert "独立复验通过" in kwargs["input"]
    assert "src/api.py" in kwargs["input"]
    assert "+def search(): pass" in kwargs["input"]
    assert "3 passed" in kwargs["input"]


def test_claude_adapter_supports_generic_read_only_roles(tmp_path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout='{"ready": true}',
            stderr="",
        )

    result = ClaudeCodeAdapter(
        claude_path="/mock/claude",
        process_runner=runner,
    ).execute_readonly(
        ClaudeAgentRequest(
            workspace_path=str(workspace),
            prompt="只读规划任务",
        )
    )

    assert result.status is ClaudeAgentStatus.COMPLETED
    assert result.output == '{"ready": true}'
    assert calls[0][1]["input"] == "只读规划任务"
    assert "Edit,Write,NotebookEdit,Bash" in calls[0][0]


def test_claude_adapter_rejects_missing_workspace(tmp_path) -> None:
    result = ClaudeCodeAdapter().review(
        request(str(tmp_path / "missing"))
    )

    assert result.status is ClaudeReviewStatus.FAILED
    assert result.error is not None
    assert result.error.startswith("Workspace does not exist:")


def test_claude_adapter_handles_cli_exception(tmp_path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()

    def runner(*args, **kwargs):
        raise OSError("claude unavailable")

    result = ClaudeCodeAdapter(process_runner=runner).review(
        request(str(workspace))
    )

    assert result.status is ClaudeReviewStatus.FAILED
    assert result.error == "claude unavailable"
    assert result.raw_output == ""


@pytest.mark.parametrize(
    ("raw_output", "expected"),
    [
        (
            "正文讨论 FAIL 风险，但证据充分\nFINAL_RESULT: PASS",
            ClaudeReviewStatus.PASS,
        ),
        (
            "正文也提到 PASS 项目\nFINAL_RESULT: FAIL",
            ClaudeReviewStatus.FAIL,
        ),
        (
            "缺少必要证据\nFINAL_RESULT: BLOCKED",
            ClaudeReviewStatus.BLOCKED,
        ),
    ],
)
def test_claude_adapter_parses_explicit_final_result(
    tmp_path, raw_output, expected
) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    adapter = ClaudeCodeAdapter(
        process_runner=lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=raw_output,
            stderr="",
        )
    )

    result = adapter.review(request(str(workspace)))

    assert result.status is expected
    assert result.output.startswith(f"{expected.value}\n")
