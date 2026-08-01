import os
import subprocess
import sys
from pathlib import Path

import pytest

from auto_dev_team.main import resolve_project_goal

ROOT = Path(__file__).resolve().parents[1]


def test_startup_without_api_configuration_is_safe() -> None:
    environment = os.environ.copy()
    # Empty existing values prevent python-dotenv from reloading real values
    # from the project .env while keeping credentials out of the test process.
    environment["DEEPSEEK_API_KEY"] = ""
    environment["DEEPSEEK_MODEL"] = ""

    result = subprocess.run(
        [sys.executable, "-m", "auto_dev_team.main"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    combined_output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "配置错误：缺少环境变量" in combined_output
    assert "KeyError" not in combined_output
    assert "sk-" not in combined_output


def test_project_goal_comes_from_argument_or_environment(monkeypatch) -> None:
    monkeypatch.delenv("AUTO_DEV_PROJECT_GOAL", raising=False)
    assert resolve_project_goal(["--project-goal", "实现任务API"]) == "实现任务API"

    monkeypatch.setenv("AUTO_DEV_PROJECT_GOAL", "环境变量目标")
    assert resolve_project_goal([]) == "环境变量目标"


def test_missing_project_goal_is_rejected(monkeypatch) -> None:
    monkeypatch.delenv("AUTO_DEV_PROJECT_GOAL", raising=False)
    with pytest.raises(SystemExit, match="缺少项目目标"):
        resolve_project_goal([])
