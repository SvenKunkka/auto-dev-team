from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from auto_dev_team.crew import normalize_review_text


class ClaudeReviewStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class ClaudeAgentStatus(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ClaudeAgentRequest(BaseModel):
    workspace_path: str
    prompt: str


class ClaudeAgentResult(BaseModel):
    status: ClaudeAgentStatus
    output: str
    error: str | None = None
    raw_output: str
    exit_code: int | None = None


class ClaudeReviewRequest(BaseModel):
    task_id: str
    workspace_path: str
    goal: str
    requirements: list[str] = Field(default_factory=list)
    requirement_spec: str = ""
    acceptance_criteria: str
    verification_report: str = ""
    developer_evidence: dict[str, Any] | str
    git_diff: str = ""
    test_results: list[dict[str, Any]] = Field(default_factory=list)


class ClaudeReviewResult(BaseModel):
    status: ClaudeReviewStatus
    output: str
    error: str | None = None
    raw_output: str
    exit_code: int | None = None


ProcessRunner = Callable[..., Any]


class ClaudeCodeAdapter:
    """以只读工具集非交互调用 Claude Code。"""

    def __init__(
        self,
        *,
        claude_path: str = "claude",
        process_runner: ProcessRunner = subprocess.run,
    ) -> None:
        self.claude_path = claude_path
        self._process_runner = process_runner

    def execute_readonly(
        self, request: ClaudeAgentRequest
    ) -> ClaudeAgentResult:
        workspace = Path(request.workspace_path).expanduser().resolve()
        if not workspace.exists():
            return self._agent_failure(
                f"Workspace does not exist: {workspace}"
            )
        if not workspace.is_dir():
            return self._agent_failure(
                f"Workspace is not a directory: {workspace}"
            )

        command = [
            self.claude_path,
            "--print",
            "--permission-mode",
            "plan",
            "--tools",
            "Read,Grep,Glob",
            "--disallowedTools",
            "Edit,Write,NotebookEdit,Bash",
            "--no-session-persistence",
            "--safe-mode",
            "--no-chrome",
            "--disable-slash-commands",
            "--output-format",
            "text",
        ]
        try:
            completed = self._process_runner(
                command,
                input=request.prompt,
                text=True,
                capture_output=True,
                check=False,
                cwd=workspace,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return self._agent_failure(str(exc))

        raw_output = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        if completed.returncode != 0:
            return self._agent_failure(
                stderr or f"Claude exited with code {completed.returncode}",
                raw_output=raw_output,
                exit_code=completed.returncode,
            )
        if not raw_output:
            return self._agent_failure(
                "Agent returned empty output",
                exit_code=completed.returncode,
            )
        return ClaudeAgentResult(
            status=ClaudeAgentStatus.COMPLETED,
            output=raw_output,
            raw_output=raw_output,
            exit_code=completed.returncode,
        )

    def review(self, request: ClaudeReviewRequest) -> ClaudeReviewResult:
        execution = self.execute_readonly(
            ClaudeAgentRequest(
                workspace_path=request.workspace_path,
                prompt=self._build_prompt(request),
            )
        )
        if execution.status is ClaudeAgentStatus.FAILED:
            return self._failure(
                execution.error or "Claude execution failed",
                raw_output=execution.raw_output,
                exit_code=execution.exit_code,
            )

        verdict, normalized = normalize_review_text(execution.output)
        return ClaudeReviewResult(
            status=ClaudeReviewStatus(verdict),
            output=normalized,
            raw_output=execution.raw_output,
            exit_code=execution.exit_code,
            error=None,
        )

    @staticmethod
    def _build_prompt(request: ClaudeReviewRequest) -> str:
        context = {
            "task_id": request.task_id,
            "workspace_path": request.workspace_path,
            "goal": request.goal,
            "requirements": request.requirements,
            "requirement_spec": request.requirement_spec,
            "acceptance_criteria": request.acceptance_criteria,
            "developer_evidence": request.developer_evidence,
            "git_diff": request.git_diff,
            "test_results": request.test_results,
            "verification_report": request.verification_report,
        }
        return (
            "你是独立代码验收负责人。只能读取工作区，不得修改、创建、删除或"
            "提交任何文件。请根据任务、代码、Git diff和测试证据进行验收。\n"
            "正式结论必须使用 FINAL_RESULT: PASS、FINAL_RESULT: FAIL 或"
            " FINAL_RESULT: BLOCKED。正文中的状态词不构成结论。\n\n"
            f"{json.dumps(context, ensure_ascii=False, indent=2)}"
        )

    @staticmethod
    def _failure(
        error: str,
        *,
        raw_output: str = "",
        exit_code: int | None = None,
    ) -> ClaudeReviewResult:
        return ClaudeReviewResult(
            status=ClaudeReviewStatus.FAILED,
            output="",
            error=error,
            raw_output=raw_output,
            exit_code=exit_code,
        )

    @staticmethod
    def _agent_failure(
        error: str,
        *,
        raw_output: str = "",
        exit_code: int | None = None,
    ) -> ClaudeAgentResult:
        return ClaudeAgentResult(
            status=ClaudeAgentStatus.FAILED,
            output="",
            error=error,
            raw_output=raw_output,
            exit_code=exit_code,
        )
