from __future__ import annotations

from pydantic import BaseModel, Field


class GoalSummary(BaseModel):
    task_id: str
    project_name: str
    goal: str


class AgentExecutionStatistics(BaseModel):
    agent_name: str
    role_name: str
    goal_execution_count: int = Field(ge=0)
    cumulative_execution_count: int = Field(ge=0)


class DepartmentStatistics(BaseModel):
    department_name: str = "任务统计部"
    selected_goal: GoalSummary | None = None
    roles: list[AgentExecutionStatistics]
