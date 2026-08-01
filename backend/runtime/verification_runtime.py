from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from backend.adapters.claude_code_adapter import (
    ClaudeAgentRequest,
    ClaudeAgentStatus,
    ClaudeCodeAdapter,
)
from backend.adapters.kimi_api_adapter import (
    KimiAPIAdapter,
    KimiVerificationRequest,
    KimiVerificationStatus,
)
from backend.evidence.test_collector import TestCollector
from backend.runtime.agent_runtime import (
    AgentRuntime,
    RuntimeRequest,
    RuntimeResult,
    RuntimeStatus,
)
from backend.runtime.runtime_utils import extract_required_tests
from backend.runtime.role_context_builder import RoleContextBuilder
from backend.safety.workspace_validator import WorkspaceValidator

ProcessRunner = Callable[..., Any]


class VerificationRuntime(AgentRuntime):
    """独立重跑受控测试并生成只读VerificationReport。"""

    agent_name = "verification_engineer"

    def __init__(
        self,
        *,
        test_collector: TestCollector | None = None,
        git_runner: ProcessRunner = subprocess.run,
        workspace_validator: WorkspaceValidator | None = None,
        verification_mode: str | None = None,
        claude_adapter: ClaudeCodeAdapter | None = None,
        kimi_adapter: KimiAPIAdapter | None = None,
    ) -> None:
        self._test_collector = test_collector or TestCollector()
        self._git_runner = git_runner
        self._workspace_validator = (
            workspace_validator or WorkspaceValidator(git_runner)
        )
        self.verification_mode = (
            verification_mode or self._mode_from_environment()
        )
        if self.verification_mode not in {
            "deterministic",
            "claude",
            "kimi",
        }:
            raise ValueError(
                "verification_mode must be deterministic, claude, or kimi"
            )
        self._claude_adapter = claude_adapter
        self._kimi_adapter = kimi_adapter

    def run(self, request: RuntimeRequest) -> RuntimeResult:
        workspace = Path(request.workspace_path).expanduser().resolve()
        validation = self._workspace_validator.validate(workspace)
        if not validation.valid:
            return RuntimeResult(
                agent_name=self.agent_name,
                status=RuntimeStatus.BLOCKED,
                output="",
                error=validation.error,
            )

        developer_output = request.previous_outputs.get("developer", "")
        try:
            parsed_developer = json.loads(developer_output)
        except (json.JSONDecodeError, TypeError):
            parsed_developer = {}
        developer_evidence = (
            parsed_developer.get("evidence", {})
            if isinstance(parsed_developer, dict)
            else {}
        )
        if not isinstance(developer_evidence, dict):
            developer_evidence = {}

        supervisor_output = request.previous_outputs.get("supervisor", "")
        required_tests = extract_required_tests(supervisor_output)
        before_status = self._git_status(workspace)
        test_results = self._test_collector.collect(
            workspace, required_tests
        )
        after_status = self._git_status(workspace)

        issues: list[str] = []
        if not developer_evidence:
            issues.append("Developer Evidence is missing or invalid")
        for result in test_results:
            if result.error:
                issues.append(
                    f"Test command failed to execute: {' '.join(result.command)}"
                )
            elif result.exit_code != 0:
                issues.append(
                    f"Test command returned {result.exit_code}: "
                    f"{' '.join(result.command)}"
                )
        if after_status != before_status:
            issues.append("Verification changed the workspace")

        report: dict[str, Any] = {
            "task_id": request.task_id,
            "verification_result": "FAIL" if issues else "PASS",
            "required_tests": required_tests,
            "test_results": [
                item.model_dump(mode="json") for item in test_results
            ],
            "developer_evidence_present": bool(developer_evidence),
            "git_commit": developer_evidence.get("git_commit"),
            "changed_files": developer_evidence.get("changed_files", []),
            "workspace_status_before": before_status,
            "workspace_status_after": after_status,
            "issues": issues,
        }
        if self.verification_mode in {"claude", "kimi"}:
            model_result = (
                self._run_claude(
                    request=request,
                    workspace=workspace,
                    report=report,
                )
                if self.verification_mode == "claude"
                else self._run_kimi(request=request, report=report)
            )
            if model_result.status is not RuntimeStatus.COMPLETED:
                return model_result
            try:
                model_report = self._parse_json_output(model_result.output)
            except (json.JSONDecodeError, TypeError):
                return RuntimeResult(
                    agent_name=self.agent_name,
                    status=RuntimeStatus.FAILED,
                    output="",
                    error=(
                        f"{self.verification_mode.title()} verification "
                        "returned invalid JSON"
                    ),
                )
            model_verdict = str(
                model_report.get("verification_result", "FAIL")
            ).upper()
            model_blockers = model_report.get("blocking_issues", [])
            model_warnings = model_report.get("warnings", [])
            legacy_issues = model_report.get("issues", [])
            if not isinstance(model_blockers, list):
                model_blockers = [
                    "Verification blocking_issues field is invalid"
                ]
            if not isinstance(model_warnings, list):
                model_warnings = []
            if isinstance(legacy_issues, list):
                if model_verdict == "PASS":
                    model_warnings.extend(legacy_issues)
                else:
                    model_blockers.extend(legacy_issues)
            report["verification_provider"] = self.verification_mode
            if model_result.evidence:
                report["verification_model"] = model_result.evidence.get(
                    "model", ""
                )
                report["model_usage"] = model_result.evidence.get(
                    "usage", {}
                )
            report["model_assessment"] = str(
                model_report.get("assessment", "")
            )
            report["issues"] = issues + [
                str(item) for item in model_blockers if str(item).strip()
            ]
            report["warnings"] = [
                str(item) for item in model_warnings if str(item).strip()
            ]
            report["verification_result"] = (
                "PASS"
                if model_verdict == "PASS" and not report["issues"]
                else "FAIL"
            )
        else:
            report["verification_provider"] = "deterministic"
        output = json.dumps(report, ensure_ascii=False, indent=2)
        return RuntimeResult(
            agent_name=self.agent_name,
            status=RuntimeStatus.COMPLETED,
            output=output,
            evidence={"verification_report": report},
        )

    def _run_claude(
        self,
        *,
        request: RuntimeRequest,
        workspace: Path,
        report: dict[str, Any],
    ) -> RuntimeResult:
        prompt = (
            "你是独立 Verification Engineer。只能读取工作区，不得修改、"
            "创建、删除或提交文件。程序已经独立运行批准的测试，请检查代码、"
            "Developer Evidence 与确定性测试结果。\n"
            "不得把失败测试判为通过。只输出一个 JSON 对象，不要使用 Markdown"
            " 代码块，字段必须为 verification_result（PASS或FAIL）、"
            "blocking_issues（会导致验收失败的字符串数组）、warnings"
            "（不影响通过的建议数组）、assessment（字符串）。不得因为缓存、"
            "格式偏好等非阻塞建议把本应通过的结果标为FAIL。\n\n"
            f"{json.dumps({'task': request.model_dump(mode='json'), 'deterministic_report': report}, ensure_ascii=False, indent=2)}"
        )
        adapter = self._claude_adapter or ClaudeCodeAdapter(
            claude_path=os.getenv("CLAUDE_PATH", "claude")
        )
        result = adapter.execute_readonly(
            ClaudeAgentRequest(
                workspace_path=str(workspace),
                prompt=prompt,
            )
        )
        if result.status is ClaudeAgentStatus.FAILED:
            return RuntimeResult(
                agent_name=self.agent_name,
                status=RuntimeStatus.FAILED,
                output="",
                error=result.error or "Claude verification failed",
            )
        return RuntimeResult(
            agent_name=self.agent_name,
            status=RuntimeStatus.COMPLETED,
            output=result.output,
        )

    def _run_kimi(
        self,
        *,
        request: RuntimeRequest,
        report: dict[str, Any],
    ) -> RuntimeResult:
        prompt = (
            "请根据任务上下文、Developer Evidence、Git Diff与程序独立运行的"
            "测试结果生成VerificationReport。你不能修改代码，不能执行命令，"
            "不得把失败测试改判为通过。\n"
            "只输出一个JSON对象，不要使用Markdown代码块。字段必须为："
            "verification_result（PASS或FAIL）、blocking_issues（会导致失败的"
            "字符串数组）、warnings（不影响通过的建议数组）、assessment"
            "（字符串，最多500个汉字）。缓存和格式偏好只能放入warnings。\n\n"
            f"{RoleContextBuilder.compact_json(RoleContextBuilder.verification_context(request, report))}"
        )
        adapter = self._kimi_adapter or KimiAPIAdapter(
            api_key=os.getenv("KIMI_API_KEY", ""),
            base_url=os.getenv(
                "KIMI_BASE_URL", "https://api.moonshot.cn/v1"
            ),
            model=os.getenv("KIMI_MODEL", "kimi-k3"),
            reasoning_effort=os.getenv(
                "KIMI_REASONING_EFFORT", "high"
            ),
            max_tokens=int(os.getenv("KIMI_MAX_TOKENS", "4096")),
        )
        result = adapter.verify(KimiVerificationRequest(prompt=prompt))
        if result.status is KimiVerificationStatus.FAILED:
            return RuntimeResult(
                agent_name=self.agent_name,
                status=RuntimeStatus.FAILED,
                output="",
                error=result.error or "Kimi verification failed",
            )
        return RuntimeResult(
            agent_name=self.agent_name,
            status=RuntimeStatus.COMPLETED,
            output=result.output,
            evidence={
                "model": result.model,
                "usage": result.usage,
            },
        )

    def _git_status(self, workspace: Path) -> str:
        try:
            completed = self._git_runner(
                ["git", "-C", str(workspace), "status", "--porcelain"],
                text=True,
                capture_output=True,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError):
            return "[git status unavailable]"
        if completed.returncode != 0:
            return "[git status unavailable]"
        return (completed.stdout or "").strip()

    @staticmethod
    def _mode_from_environment() -> str:
        configured = os.getenv(
            "VERIFICATION_PROVIDER", ""
        ).strip().lower()
        if configured:
            return configured
        enabled = os.getenv("CLAUDE_ENABLED", "false").strip().lower()
        return (
            "claude"
            if enabled in {"1", "true", "yes", "on"}
            else "deterministic"
        )

    @staticmethod
    def _parse_json_output(output: str) -> dict[str, Any]:
        candidate = output.strip()
        if candidate.startswith("```") and candidate.endswith("```"):
            lines = candidate.splitlines()
            candidate = "\n".join(lines[1:-1]).strip()
        parsed = json.loads(candidate)
        if not isinstance(parsed, dict):
            raise TypeError("verification output must be a JSON object")
        return parsed
