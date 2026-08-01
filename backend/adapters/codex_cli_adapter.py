from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from backend.safety.workspace_validator import WorkspaceValidator

PLATFORM_ROOT = Path(__file__).resolve().parents[2]
PROTECTED_PLATFORM_DIRECTORIES = (
    PLATFORM_ROOT / "backend",
    PLATFORM_ROOT / "frontend",
    PLATFORM_ROOT / "src",
    PLATFORM_ROOT / "config",
    PLATFORM_ROOT / "data",
    PLATFORM_ROOT / "logs",
    PLATFORM_ROOT / "deploy",
    PLATFORM_ROOT / "scripts",
)


class CodexExecutionStatus(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CodexExecutionRequest(BaseModel):
    task_id: str
    workspace_path: str
    goal: str
    requirements: list[str] = Field(default_factory=list)
    acceptance_criteria: str


class CodexExecutionResult(BaseModel):
    status: CodexExecutionStatus
    output: str
    changed_files: list[str] = Field(default_factory=list)
    commands: list[list[str]] = Field(default_factory=list)
    exit_code: int | None = None
    stderr: str = ""
    usage: dict[str, int] = Field(default_factory=dict)
    error: str | None = None


ProcessRunner = Callable[..., Any]


class CodexCLIAdapter:
    """通过受限的非交互命令调用 Codex CLI。"""

    def __init__(
        self,
        *,
        codex_path: str = "codex",
        process_runner: ProcessRunner = subprocess.run,
        git_runner: ProcessRunner = subprocess.run,
        allow_platform_workspace: bool = False,
        workspace_validator: WorkspaceValidator | None = None,
    ) -> None:
        self.codex_path = codex_path
        self._process_runner = process_runner
        self._git_runner = git_runner
        self.allow_platform_workspace = allow_platform_workspace
        self._workspace_validator = (
            workspace_validator or WorkspaceValidator(git_runner)
        )

    def execute(self, request: CodexExecutionRequest) -> CodexExecutionResult:
        workspace = Path(request.workspace_path).expanduser().resolve()
        validation_error = self._validate_workspace(workspace)
        if validation_error:
            return CodexExecutionResult(
                status=CodexExecutionStatus.FAILED,
                output="",
                error=validation_error,
            )

        command = [
            self.codex_path,
            "exec",
            "--ignore-user-config",
            "--sandbox",
            "workspace-write",
            "--cd",
            str(workspace),
            "--ephemeral",
            "--color",
            "never",
            "--json",
            "-",
        ]
        prompt = self._build_prompt(request)

        try:
            completed = self._process_runner(
                command,
                input=prompt,
                text=True,
                capture_output=True,
                check=False,
                cwd=workspace,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return CodexExecutionResult(
                status=CodexExecutionStatus.FAILED,
                output="",
                commands=[command],
                error=str(exc),
            )

        output, usage = self._parse_jsonl_output(completed.stdout or "")
        error_output = self._bounded_diagnostics(completed.stderr or "")
        changed_files = self._read_changed_files(workspace)
        if completed.returncode != 0:
            return CodexExecutionResult(
                status=CodexExecutionStatus.FAILED,
                output=output,
                changed_files=changed_files,
                commands=[command],
                exit_code=completed.returncode,
                stderr=error_output,
                usage=usage,
                error=error_output or f"Codex exited with code {completed.returncode}",
            )

        return CodexExecutionResult(
            status=CodexExecutionStatus.COMPLETED,
            output=output,
            changed_files=changed_files,
            commands=[command],
            exit_code=completed.returncode,
            stderr=error_output,
            usage=usage,
            error=None,
        )

    def _validate_workspace(self, workspace: Path) -> str | None:
        if not workspace.exists():
            return f"Workspace does not exist: {workspace}"
        if not workspace.is_dir():
            return f"Workspace is not a directory: {workspace}"
        if (
            not self.allow_platform_workspace
            and self._is_protected_platform_path(workspace)
        ):
            return "Refusing to modify Auto Dev Platform workspace"
        validation = self._workspace_validator.validate(workspace)
        return validation.error if not validation.valid else None

    @staticmethod
    def _paths_overlap(first: Path, second: Path) -> bool:
        return (
            first == second
            or first in second.parents
            or second in first.parents
        )

    @staticmethod
    def _is_protected_platform_path(workspace: Path) -> bool:
        if workspace == PLATFORM_ROOT or workspace in PLATFORM_ROOT.parents:
            return True
        return any(
            workspace == protected or protected in workspace.parents
            for protected in PROTECTED_PLATFORM_DIRECTORIES
        )

    @staticmethod
    def _build_prompt(request: CodexExecutionRequest) -> str:
        requirements = "\n".join(
            f"- {requirement}" for requirement in request.requirements
        ) or "- 无额外需求"
        return (
            "你是 Auto Dev Platform 的 Developer。请在指定工作区内完成真实代码修改。\n"
            "不得访问或修改工作区之外的文件，不得自行改变验收标准。\n\n"
            f"任务ID：{request.task_id}\n"
            f"工作区：{request.workspace_path}\n"
            f"目标：{request.goal}\n"
            f"需求：\n{requirements}\n\n"
            f"验收标准与Supervisor任务计划：\n{request.acceptance_criteria}\n\n"
            "执行效率要求：先用 rg 和精确范围读取定位相关代码；禁止无目的地输出整份"
            "大文件、完整仓库清单或重复读取相同内容。调试时优先运行与改动直接相关的"
            "最小测试集；Supervisor 指定的 required_tests 会由后续 Evidence 与验证"
            "工程师独立完整执行，不要为了展示过程重复运行。不得降低实现质量或跳过"
            "必要检查。\n"
            "完成修改后只需在最终答复中简洁说明变更文件、实现结果和已运行测试；"
            "不要复述长日志、diff 或完整任务上下文。"
        )

    @staticmethod
    def _parse_jsonl_output(raw_output: str) -> tuple[str, dict[str, int]]:
        """Return only the final agent message and aggregate usage.

        Older or mocked Codex versions may still emit plain text, so malformed
        JSONL safely falls back to the original stdout.
        """
        final_messages: list[str] = []
        usage: dict[str, int] = {}
        parsed_event = False
        for line in raw_output.splitlines():
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(event, dict):
                continue
            parsed_event = True
            event_type = event.get("type")
            item = event.get("item")
            if (
                event_type == "item.completed"
                and isinstance(item, dict)
                and item.get("type") == "agent_message"
            ):
                text = str(item.get("text", "")).strip()
                if text:
                    final_messages.append(text)
            if event_type == "turn.completed":
                raw_usage = event.get("usage")
                if isinstance(raw_usage, dict):
                    usage = {
                        str(key): int(value)
                        for key, value in raw_usage.items()
                        if isinstance(value, int)
                    }
        if final_messages:
            return final_messages[-1], usage
        if parsed_event:
            return "", usage
        return raw_output.strip(), usage

    @staticmethod
    def _bounded_diagnostics(raw: str, limit: int = 16_000) -> str:
        """Keep actionable diagnostics without persisting huge CLI transcripts."""
        text = raw.strip()
        if len(text) <= limit:
            return text
        half = limit // 2
        omitted = len(text) - (half * 2)
        return (
            text[:half]
            + f"\n\n...[omitted {omitted} diagnostic characters]...\n\n"
            + text[-half:]
        )

    def _read_changed_files(self, workspace: Path) -> list[str]:
        try:
            completed = self._git_runner(
                ["git", "-C", str(workspace), "status", "--porcelain"],
                text=True,
                capture_output=True,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError):
            return []
        if completed.returncode != 0:
            return []

        changed_files: list[str] = []
        for line in (completed.stdout or "").splitlines():
            path = line[3:].strip()
            if " -> " in path:
                path = path.rsplit(" -> ", 1)[1]
            if path:
                changed_files.append(path)
        return changed_files
