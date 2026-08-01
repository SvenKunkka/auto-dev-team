from __future__ import annotations

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from fastapi import FastAPI

from backend.config.runtime import RuntimeSettings
from backend.api.tasks import router as tasks_router
from backend.api.health import router as health_router
from backend.api.statistics import router as statistics_router
from backend.api.agents import router as agents_router
from backend.api.models import router as models_router
from backend.database.sqlite import SQLiteDatabase
from backend.runtime.agent_runtime import AgentRuntime
from backend.runtime.developer_runtime import DeveloperRuntime
from backend.runtime.requirement_analyst_runtime import (
    RequirementAnalystRuntime,
)
from backend.runtime.reviewer_runtime import ReviewerRuntime
from backend.runtime.supervisor_runtime import SupervisorRuntime
from backend.runtime.verification_runtime import VerificationRuntime
from backend.runtime.agent_runtime_factory import AgentRuntimeFactory
from backend.reliability.recovery_manager import RecoveryManager
from backend.reliability.workspace_lock_manager import WorkspaceLockManager
from backend.services.crew_service import CrewService
from backend.services.task_service import TaskService
from backend.services.statistics_service import StatisticsService
from backend.services.agent_catalog_service import AgentCatalogService
from backend.services.model_config_service import ModelConfigService
from backend.worker.task_worker import TaskWorker

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def create_app(
    *,
    database_path: str | Path | None = None,
    requirement_analyst_runtime: AgentRuntime | None = None,
    supervisor_runtime: AgentRuntime | None = None,
    developer_runtime: AgentRuntime | None = None,
    verification_runtime: AgentRuntime | None = None,
    reviewer_runtime: AgentRuntime | None = None,
    worker_poll_interval: float = 1.0,
    heartbeat_interval: float = 5.0,
) -> FastAPI:
    requested_env_file = Path(
        os.getenv("AUTO_DEV_ENV_FILE", str(PROJECT_ROOT / ".env"))
    ).expanduser()
    load_dotenv(requested_env_file, override=False)
    settings = RuntimeSettings.from_environment(PROJECT_ROOT)
    os.environ.setdefault("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    os.environ.setdefault("OTEL_SDK_DISABLED", "true")
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "true")

    resolved_database_path = (
        Path(database_path)
        if database_path is not None
        else settings.data_dir / "auto_dev_team.db"
    )
    database = SQLiteDatabase(resolved_database_path)
    database.initialize()
    model_config_service = ModelConfigService(database)
    agent_catalog_service = AgentCatalogService(model_config_service)
    workspace_lock_manager = WorkspaceLockManager(database)
    custom_pipeline = any(
        runtime is not None
        for runtime in (
            requirement_analyst_runtime,
            supervisor_runtime,
            developer_runtime,
            verification_runtime,
            reviewer_runtime,
        )
    )
    crew_service = CrewService(
        database=database,
        requirement_analyst_runtime=(
            requirement_analyst_runtime
            if requirement_analyst_runtime is not None
            else (None if custom_pipeline else RequirementAnalystRuntime())
        ),
        supervisor_runtime=supervisor_runtime or SupervisorRuntime(),
        developer_runtime=developer_runtime or DeveloperRuntime(),
        verification_runtime=(
            verification_runtime
            if verification_runtime is not None
            else (None if custom_pipeline else VerificationRuntime())
        ),
        reviewer_runtime=reviewer_runtime or ReviewerRuntime(),
        workspace_lock_manager=workspace_lock_manager,
        runtime_resolver=(
            None
            if custom_pipeline
            else AgentRuntimeFactory(
                agent_catalog_service, model_config_service
            ).create
        ),
        agent_catalog_service=agent_catalog_service,
    )
    task_service = TaskService(
        database, crew_service, agent_catalog_service
    )
    statistics_service = StatisticsService(
        database, agent_catalog_service
    )
    recovery_manager = RecoveryManager(
        database,
        task_service.enqueue_task,
        lock_manager=workspace_lock_manager,
    )
    task_worker = TaskWorker(
        database,
        task_service,
        lock_manager=workspace_lock_manager,
        poll_interval=worker_poll_interval,
        heartbeat_interval=heartbeat_interval,
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        recovery_report = await asyncio.to_thread(
            recovery_manager.recover_on_startup
        )
        application.state.recovery_report = recovery_report
        task_worker.start()
        try:
            yield
        finally:
            await asyncio.to_thread(task_worker.stop)

    application = FastAPI(
        title="Auto Dev Platform",
        version="1.7.0",
        lifespan=lifespan,
    )
    application.state.database = database
    application.state.task_service = task_service
    application.state.statistics_service = statistics_service
    application.state.agent_catalog_service = agent_catalog_service
    application.state.model_config_service = model_config_service
    application.state.recovery_manager = recovery_manager
    application.state.task_worker = task_worker
    application.state.runtime_settings = settings
    application.include_router(tasks_router)
    application.include_router(health_router)
    application.include_router(statistics_router)
    application.include_router(agents_router)
    application.include_router(models_router)

    @application.get("/")
    def system_status() -> dict[str, str]:
        return {
            "name": "Auto Dev Platform",
            "status": "RUNNING",
            "phase": "5",
            "environment": settings.environment,
        }

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
