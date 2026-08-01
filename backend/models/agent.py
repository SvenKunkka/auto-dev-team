from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class AgentModel(StrEnum):
    DEEPSEEK = "deepseek"
    CLAUDE = "claude"
    KIMI = "kimi"
    CODEX = "codex"


class AgentKind(StrEnum):
    CORE = "core"
    SPECIALIST = "specialist"
    DELIVERY = "delivery"


class AgentModelOption(BaseModel):
    id: str
    name: str
    description: str
    provider: str = ""
    model_id: str = ""
    base_url: str = ""
    api_style: str = "built_in"
    capabilities: list[str] = Field(default_factory=list)
    configured: bool = False
    enabled: bool = True


class AgentTemplate(BaseModel):
    id: str
    name: str
    department: str
    kind: AgentKind
    role: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
    system_prompt: str
    default_model: str
    supported_models: list[str]
    order: int
    required: bool = False
    dependencies: list[str] = Field(default_factory=list)
    context_roles: list[str] = Field(default_factory=list)
    source_access: str = "provided_materials"


class AgentPreset(BaseModel):
    id: str
    name: str
    description: str
    agent_ids: list[str]


class AgentCatalog(BaseModel):
    models: list[AgentModelOption]
    templates: list[AgentTemplate]
    presets: list[AgentPreset]


class WorkflowStep(BaseModel):
    step_id: str = Field(min_length=1, max_length=64)
    role_id: str = Field(min_length=1, max_length=64)
    model_id: str = Field(min_length=1, max_length=128)
    order: int = Field(ge=0)


class ModelConfigCreate(BaseModel):
    id: str = Field(
        min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]+$"
    )
    name: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=64)
    model_id: str = Field(min_length=1, max_length=160)
    base_url: str = Field(default="", max_length=500)
    api_style: str = Field(
        pattern=r"^(openai_compatible|anthropic_messages|manual)$"
    )
    description: str = Field(default="", max_length=500)
    capabilities: list[str] = Field(default_factory=list, max_length=20)
    api_key: str = Field(default="", max_length=1000)


class ModelCredentialUpdate(BaseModel):
    api_key: str = Field(min_length=1, max_length=1000)
