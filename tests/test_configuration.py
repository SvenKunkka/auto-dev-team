from pathlib import Path

import yaml
from crewai import Process

from auto_dev_team.crew import AutoDevTeam, normalize_acceptance_output

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "src" / "auto_dev_team" / "config"


def load_yaml(name: str) -> dict[str, object]:
    """读取测试所需 YAML 配置。"""
    with (CONFIG_DIR / name).open(encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)


def test_required_agents_and_tasks_exist() -> None:
    agents = load_yaml("agents.yaml")
    tasks = load_yaml("tasks.yaml")

    assert set(agents) == {
        "requirement_analyst",
        "supervisor",
        "developer",
        "verification_engineer",
        "acceptance_reviewer",
    }
    assert set(tasks) == {
        "requirement_analysis_task",
        "planning_task",
        "development_task",
        "verification_task",
        "acceptance_task",
    }


def test_task_contexts_are_explicit() -> None:
    tasks = load_yaml("tasks.yaml")

    assert tasks["planning_task"]["context"] == [
        "requirement_analysis_task"
    ]
    assert tasks["development_task"]["context"] == ["planning_task"]
    assert tasks["verification_task"]["context"] == [
        "planning_task",
        "development_task",
    ]
    assert tasks["acceptance_task"]["context"] == [
        "requirement_analysis_task",
        "planning_task",
        "development_task",
        "verification_task",
    ]


def test_runtime_process_and_task_order_are_strictly_sequential(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "test-model")
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "true")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")

    configured_crew = AutoDevTeam().crew()

    assert configured_crew.process is Process.sequential
    assert [task.name for task in configured_crew.tasks] == [
        "requirement_analysis_task",
        "planning_task",
        "development_task",
        "verification_task",
        "acceptance_task",
    ]
    assert [task.name for task in configured_crew.tasks[1].context] == [
        "requirement_analysis_task"
    ]
    assert [task.name for task in configured_crew.tasks[2].context] == [
        "planning_task"
    ]
    assert [task.name for task in configured_crew.tasks[3].context] == [
        "planning_task",
        "development_task",
    ]
    assert [task.name for task in configured_crew.tasks[4].context] == [
        "requirement_analysis_task",
        "planning_task",
        "development_task",
        "verification_task",
    ]


def test_yaml_names_match_python_methods() -> None:
    agents = load_yaml("agents.yaml")
    tasks = load_yaml("tasks.yaml")

    for name in (*agents.keys(), *tasks.keys()):
        assert callable(getattr(AutoDevTeam, name))


def test_gitignore_protects_environment_file() -> None:
    entries = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in entries


def test_prompts_describe_real_delivery_without_role_conflict() -> None:
    agents = load_yaml("agents.yaml")
    tasks = load_yaml("tasks.yaml")
    prompt_text = "\n".join(
        str(value)
        for config in (*agents.values(), *tasks.values())
        for value in config.values()
        if isinstance(value, str)
    )

    assert "实施真实代码修改" in prompt_text
    assert "实际交付物" in prompt_text
    assert "不直接修改代码" in prompt_text
    assert "不得自行验收" in prompt_text
    assert "只读检查，不得修改代码" in prompt_text
    assert "PLAN_REVIEW" not in prompt_text


def test_supervisor_is_forbidden_from_inventing_requirements() -> None:
    agents = load_yaml("agents.yaml")
    tasks = load_yaml("tasks.yaml")
    supervisor_prompt = "\n".join(
        [
            agents["supervisor"]["goal"],
            agents["supervisor"]["backstory"],
            tasks["planning_task"]["description"],
            tasks["planning_task"]["expected_output"],
        ]
    )

    for required_constraint in (
        "不得发明用户没有提供的需求",
        "信息不足时必须列出 blockers",
        "不直接修改代码",
        "required_tests",
    ):
        assert required_constraint in supervisor_prompt


def test_structured_output_fields_are_declared() -> None:
    tasks = load_yaml("tasks.yaml")

    for field in (
        "task_id",
        "objective",
        "confirmed_requirements",
        "deliverables",
        "acceptance_criteria",
        "required_tests",
        "forbidden_scope",
        "blockers",
        "ready_for_development",
    ):
        assert field in tasks["planning_task"]["expected_output"]

    for field in (
        "task_id",
        "changed_files",
        "implementation_summary",
        "tests",
        "blockers",
        "ready_for_review",
    ):
        assert field in tasks["development_task"]["expected_output"]


def test_reviewer_is_read_only_and_reviews_real_evidence() -> None:
    agents = load_yaml("agents.yaml")
    tasks = load_yaml("tasks.yaml")
    reviewer_prompt = "\n".join(
        [
            agents["acceptance_reviewer"]["goal"],
            agents["acceptance_reviewer"]["backstory"],
            tasks["acceptance_task"]["description"],
            tasks["acceptance_task"]["expected_output"],
        ]
    )

    assert "真实代码" in reviewer_prompt
    assert "Git diff" in reviewer_prompt
    assert "Developer Evidence" in reviewer_prompt
    assert "只读" in reviewer_prompt
    assert "不得修改代码" in reviewer_prompt


def test_acceptance_report_is_normalized_to_required_prefix() -> None:
    class Result:
        raw = "方案验收报告\n\nFINAL_RESULT: PASS"

    accepted, normalized = normalize_acceptance_output(Result())  # type: ignore[arg-type]

    assert accepted is True
    assert normalized.startswith("PASS\n")
