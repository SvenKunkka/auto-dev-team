#!/usr/bin/env python
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_ENV_VARS = ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL")


def load_and_validate_environment() -> None:
    """加载项目环境并用清晰中文提示缺失配置。"""
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        joined = "、".join(missing)
        raise SystemExit(
            f"配置错误：缺少环境变量 {joined}。"
            "请在项目根目录 .env 中填写后重试；不要把 API Key 发送到聊天中。"
        )

    os.environ.setdefault("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    os.environ.setdefault("OTEL_SDK_DISABLED", "true")
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "true")


def resolve_project_goal(arguments: list[str] | None = None) -> str:
    """从命令参数或环境变量读取本次任务目标。"""
    parser = argparse.ArgumentParser(description="运行 Auto Dev Team Crew")
    parser.add_argument("--project-goal")
    parsed, _ = parser.parse_known_args(arguments)
    project_goal = parsed.project_goal or os.getenv("AUTO_DEV_PROJECT_GOAL")
    if not project_goal:
        raise SystemExit(
            "配置错误：缺少项目目标。请使用 --project-goal 参数，"
            "或设置 AUTO_DEV_PROJECT_GOAL。"
        )
    return project_goal


def run(project_goal: str | None = None) -> None:
    """校验配置并运行一次五角色顺序协作。"""
    load_and_validate_environment()
    resolved_goal = project_goal or resolve_project_goal()
    (PROJECT_ROOT / "output").mkdir(parents=True, exist_ok=True)

    try:
        from auto_dev_team.crew import AutoDevTeam

        AutoDevTeam().crew().kickoff(
            inputs={"project_goal": resolved_goal}
        )
    except SystemExit:
        raise
    except Exception as exc:
        raise SystemExit(f"运行失败：{exc}") from exc


if __name__ == "__main__":
    run()
