from pathlib import Path

import pytest

from backend.config.runtime import RuntimeSettings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_development_runtime_uses_project_data(
    monkeypatch,
) -> None:
    monkeypatch.delenv("AUTO_DEV_ENV", raising=False)
    monkeypatch.delenv("AUTO_DEV_DATA_DIR", raising=False)
    monkeypatch.delenv("AUTO_DEV_WORKSPACES_ROOT", raising=False)

    settings = RuntimeSettings.from_environment(PROJECT_ROOT)

    assert settings.environment == "development"
    assert settings.data_dir == PROJECT_ROOT / "data"
    assert settings.workspace_root is None


def test_production_runtime_requires_workspace_root(
    monkeypatch,
) -> None:
    monkeypatch.setenv("AUTO_DEV_ENV", "production")
    monkeypatch.delenv("AUTO_DEV_WORKSPACES_ROOT", raising=False)

    with pytest.raises(
        ValueError,
        match="AUTO_DEV_WORKSPACES_ROOT is required",
    ):
        RuntimeSettings.from_environment(PROJECT_ROOT)


def test_launchd_and_control_scripts_are_present() -> None:
    production = PROJECT_ROOT / "deploy" / "production"

    assert (production / "start.sh").is_file()
    assert (production / "stop.sh").is_file()
    assert (production / "status.sh").is_file()
    assert (
        production
        / "launchd"
        / "com.autodevplatform.backend-worker.plist"
    ).is_file()
    assert (
        production
        / "launchd"
        / "com.autodevplatform.frontend.plist"
    ).is_file()
