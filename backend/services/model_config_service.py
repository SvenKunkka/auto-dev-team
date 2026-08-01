from __future__ import annotations

import json
import os

from backend.database.sqlite import SQLiteDatabase, utc_now
from backend.models.agent import AgentModelOption, ModelConfigCreate
from backend.security.credential_store import (
    CredentialStore,
    MacOSKeychainCredentialStore,
)


BUILTIN_MODELS = [
    AgentModelOption(
        id="deepseek",
        name="DeepSeek V4 Flash",
        provider="DeepSeek",
        model_id="environment",
        api_style="openai_compatible",
        description="响应快，适合结构化需求、文字分析和常规推理。",
        capabilities=["reasoning", "structured_output", "fast"],
    ),
    AgentModelOption(
        id="claude",
        name="Claude Code",
        provider="Anthropic CLI",
        model_id="claude-code",
        api_style="cli",
        description="擅长复杂推理、长任务规划、代码库理解和工具调用。",
        capabilities=["reasoning", "coding", "long_context", "tool_use"],
    ),
    AgentModelOption(
        id="kimi",
        name="Kimi K3",
        provider="Moonshot",
        model_id="environment",
        api_style="openai_compatible",
        description="擅长超长上下文、深度推理以及图片和文档等多模态输入。",
        capabilities=[
            "reasoning",
            "multimodal",
            "vision",
            "long_context",
        ],
    ),
    AgentModelOption(
        id="codex",
        name="Codex CLI",
        provider="OpenAI CLI",
        model_id="codex",
        api_style="cli",
        description="专注真实代码修改、调试、测试执行和工程交付。",
        capabilities=["coding", "reasoning", "tool_use"],
    ),
    AgentModelOption(
        id="claude_opus_design",
        name="Claude Opus · 设计模式",
        provider="Anthropic",
        model_id="claude-opus-4-7",
        base_url="https://api.anthropic.com",
        api_style="anthropic_messages",
        description=(
            "自动化UI/UX设计配置，强调视觉推理、设计系统、线框和交互原型。"
        ),
        capabilities=[
            "design",
            "reasoning",
            "multimodal",
            "vision",
            "long_context",
        ],
    ),
    AgentModelOption(
        id="claude_design_handoff",
        name="Claude Design · 人工交接",
        provider="Anthropic Labs",
        model_id="claude-design",
        api_style="manual",
        description="生成设计任务包后由人员进入Claude Design完成视觉设计。",
        capabilities=["design", "multimodal", "vision", "manual_handoff"],
        configured=True,
    ),
]


