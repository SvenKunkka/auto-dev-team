from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from backend.models.statistics import DepartmentStatistics
from backend.services.statistics_service import StatisticsService

router = APIRouter(prefix="/departments", tags=["departments"])


def get_statistics_service(request: Request) -> StatisticsService:
    return request.app.state.statistics_service


@router.get("/statistics", response_model=DepartmentStatistics)
def agent_execution_statistics(
    request: Request,
    task_id: str | None = None,
) -> DepartmentStatistics:
    try:
        return get_statistics_service(request).agent_execution_statistics(
            task_id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="任务不存在") from exc
