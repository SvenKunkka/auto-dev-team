from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from auto_dev_team.crew import AutoDevTeam
from backend.adapters.claude_code_adapter import (
    ClaudeAgentRequest,
    ClaudeAgentStatus,
    ClaudeCodeAdapter,
)
from backend.runtime.agent_runtime import (
    AgentRuntime,
    RuntimeRequest,
    RuntimeResult,
    RuntimeStatus,
)


class DecisionAction(StrEnum):
    COMPLETE = "COMPLETE"
    REWORK = "REWORK"
    BLOCKED = "BLOCKED"


class SupervisorDecisionRequest(BaseModel):
    task: dict[str, Any]
    review_result: str
    developer_evidence: dict[str, Any] = Field(default_factory=dict)
    iteration: int


class DecisionResult(BaseModel):
    action: DecisionAction
    developer_task: str | None = None
    output: str
    error: str | None = None


class SupervisorRuntime(AgentRuntime):
    agent_name = "supervisor"

    def __init__(
        self,
        agent_factory: Callable[[], Any] | None = None,
        *,
        plan_mode: str | None = None,
        claude_adapter: ClaudeCodeAdapter | None = None,
    ) -> None:
        self._agent_factory = agent_factory or (lambda: AutoDevTeam().supervisor())
        self.plan_mode = plan_mode or (
            "mock" if agent_factory is not None else self._mode_from_environment()
        )
        if self.plan_mode not in {"mock", "claude"}:
            raise ValueError("plan_mode must be either 'mock' or 'claude'")
        self._claude_adapter = claude_adapter

    def run(self, request: RuntimeRequest) -> RuntimeResult:
        return self.plan(request)

    def plan(self, request: RuntimeRequest) -> RuntimeResult:
        requirement_spec = request.previous_outputs.get(
            "requirement_analyst", ""
        )
        workflow_outputs = {
            role_id: output
            for role_id, output in request.previous_outputs.items()
            if role_id.startswith("workflow:")
        }
        specialist_outputs = workflow_outputs or {
            role_id: output
            for role_id, output in request.previous_outputs.items()
            if role_id not in {"requirement_analyst", "supervisor"}
        }
        prompt = (
            "请作为 Supervisor 根据Requirement Analyst交付的需求规格制定"
            "任务规划和验收标准。\n"
            f"任务ID：{request.task_id}\n"
            f"项目名称：{request.project_name}\n"
            f"工作区：{request.workspace_path}\n"
            f"目标：{request.goal}\n"
            f"需求：{request.requirements}\n"
            f"RequirementSpec：\n{requirement_spec}\n"
            "已选专业智能体输出：\n"
            f"{json.dumps(specialist_outputs, ensure_ascii=False, separators=(',', ':'))}\n"
            "只负责规划和管理，不修改代码。\n"
            "必须只输出一个 JSON 对象，不要使用 Markdown 代码块，字段为："
            "task_id、objective、confirmed_requirements、deliverables、"
            "acceptance_criteria、required_tests、forbidden_scope、blockers、"
            "ready_for_development。required_tests 必须是字符串数组，只能列出"
            "项目已有或需求明确指定的测试命令，不得列出通用 Shell 操作。"
            "信息不足以安全开发时，将 ready_for_development 设为 false 并列出"
            " blockers；范围无法在一次独立开发与验收中安全完成时也必须设为"
            " false，并在 blockers 中说明需要返回需求阶段拆分为哪些有序、"
            " 可独立验收的任务。不得发明需求。"
        )
        try:
            output, error = self._invoke(prompt, request.workspace_path)
            if error:
                return RuntimeResult(
                    agent_name=self.agent_name,
                    status=RuntimeStatus.FAILED,
                    output="",
                    error=error,
                )
            if not output:
                return RuntimeResult(
                    agent_name=self.agent_name,
                    status=RuntimeStatus.FAILED,
                    output="",
                    error="Agent returned empty output",
                )
            try:
                plan = json.loads(output)
            except (json.JSONDecodeError, TypeError):
                return RuntimeResult(
                    agent_name=self.agent_name,
                    status=RuntimeStatus.FAILED,
                    output=output,
                    error="Supervisor returned invalid JSON",
                )
            if not isinstance(plan, dict):
                return RuntimeResult(
                    agent_name=self.agent_name,
                    status=RuntimeStatus.FAILED,
                    output=output,
                    error="Supervisor output must be a JSON object",
                )
            if plan.get("ready_for_development") is not True:
                return RuntimeResult(
                    agent_name=self.agent_name,
                    status=RuntimeStatus.REQUIREMENTS_REVISION,
                    output=output,
                    error=(
                        "Supervisor returned task to requirements: "
                        "scope or requirements are not ready for development"
                    ),
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

    def decision(
        self, request: SupervisorDecisionRequest
    ) -> DecisionResult:
        prompt = (
            "请作为 Supervisor 分析 Reviewer 的失败结论并决定下一步。"
            "不得修改代码，不得自行验收。\n"
            "只能输出明确的 FINAL_ACTION: COMPLETE、FINAL_ACTION: REWORK "
            "或 FINAL_ACTION: BLOCKED。\n"
            "如果选择 REWORK，必须额外输出单行 "
            "DEVELOPER_TASK: <具体修复任务>。\n\n"
            f"{json.dumps(request.model_dump(mode='json'), ensure_ascii=False, indent=2)}"
        )
        try:
            workspace_path = str(
                request.task.get("workspace_path", "")
            )
            output, error = self._invoke(prompt, workspace_path)
            if error:
                return DecisionResult(
                    action=DecisionAction.BLOCKED,
                    output="",
                    error=error,
                )
            if not output:
                return DecisionResult(
                    action=DecisionAction.BLOCKED,
                    output="",
                    error="Agent returned empty output",
                )

            actions = re.findall(
                r"(?im)^\s*FINAL_ACTION\s*:\s*"
                r"(COMPLETE|REWORK|BLOCKED)\s*$",
                output,
            )
            if not actions:
                return DecisionResult(
                    action=DecisionAction.BLOCKED,
                    output=output,
                    error="Supervisor decision missing FINAL_ACTION",
                )
            action = DecisionAction(actions[-1].upper())
            developer_task = None
            if action is DecisionAction.REWORK:
                tasks = re.findall(
                    r"(?im)^\s*DEVELOPER_TASK\s*:\s*(.+?)\s*$",
                    output,
                )
                if not tasks:
                    return DecisionResult(
                        action=DecisionAction.BLOCKED,
                        output=output,
                        error="REWORK decision missing DEVELOPER_TASK",
                    )
                developer_task = tasks[-1].strip()
            return DecisionResult(
                action=action,
                developer_task=developer_task,
                output=output,
            )
        except Exception as exc:
            return DecisionResult(
                action=DecisionAction.BLOCKED,
                output="",
                error=str(exc),
            )

    def _invoke(
        self, prompt: str, workspace_path: str
    ) -> tuple[str, str | None]:
        if self.plan_mode == "claude":
            adapter = self._claude_adapter or ClaudeCodeAdapter(
                claude_path=os.getenv("CLAUDE_PATH", "claude")
            )
            result = adapter.execute_readonly(
                ClaudeAgentRequest(
                    workspace_path=workspace_path,
                    prompt=prompt,
                )
            )
            if result.status is ClaudeAgentStatus.FAILED:
                return "", result.error or "Claude execution failed"
            return result.output.strip(), None
        result = self._agent_factory().kickoff(prompt)
        raw = result.raw
        return ("" if raw is None else str(raw).strip()), None

    @staticmethod
    def _mode_from_environment() -> str:
        enabled = os.getenv("CLAUDE_ENABLED", "false").strip().lower()
        return "claude" if enabled in {"1", "true", "yes", "on"} else "mock"