class ModelConfigService:
    def __init__(
        self,
        database: SQLiteDatabase,
        credential_store: CredentialStore | None = None,
    ) -> None:
        self.database = database
        self.credential_store = (
            credential_store or MacOSKeychainCredentialStore()
        )
        self._hydrate_environment()

    def list_models(self) -> list[AgentModelOption]:
        builtins = []
        for item in BUILTIN_MODELS:
            model_id = item.model_id
            if item.id == "deepseek":
                model_id = os.getenv("DEEPSEEK_MODEL", model_id)
            elif item.id == "kimi":
                model_id = os.getenv("KIMI_MODEL", model_id)
            elif item.id == "claude_opus_design":
                model_id = os.getenv("ANTHROPIC_DESIGN_MODEL", model_id)
            builtins.append(
                item.model_copy(
                    update={
                        "configured": self._builtin_ready(item.id),
                        "model_id": model_id,
                    }
                )
            )
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM model_configs ORDER BY created_at, id"
            ).fetchall()
        return builtins + [self._from_row(row) for row in rows]

    def get(self, model_id: str) -> AgentModelOption:
        model = next(
            (item for item in self.list_models() if item.id == model_id),
            None,
        )
        if model is None:
            raise KeyError(f"模型不存在：{model_id}")
        return model

    def create(self, payload: ModelConfigCreate) -> AgentModelOption:
        if any(item.id == payload.id for item in BUILTIN_MODELS):
            raise ValueError("不能覆盖内置模型")
        timestamp = utc_now()
        credential_ref = (
            f"keychain:{payload.id}" if payload.api_key.strip() else None
        )
        if payload.api_key.strip():
            self.credential_store.set(payload.id, payload.api_key.strip())
        try:
            with self.database.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO model_configs (
                        id, name, provider, model_id, base_url, api_style,
                        description, capabilities, enabled, credential_ref,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (
                        payload.id,
                        payload.name,
                        payload.provider,
                        payload.model_id,
                        payload.base_url.rstrip("/"),
                        payload.api_style,
                        payload.description,
                        json.dumps(payload.capabilities, ensure_ascii=False),
                        credential_ref,
                        timestamp,
                        timestamp,
                    ),
                )
        except Exception:
            if credential_ref:
                self.credential_store.delete(payload.id)
            raise
        return self.get(payload.id)

    def set_credential(
        self, model_id: str, api_key: str
    ) -> AgentModelOption:
        model = self.get(model_id)
        self.credential_store.set(model_id, api_key.strip())
        env_name = self._environment_key(model_id)
        if env_name:
            os.environ[env_name] = api_key.strip()
        if not any(item.id == model_id for item in BUILTIN_MODELS):
            with self.database.connect() as connection:
                connection.execute(
                    "UPDATE model_configs SET credential_ref = ?, "
                    "updated_at = ? WHERE id = ?",
                    (f"keychain:{model_id}", utc_now(), model_id),
                )
        return self.get(model_id)

    def credential(self, model_id: str) -> str:
        keychain_value = self.credential_store.get(model_id)
        if keychain_value:
            return keychain_value
        env_name = self._environment_key(model_id)
        return os.getenv(env_name, "") if env_name else ""

    def delete(self, model_id: str) -> None:
        if any(item.id == model_id for item in BUILTIN_MODELS):
            raise ValueError("不能删除内置模型")
        with self.database.connect() as connection:
            task_rows = connection.execute(
                "SELECT workflow_steps, agent_models FROM tasks"
            ).fetchall()
            for row in task_rows:
                workflow = json.loads(row["workflow_steps"] or "[]")
                agent_models = json.loads(row["agent_models"] or "{}")
                if model_id in agent_models.values() or any(
                    step.get("model_id") == model_id
                    for step in workflow
                    if isinstance(step, dict)
                ):
                    raise ValueError("模型已被任务引用，不能删除")
            result = connection.execute(
                "DELETE FROM model_configs WHERE id = ?", (model_id,)
            )
        if result.rowcount == 0:
            raise KeyError(f"模型不存在：{model_id}")
        self.credential_store.delete(model_id)

    def _builtin_ready(self, model_id: str) -> bool:
        if model_id == "claude_design_handoff":
            return True
        if model_id == "claude":
            return os.getenv("CLAUDE_ENABLED", "").lower() == "true"
        if model_id == "codex":
            return os.getenv("CODEX_ENABLED", "").lower() == "true"
        env_name = self._environment_key(model_id)
        return bool(os.getenv(env_name, "")) if env_name else False

    @staticmethod
    def _environment_key(model_id: str) -> str | None:
        return {
            "deepseek": "DEEPSEEK_API_KEY",
            "kimi": "KIMI_API_KEY",
            "claude_opus_design": "ANTHROPIC_API_KEY",
        }.get(model_id)

    def _hydrate_environment(self) -> None:
        for model_id in ("deepseek", "kimi", "claude_opus_design"):
            env_name = self._environment_key(model_id)
            if not env_name or os.getenv(env_name):
                continue
            secret = self.credential_store.get(model_id)
            if secret:
                os.environ[env_name] = secret

    def _from_row(self, row) -> AgentModelOption:
        return AgentModelOption(
            id=row["id"],
            name=row["name"],
            provider=row["provider"],
            model_id=row["model_id"],
            base_url=row["base_url"],
            api_style=row["api_style"],
            description=row["description"],
            capabilities=json.loads(row["capabilities"]),
            configured=bool(row["credential_ref"]),
            enabled=bool(row["enabled"]),
        )
