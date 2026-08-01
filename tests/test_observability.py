from backend.database.sqlite import SQLiteDatabase
from backend.models.task import TaskCreate
from backend.observability.logger import EventType, StructuredLogger
from backend.runtime.agent_runtime import (
    AgentRuntime,
    RuntimeRequest,
    RuntimeResult,
    RuntimeStatus,
)
from backend.services.crew_service import CrewService
from backend.services.task_service import TaskService


class RuntimeFake(AgentRuntime):
    def __init__(self, agent_name: str, output: str) -> None:
        self.agent_name = agent_name
        self.output = output

    def run(self, request: RuntimeRequest) -> RuntimeResult:
        return RuntimeResult(
            agent_name=self.agent_name,
            status=RuntimeStatus.COMPLETED,
            output=self.output,
        )


def test_execution_logs_are_persisted_for_lifecycle(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    service = TaskService(
        database,
        CrewService(
            database,
            RuntimeFake("supervisor", "计划"),
            RuntimeFake("developer", "结果"),
            RuntimeFake("reviewer", "PASS\n通过"),
        ),
    )
    task = service.create_task(
        TaskCreate(
            project_name="可观测测试",
            workspace_path=str(tmp_path),
            goal="验证日志",
            requirements=[],
            execution_mode="execute",
        )
    )

    service.run_task(task.task_id)

    logs = database.list_execution_logs(task.task_id)
    assert [log.event_type for log in logs] == [
        "TASK_CREATED",
        "TASK_STARTED",
        "REQUIREMENT_ANALYSIS_STARTED",
        "REQUIREMENT_ANALYSIS_FINISHED",
        "SUPERVISOR_STARTED",
        "SUPERVISOR_FINISHED",
        "DEVELOPER_STARTED",
        "VERIFICATION_STARTED",
        "VERIFICATION_FINISHED",
        "REVIEW_STARTED",
        "TASK_FINISHED",
    ]
    assert logs[-1].message == "Task finished with PASSED"


def test_structured_logger_preserves_agent_and_level(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    task = database.create_task(
        "task-log",
        TaskCreate(
            project_name="日志",
            workspace_path=str(tmp_path),
            goal="记录错误",
            requirements=[],
        ),
    )

    StructuredLogger(database).log(
        task_id=task.task_id,
        event_type=EventType.ERROR,
        agent_name="developer",
        level="error",
        message="boom",
    )

    log = database.list_execution_logs(task.task_id)[0]
    assert log.agent_name == "developer"
    assert log.level == "ERROR"
    assert log.message == "boom"
