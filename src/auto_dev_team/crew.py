import os
import re
from typing import Any

from crewai import Agent, Crew, LLM, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.tasks.task_output import TaskOutput


def build_deepseek_llm() -> LLM:
    """根据已验证的环境变量创建 DeepSeek LLM。"""
    model = os.environ["DEEPSEEK_MODEL"]
    return LLM(
        model=f"deepseek/{model}",
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        temperature=0.2,
    )


def normalize_acceptance_output(result: TaskOutput) -> tuple[bool, Any]:
    """规范化正式验收结论且不触发重试。"""
    _, normalized = normalize_review_text(result.raw)
    return True, normalized


def normalize_review_text(raw: str) -> tuple[str, str]:
    """只读取第一行结论或明确的 FINAL_RESULT 字段。"""
    raw = raw.strip()
    final_results = re.findall(
        r"(?im)^\s*FINAL_RESULT\s*:\s*(PASS|FAIL|BLOCKED)\s*$",
        raw,
    )
    if final_results:
        verdict = final_results[-1].upper()
        return verdict, f"{verdict}\n\n{raw}"

    first_line = next(
        (line.strip() for line in raw.splitlines() if line.strip()),
        "",
    )
    if first_line in {"PASS", "FAIL", "BLOCKED"}:
        return first_line, raw

    return "BLOCKED", (
        "BLOCKED\n\n"
        "验收输出首行未包含正式结论，且没有 FINAL_RESULT 字段，"
        "因此按安全规则阻止任务继续。\n\n"
        f"{raw}"
    )


@CrewBase
class AutoDevTeam:
    """严格顺序执行的五角色 Crew。"""

    agents: list[BaseAgent]
    tasks: list[Task]

    @agent
    def requirement_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["requirement_analyst"],  # type: ignore[index]
            llm=build_deepseek_llm(),
            verbose=True,
        )

    @agent
    def supervisor(self) -> Agent:
        return Agent(
            config=self.agents_config["supervisor"],  # type: ignore[index]
            llm=build_deepseek_llm(),
            verbose=True,
        )

    @agent
    def developer(self) -> Agent:
        return Agent(
            config=self.agents_config["developer"],  # type: ignore[index]
            llm=build_deepseek_llm(),
            verbose=True,
        )

    @agent
    def verification_engineer(self) -> Agent:
        return Agent(
            config=self.agents_config["verification_engineer"],  # type: ignore[index]
            llm=build_deepseek_llm(),
            verbose=True,
        )

    @agent
    def acceptance_reviewer(self) -> Agent:
        return Agent(
            config=self.agents_config["acceptance_reviewer"],  # type: ignore[index]
            llm=build_deepseek_llm(),
            verbose=True,
        )

    @task
    def requirement_analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config["requirement_analysis_task"],  # type: ignore[index]
        )

    @task
    def planning_task(self) -> Task:
        return Task(
            config=self.tasks_config["planning_task"],  # type: ignore[index]
            context=[self.requirement_analysis_task()],
        )

    @task
    def development_task(self) -> Task:
        return Task(
            config=self.tasks_config["development_task"],  # type: ignore[index]
            context=[self.planning_task()],
        )

    @task
    def verification_task(self) -> Task:
        return Task(
            config=self.tasks_config["verification_task"],  # type: ignore[index]
            context=[self.planning_task(), self.development_task()],
        )

    @task
    def acceptance_task(self) -> Task:
        return Task(
            config=self.tasks_config["acceptance_task"],  # type: ignore[index]
            context=[
                self.requirement_analysis_task(),
                self.planning_task(),
                self.development_task(),
                self.verification_task(),
            ],
            output_file="output/acceptance_report.md",
            guardrail=normalize_acceptance_output,
        )

    @crew
    def crew(self) -> Crew:
        """创建无委派、无记忆、无遥测分享的顺序 Crew。"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            memory=False,
            share_crew=False,
        )
