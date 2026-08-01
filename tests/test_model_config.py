import json

from fastapi.testclient import TestClient

from backend.database.sqlite import SQLiteDatabase
from backend.main import create_app
from backend.models.agent import ModelConfigCreate
from backend.services.agent_catalog_service import AgentCatalogService
from backend.services.model_config_service import ModelConfigService


class FakeCredentialStore:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def set(self, account: str, secret: str) -> None:
        self.values[account] = secret

    def get(self, account: str) -> str:
        return self.values.get(account, "")

    def delete(self, account: str) -> None:
        self.values.pop(account, None)


def test_custom_model_uses_credential_store_and_never_persists_secret(
    tmp_path,
) -> None:
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    credentials = FakeCredentialStore()
    service = ModelConfigService(database, credentials)

    created = service.create(
        ModelConfigCreate(
            id="visual_reasoner",
            name="视觉推理模型",
            provider="Example",
            model_id="vision-1",
            base_url="https://example.test/v1",
            api_style="openai_compatible",
            description="视觉与复杂推理",
            capabilities=["reasoning", "multimodal", "vision"],
            api_key="secret-value-123",
        )
    )

    assert created.configured is True
    assert credentials.values["visual_reasoner"] == "secret-value-123"
    assert "api_key" not in created.model_dump()
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM model_configs WHERE id = 'visual_reasoner'"
        ).fetchone()
    assert "secret-value-123" not in json.dumps(dict(row))


def test_custom_model_is_available_to_specialist_templates(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    service = ModelConfigService(database, FakeCredentialStore())
    service.create(
        ModelConfigCreate(
            id="private_reasoner",
            name="私有推理模型",
            provider="Internal",
            model_id="reasoner-v1",
            base_url="https://models.example.test/v1",
            api_style="openai_compatible",
            capabilities=["reasoning"],
        )
    )
    catalog = AgentCatalogService(service)

    assert "private_reasoner" in catalog.template(
        "market_researcher"
    ).supported_models
    assert catalog.template("ux_ui_designer").default_model == (
        "claude_opus_design"
    )


def test_custom_model_delete_removes_credential(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    credentials = FakeCredentialStore()
    service = ModelConfigService(database, credentials)
    service.create(
        ModelConfigCreate(
            id="temporary_model",
            name="临时模型",
            provider="Example",
            model_id="temp-v1",
            base_url="https://example.test/v1",
            api_style="openai_compatible",
            api_key="temporary-secret",
        )
    )

    service.delete("temporary_model")

    assert credentials.get("temporary_model") == ""
    try:
        service.get("temporary_model")
    except KeyError:
        pass
    else:
        raise AssertionError("deleted model must not be returned")


def test_model_config_api_never_returns_api_key(tmp_path) -> None:
    app = create_app(database_path=tmp_path / "platform.db")
    credentials = FakeCredentialStore()
    service = ModelConfigService(app.state.database, credentials)
    app.state.model_config_service = service
    app.state.agent_catalog_service.model_config_service = service

    with TestClient(app) as client:
        created = client.post(
            "/models",
            json={
                "id": "api_model",
                "name": "API模型",
                "provider": "Example",
                "model_id": "api-v1",
                "base_url": "https://example.test/v1",
                "api_style": "openai_compatible",
                "description": "接口测试",
                "capabilities": ["reasoning"],
                "api_key": "api-secret-value",
            },
        )
        listed = client.get("/models")

    assert created.status_code == 201
    assert created.json()["configured"] is True
    assert "api_key" not in created.json()
    assert "api-secret-value" not in listed.text
