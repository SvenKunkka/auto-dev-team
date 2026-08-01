from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

from auto_dev_team.crew import AutoDevTeam
from backend.adapters.codex_cli_adapter import (
    CodexCLIAdapter,
    CodexExecutionRequest,
    CodexExecutionStatus,
)
from backend.evidence.evidence_collector import EvidenceCollector
from backend.evidence.git_committer import GitCommitter
from backend.evidence.workspace_cleaner import WorkspaceCleaner
from backend.runtime.agent_runtime import (
    AgentRuntime,
    RuntimeRequest,
    RuntimeResult,
    RuntimeStatus,
)
from backend.runtime.runtime_utils import extract_required_tests
from backend.safety.workspace_validator import WorkspaceValidator


class DeveloperRuntime(AgentRuntime):
    """Developer执行入口；支持CrewAI mock模式和Codex CLI模式。"""

    agent_name = "developer"

    def __init__(
        self,
        agent_factory: Callable[[], Any] | None = None,
        *,
        execution_mode: str | None = None,
        codex_adapter: CodexCLIAdapter | None = None,
        evidence_collector: EvidenceCollector | None = None,
        workspace_validator: WorkspaceValidator | None = None,
        git_committer: GitCommitter | None = None,
        workspace_cleaner: WorkspaceCleaner | None = None,
    ) -> None:
        self._agent_factory = agent_factory or (lambda: AutoDevTeam().developer())
        self.execution_mode = execution_mode or self._mode_from_environment()
        if self.execution_mode not in {"mock", "codex"}:
            raise ValueError(
                "execution_mode must be either 'mock' or 'codex'"
            )
        self._codex_adapter = codex_adapter
        self._evidence_collector = evidence_collector
        self._workspace_validator = workspace_validator or WorkspaceValidator()
        self._git_committer = git_committer or GitCommitter()
        self._workspace_cleaner = workspace_cleaner or WorkspaceCleaner()

    def run(self, request: RuntimeRequest) -> RuntimeResult:
        if self.execution_mode == "codex":
            return self._run_codex(request)
        return self._run_mock(request)

    def _run_mock(self, request: RuntimeRequest) -> RuntimeResult:
        supervisor_output = request.previous_outputs.get("supervisor", "")
        prompt = (
            "请作为 Developer 执行 Supervisor 交付的当前阶段任务。\n"
            f"任务ID：{request.task_id}\n"
            f"项目名称：{request.project_name}\n"
            f"工作区：{request.workspace_path}\n"
            f"目标：{request.goal}\n"
            f"需求：{request.requirements}\n\n"
            f"Supervisor输出：\n{supervisor_output}\n\n"
            "当前 Phase 1 尚未接入 Codex CLI，请按照现有 CrewAI Developer "
            "能力输出开发结果，不得自行验收。"
        )
        try:
            result = self._agent_factory().kickoff(prompt)
            raw = result.raw
            output = "" if raw is None else str(raw).strip()
            if not output:
                return RuntimeResult(
                    agent_name=self.agent_name,
                    status=RuntimeStatus.FAILED,
                    output="",
                    error="Agent returned empty output",
                )
            return RuntimeResult(
                agent_name=self.agent_name,
                status=RuntimeStatus.COMPLETED,
                output=output,
            )
        except Exception as exc:
            return RuntimeResult(
                agent_name=self.agent_name,
                status=RuntimeStatus.FAILED,
                output="",
                error=str(exc),
            )

    def _run_codex(self, request: RuntimeRequest) -> RuntimeResult:
        validation = self._workspace_validator.validate(
            request.workspace_path
        )
        validation_evidence = validation.model_dump(mode="json")
        if not validation.valid:
            return RuntimeResult(
                agent_name=self.agent_name,
                status=RuntimeStatus.BLOCKED,
                output="",
                error=validation.error,
                evidence={
                    "workspace_validation": validation_evidence,
                },
            )

        adapter = self._codex_adapter or CodexCLIAdapter(
            codex_path=os.getenv("CODEX_PATH", "codex")
        )
        acceptance_context = request.previous_outputs.get("supervisor", "")
        requirement_spec = request.previous_outputs.get(
            "requirement_analyst", ""
        )
        if requirement_spec:
            acceptance_context += (
                "\n\nRequirementSpec:\n" + requirement_spec
            )
        execution = adapter.execute(
            CodexExecutionRequest(
                task_id=request.task_id,
                workspace_path=request.workspace_path,
                goal=request.goal,
                requirements=request.requirements,
                acceptance_criteria=acceptance_context,
            )
        )
        self._workspace_cleaner.remove_transient_artifacts(
            request.workspace_path
        )
        evidence_collector = self._evidence_collector or EvidenceCollector()
        evidence = evidence_collector.collect(
            workspace_path=request.workspace_path,
            required_tests=self._required_tests(
                request.previous_outputs.get("supervisor", "")
            ),
            codex_output=execution.output,
            codex_commands=execution.commands,
        )
        evidence_data = evidence.model_dump(mode="json")
        evidence_data["workspace_validation"] = validation_evidence
        if execution.usage:
            evidence_data["codex_usage"] = execution.usage
        if (
            execution.status is CodexExecutionStatus.COMPLETED
            and execution.output.strip()
        ):
            commit = self._git_committer.commit(
                workspace_path=request.workspace_path,
                task_id=request.task_id,
            )
            if commit.created and commit.commit_hash:
                evidence_data["git_commit"] = commit.commit_hash
            elif commit.error:
                evidence_data["git_commit_error"] = commit.error

        serialized = json.dumps(
            {
                "execution": execution.model_dump(mode="json"),
                "evidence": evidence_data,
            },
            ensure_ascii=False,
            indent=2,
        )
        if (
            execution.status is CodexExecutionStatus.COMPLETED
            and not execution.output.strip()
        ):
            return RuntimeResult(
                agent_name=self.agent_name,
                status=RuntimeStatus.FAILED,
                output=serialized,
                error="Agent returned empty output",
                evidence=evidence_data,
            )
        return RuntimeResult(
            agent_name=self.agent_name,
            status=(
                RuntimeStatus.COMPLETED
                if execution.status is CodexExecutionStatus.COMPLETED
                else RuntimeStatus.FAILED
            ),
            output=serialized,
            error=execution.error,
            evidence=evidence_data,
        )

    @staticmethod
    def _mode_from_environment() -> str:
        enabled = os.getenv("CODEX_ENABLED", "false").strip().lower()
        return "codex" if enabled in {"1", "true", "yes", "on"} else "mock"

    @staticmethod
    def _required_tests(supervisor_output: str) -> list[str]:
        return extract_required_tests(supervisor_output)
