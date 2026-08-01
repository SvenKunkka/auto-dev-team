from __future__ import annotations

from collections.abc import Callable

from backend.models.agent import AgentModel
from backend.adapters.anthropic_messages_adapter import (
    AnthropicMessagesAdapter,
)
from backend.adapters.openai_compatible_adapter import (
    OpenAICompatibleAdapter,
)
from backend.runtime.agent_runtime import AgentRuntime
from backend.runtime.configurable_role_runtime import (
    ConfigurableRoleRuntime,
)
from backend.runtime.developer_runtime import DeveloperRuntime
from backend.runtime.requirement_analyst_runtime import (
    RequirementAnalystRuntime,
)
from backend.runtime.reviewer_runtime import ReviewerRuntime
from backend.runtime.supervisor_runtime import SupervisorRuntime
from backend.runtime.verification_runtime import VerificationRuntime
from backend.runtime.manual_handoff_runtime import ManualHandoffRuntime
from backend.services.agent_catalog_service import AgentCatalogService
from backend.services.model_config_service import ModelConfigService


RuntimeResolver = Callable[[str, str], AgentRuntime]


class AgentRuntimeFactory:
    def __init__(
        self,
        catalog: AgentCatalogService,
        model_config_service: ModelConfigService | None = None,
    ) -> None:
        self.catalog = catalog
        self.model_config_service = model_config_service

    def create(self, role_id: str, model_id: str) -> AgentRuntime:
        template = self.catalog.template(role_id)
        if model_id not in template.supported_models:
            raise ValueError(
                f"{template.name} does not support {model_id}"
            )
        try:
            model = AgentModel(model_id)
        except ValueError:
            return self._create_configured(template, model_id)
        if role_id == "requirement_analyst":
            return RequirementAnalystRuntime()
        if role_id == "supervisor":
            return SupervisorRuntime(
                plan_mode=(
                    "claude"
                    if model is AgentModel.CLAUDE
                    else "mock"
                )
            )
        if role_id == "developer":
            return DeveloperRuntime()
        if role_id == "verification_engineer":
            return VerificationRuntime(verification_mode=model.value)
        if role_id == "reviewer":
            return ReviewerRuntime(review_mode=model.value)
        return ConfigurableRoleRuntime(template, model)

    def _create_configured(
        self, template, model_id: str
    ) -> AgentRuntime:
        if self.model_config_service is None:
            raise ValueError(f"Model is not configured: {model_id}")
        config = self.model_config_service.get(model_id)
        if config.api_style == "manual":
            return ManualHandoffRuntime(
                template.id,
                config.name,
                "https://claude.com/product/design",
            )
        api_key = self.model_config_service.credential(model_id)
        if config.api_style == "anthropic_messages":
            adapter = AnthropicMessagesAdapter(
                api_key=api_key,
                model=config.model_id,
                base_url=config.base_url or "https://api.anthropic.com",
            )
        elif config.api_style == "openai_compatible":
            adapter = OpenAICompatibleAdapter(
                api_key=api_key,
                base_url=config.base_url,
                model=config.model_id,
                provider=config.provider,
            )
        else:
            raise ValueError(
                f"Unsupported model API style: {config.api_style}"
            )
        return ConfigurableRoleRuntime(
            template, model_id, api_adapter=adapter
        )
