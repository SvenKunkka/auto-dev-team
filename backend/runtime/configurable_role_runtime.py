from __future__ import annotations

import json
import os

from backend.adapters.claude_code_adapter import (
    ClaudeAgentRequest,
    ClaudeAgentStatus,
    ClaudeCodeAdapter,
)
from backend.adapters.openai_compatible_adapter import (
    OpenAICompatibleAdapter,
)
from backend.models.agent import AgentModel, AgentTemplate
from backend.runtime.agent_runtime import (
    AgentRuntime,
    RuntimeRequest,
    RuntimeResult,
    RuntimeStatus,
)


class ConfigurableRoleRuntime(AgentRuntime):
    """Execute a product-role template with a compatible configured model."""

    def __init__(
        self,
        template: AgentTemplate,
        model: AgentModel | str,
        *,
        claude_adapter: ClaudeCodeAdapter | None = None,
        api_adapter: OpenAICompatibleAdapter | None = None,
    ) -> None:
        self.template = template
        self.agent_name = template.id
        self.model = model
        self._claude_adapter = claude_adapter
        self._api_adapter = api_adapter

    def run(self, request: RuntimeRequest) -> RuntimeResult:
        workflow_outputs = [
            output
            for role_id, output in request.previous_outputs.items()
            if role_id.startswith("workflow:")
        ]
        context = {
            "task_id": request.task_id,
            "project_name": request.project_name,
            "goal": request.goal,
            "requirements": request.requirements,
            "upstream_outputs": {
                role_id: request.previous_outputs[role_id]
                for role_id in self.template.context_roles
                if role_id in request.previous_outputs
            },
            "previous_step_output": (
                workflow_outputs[-1] if workflow_outputs else ""
            ),
        }
        prompt = (
            f"角色：{self.template.name}\n"
            f"职责：{self.template.role}\n"
            f"能力边界：{self.template.description}\n\n"
            "输出必须简洁、可追溯，最多1500个汉字。明确列出：已确认事实、"
            "分析结论、风险、需要人工确认的问题、建议交付物。不得复述全部输入，"
            "不得编造未提供的市场数据、用户评论、价格、规格或测试结果。\n\n"
            f"{json.dumps(context, ensure_ascii=False, separators=(',', ':'))}"
        )
        try:
            if self.model == AgentModel.CLAUDE:
                execution = (
                    self._claude_adapter
                    or ClaudeCodeAdapter(
                        claude_path=os.getenv("CLAUDE_PATH", "claude")
                    )
                ).execute_readonly(
                    ClaudeAgentRequest(
                        workspace_path=request.workspace_path,
                        prompt=f"{self.template.system_prompt}\n\n{prompt}",
                    )
                )
                if execution.status is ClaudeAgentStatus.FAILED:
                    return self._failure(
                        execution.error or "Claude execution failed"
                    )
                output = execution.output.strip()
                evidence = {"provider": "claude", "model": "claude-code"}
            else:
                adapter = self._api_adapter or self._build_api_adapter()
                execution = adapter.execute(
                    system_prompt=self.template.system_prompt,
                    prompt=prompt,
                )
                if not execution.completed:
                    return self._failure(
                        execution.error or "Model execution failed"
                    )
                output = execution.output.strip()
                evidence = {
                    "provider": (
                        self.model.value
                        if isinstance(self.model, AgentModel)
                        else self.model
                    ),
                    "model": execution.model,
                    "usage": execution.usage,
                }
            if not output:
                return self._failure("Agent returned empty output")
            return RuntimeResult(
                agent_name=self.agent_name,
                status=RuntimeStatus.COMPLETED,
                output=output,
                evidence=evidence,
            )
        except Exception as exc:
            return self._failure(str(exc))

    def _build_api_adapter(self) -> OpenAICompatibleAdapter:
        if self.model == AgentModel.DEEPSEEK:
            return OpenAICompatibleAdapter(
                api_key=os.getenv("DEEPSEEK_API_KEY", ""),
                base_url=os.getenv(
                    "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
                ),
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                provider="deepseek",
            )
        if self.model == AgentModel.KIMI:
            return OpenAICompatibleAdapter(
                api_key=os.getenv("KIMI_API_KEY", ""),
                base_url=os.getenv(
                    "KIMI_BASE_URL", "https://api.moonshot.cn/v1"
                ),
                model=os.getenv("KIMI_MODEL", "kimi-k3"),
                provider="kimi",
            )
        raise ValueError(f"Unsupported specialist model: {self.model}")

    def _failure(self, error: str) -> RuntimeResult:
        return RuntimeResult(
            agent_name=self.agent_name,
            status=RuntimeStatus.FAILED,
            output="",
            error=error,
            evidence={"provider": self.model.value},
        )
