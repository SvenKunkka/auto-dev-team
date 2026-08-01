from __future__ import annotations

from backend.database.sqlite import SQLiteDatabase
from backend.models.statistics import (
    AgentExecutionStatistics,
    DepartmentStatistics,
    GoalSummary,
)
from backend.services.agent_catalog_service import AgentCatalogService


class StatisticsService:
    """基于不可变Agent运行记录提供只读角色执行统计。"""

    def __init__(
        self,
        database: SQLiteDatabase,
        agent_catalog_service: AgentCatalogService | None = None,
    ) -> None:
        self.database = database
        self.agent_catalog_service = (
            agent_catalog_service or AgentCatalogService()
        )

    def agent_execution_statistics(
        self, task_id: str | None = None
    ) -> DepartmentStatistics:
        selected_goal = None
        if task_id is not None:
            task = self.database.get_task(task_id)
            if task is None:
                raise KeyError(f"任务不存在：{task_id}")
            selected_goal = GoalSummary(
                task_id=task.task_id,
                project_name=task.project_name,
                goal=task.goal,
            )

        cumulative = self.database.count_agent_runs()
        per_goal = (
            self.database.count_agent_runs(task_id=task_id)
            if task_id is not None
            else {}
        )
        return DepartmentStatistics(
            selected_goal=selected_goal,
            roles=[
                AgentExecutionStatistics(
                    agent_name=agent_name,
                    role_name=role_name,
                    goal_execution_count=per_goal.get(agent_name, 0),
                    cumulative_execution_count=cumulative.get(agent_name, 0),
                )
                for agent_name, role_name in (
                    (template.id, template.name)
                    for template in self.agent_catalog_service.catalog().templates
                )
            ],
        )
