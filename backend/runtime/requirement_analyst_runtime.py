from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from auto_dev_team.crew import AutoDevTeam
from backend.runtime.agent_runtime import (
    AgentRuntime,
    RuntimeRequest,
    RuntimeResult,
    RuntimeStatus,
)


class RequirementAnalystRuntime(AgentRuntime):
    """把原始目标和需求文档转换为不可编码的结构化需求规格。"""

    agent_name = "requirement_analyst"

    def __init__(self, agent_factory: Callable[[], Any] | None = None) -> None:
        self._agent_factory = agent_factory or (
            lambda: AutoDevTeam().requirement_analyst()
        )

    def run(self, request: RuntimeRequest) -> RuntimeResult:
        prompt = (
            "请作为 Requirement Analyst 分析以下开发目标和需求材料。\n"
            f"任务ID：{request.task_id}\n"
            f"项目名称：{request.project_name}\n"
            f"目标：{request.goal}\n"
            f"需求材料：{request.requirements}\n\n"
            "只能澄清和结构化需求，不得制定代码实现方案，不得修改文件。\n"
            "必须只输出一个 JSON 对象，不要使用 Markdown 代码块。字段为："
            "task_id、problem_statement、clarified_goal、"
            "functional_requirements、non_functional_requirements、"
            "constraints、ambiguities、assumptions、acceptance_inputs、"
            "ready_for_planning。不得发明需求；存在阻止安全规划的歧义时，"
            "ready_for_planning 必须为 false。"
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
            try:
                parsed = json.loads(output)
            except (json.JSONDecodeError, TypeError):
                return RuntimeResult(
                    agent_name=self.agent_name,
                    status=RuntimeStatus.FAILED,
                    output=output,
                    error="Requirement Analyst returned invalid JSON",
                )
            if not isinstance(parsed, dict):
                return RuntimeResult(
                    agent_name=self.agent_name,
                    status=RuntimeStatus.FAILED,
                    output=output,
                    error="Requirement Analyst output must be a JSON object",
                )
            if parsed.get("ready_for_planning") is not True:
                return RuntimeResult(
                    agent_name=self.agent_name,
                    status=RuntimeStatus.REQUIREMENTS_REVISION,
                    output=output,
                    error="Requirements must return to requirement revision",
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
