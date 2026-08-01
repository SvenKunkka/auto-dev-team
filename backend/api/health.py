from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel


router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded"]
    database: Literal["healthy", "unavailable"]
    worker: Literal["running", "stopped"]
    queue_size: int | None


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    database = request.app.state.database
    database_ok = database.health_check()
    queue_size = database.count_queued_tasks() if database_ok else None
    worker_running = request.app.state.task_worker.is_running
    return HealthResponse(
        status=(
            "healthy"
            if database_ok and worker_running
            else "degraded"
        ),
        database="healthy" if database_ok else "unavailable",
        worker="running" if worker_running else "stopped",
        queue_size=queue_size,
    )
