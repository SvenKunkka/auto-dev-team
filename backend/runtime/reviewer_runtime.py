from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

from auto_dev_team.crew import AutoDevTeam, normalize_review_text
from backend.adapters.claude_code_adapter import (
    ClaudeCodeAdapter,
    ClaudeReviewRequest,
    ClaudeReviewStatus,
)
from backend.runtime.agent_runtime import (
    AgentRuntime,
    RuntimeRequest,
    RuntimeResult,
    RuntimeStatus,
)
from backend.runtime.role_context_builder import RoleContextBuilder


class ReviewerRuntime(AgentRuntime):
    """Reviewer入口；默认使用DeepSeek，保留Claude兼容模式。"""

    agent_name = "reviewer"

    def __init__(
        self,
        agent_factory: Callable[[], Any] | None = None,
        *,
        review_mode: str | None = None,
        claude_adapter: ClaudeCodeAdapter | None = None,
    ) -> None:
        self._agent_factory = agent_factory or (
            lambda: AutoDevTeam().acceptance_reviewer()
        )
        self.review_mode = review_mode or self._mode_from_environment()
        if self.review_mode == "mock":
            self.review_mode = "deepseek"
        if self.review_mode not in {"deepseek", "claude"}:
            raise ValueError(
                "review_mode must be either 'deepseek' or 'claude'"
            )
        self._claude_adapter = claude_adapter

    def run(self, request: RuntimeRequest) -> RuntimeResult:
        if self.review_mode == "claude":
            return self._run_claude(request)
        return self._run_deepseek(request)

    def _run_deepseek(self, request: RuntimeRequest) -> RuntimeResult:
        context = RoleContextBuilder.review_context(request)
        prompt = (
            "请作为独立 Acceptance Reviewer 验收以下任务结果。\n"
            "你收到的是完整原始需求、验收标准、最终Git Diff、确定性测试结果"
            "和VerificationReport；Codex过程性文字已省略，但原始交付证据未省略。\n"
            "正式结论必须放在第一行，或使用 FINAL_RESULT: PASS、"
            "FINAL_RESULT: FAIL、FINAL_RESULT: BLOCKED；"
            "不得修改 Developer 的结果，不得推翻失败测试。\n\n"
            f"{RoleContextBuilder.compact_json(context)}"
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
            verdict, output = normalize_review_text(output)
            return RuntimeResult(
                agent_name=self.agent_name,
                status=(
                    RuntimeStatus.BLOCKED
                    if verdict == "BLOCKED"
                    else RuntimeStatus.COMPLETED
                ),
                output=output,
            )
        except Exception as exc:
            return RuntimeResult(
                agent_name=self.agent_name,
                status=RuntimeStatus.FAILED,
                output="",
                error=str(exc),
            )

    def _run_claude(self, request: RuntimeRequest) -> RuntimeResult:
        developer_output = request.previous_outputs.get("developer", "")
        developer_evidence: dict[str, Any] | str = developer_output
        git_diff = ""
        test_results: list[dict[str, Any]] = []
        try:
            parsed = json.loads(developer_output)
            if isinstance(parsed, dict):
                evidence = parsed.get("evidence", {})
                developer_evidence = evidence
                if isinstance(evidence, dict):
                    git_diff = str(evidence.get("git_diff", ""))
                    raw_tests = evidence.get("test_results", [])
                    if isinstance(raw_tests, list):
                        test_results = [
                            item for item in raw_tests if isinstance(item, dict)
                        ]
        except (json.JSONDecodeError, TypeError):
            pass

        adapter = self._claude_adapter or ClaudeCodeAdapter(
            claude_path=os.getenv("CLAUDE_PATH", "claude")
        )
        review = adapter.review(
            ClaudeReviewRequest(
                task_id=request.task_id,
                workspace_path=request.workspace_path,
                goal=request.goal,
                requirements=request.requirements,
                requirement_spec=request.previous_outputs.get(
                    "requirement_analyst", ""
                ),
                acceptance_criteria=request.previous_outputs.get(
                    "supervisor", ""
                ),
                verification_report=request.previous_outputs.get(
                    "verification_engineer", ""
                ),
                developer_evidence=developer_evidence,
                git_diff=git_diff,
                test_results=test_results,
            )
        )
        if review.status is ClaudeReviewStatus.FAILED:
            return RuntimeResult(
                agent_name=self.agent_name,
                status=RuntimeStatus.FAILED,
                output=review.output,
                error=review.error,
            )
        return RuntimeResult(
            agent_name=self.agent_name,
            status=(
                RuntimeStatus.BLOCKED
                if review.status is ClaudeReviewStatus.BLOCKED
                else RuntimeStatus.COMPLETED
            ),
            output=review.output,
            error=review.error,
        )

    @staticmethod
    def _mode_from_environment() -> str:
        return os.getenv("REVIEWER_MODE", "deepseek").strip().lower()
