from backend.database.sqlite import SQLiteDatabase
from backend.models.task import TaskCreate, TaskStatus
from backend.runtime.agent_runtime import (
    AgentRuntime,
    RuntimeRequest,
    RuntimeResult,
    RuntimeStatus,
)
from backend.runtime.supervisor_runtime import (
    DecisionAction,
    DecisionResult,
    SupervisorDecisionRequest,
)
from backend.services.crew_service import CrewService
from backend.services.task_service import TaskService


class SupervisorMock(AgentRuntime):
    agent_name = "supervisor"

    def __init__(self, decisions: list[DecisionResult] | None = None) -> None:
        self.decisions = decisions or []
        self.decision_requests: list[SupervisorDecisionRequest] = []

    def run(self, request: RuntimeRequest) -> RuntimeResult:
        return RuntimeResult(
            agent_name=self.agent_name,
            status=RuntimeStatus.COMPLETED,
            output="原始任务计划",
        )

    def decision(
        self, request: SupervisorDecisionRequest
    ) -> DecisionResult:
        self.decision_requests.append(request)
        return self.decisions[len(self.decision_requests) - 1]


class SequenceRuntime(AgentRuntime):
    def __init__(self, agent_name: str, outputs: list[str]) -> None:
        self.agent_name = agent_name
        self.outputs = outputs
        self.requests: list[RuntimeRequest] = []

    def run(self, request: RuntimeRequest) -> RuntimeResult:
        self.requests.append(request)
        return RuntimeResult(
            agent_name=self.agent_name,
            status=RuntimeStatus.COMPLETED,
            output=self.outputs[len(self.requests) - 1],
            evidence=(
                {"git_diff": "+changed", "test_results": []}
                if self.agent_name == "developer"
                else None
            ),
        )


def task_input(max_retry: int = 3) -> TaskCreate:
    return TaskCreate(
        project_name="产品知识系统",
        workspace_path="/tmp/project",
        goal="实现Knowledge API",
        requirements=["统一查询入口"],
        priority="high",
        execution_mode="execute",
        max_retry=max_retry,
    )


def build_service(
    tmp_path,
    supervisor: SupervisorMock,
    developer: SequenceRuntime,
    reviewer: SequenceRuntime,
) -> tuple[SQLiteDatabase, TaskService]:
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    crew_service = CrewService(
        database, supervisor, developer, reviewer
    )
    return database, TaskService(database, crew_service)


def test_reviewer_pass_completes_in_one_iteration(tmp_path) -> None:
    supervisor = SupervisorMock()
    developer = SequenceRuntime("developer", ["开发结果"])
    reviewer = SequenceRuntime("reviewer", ["PASS\n验收通过"])
    database, service = build_service(
        tmp_path, supervisor, developer, reviewer
    )
    created = service.create_task(task_input())

    finished = service.run_task(created.task_id)
    iterations = database.list_task_iterations(created.task_id)

    assert finished.status is TaskStatus.PASSED
    assert finished.retry_count == 0
    assert len(developer.requests) == 1
    assert len(reviewer.requests) == 1
    assert supervisor.decision_requests == []
    assert [item.status for item in iterations] == [TaskStatus.PASSED]


def test_fail_rework_then_second_iteration_passes(tmp_path) -> None:
    supervisor = SupervisorMock(
        [
            DecisionResult(
                action=DecisionAction.REWORK,
                developer_task="修复失败测试",
                output=(
                    "DEVELOPER_TASK: 修复失败测试\n"
                    "FINAL_ACTION: REWORK"
                ),
            )
        ]
    )
    developer = SequenceRuntime(
        "developer", ["第一轮开发", "第二轮修复"]
    )
    reviewer = SequenceRuntime(
        "reviewer", ["FAIL\n测试失败", "PASS\n验收通过"]
    )
    database, service = build_service(
        tmp_path, supervisor, developer, reviewer
    )
    created = service.create_task(task_input())

    finished = service.run_task(created.task_id)
    iterations = database.list_task_iterations(created.task_id)

    assert finished.status is TaskStatus.PASSED
    assert finished.retry_count == 1
    assert len(developer.requests) == 2
    assert len(reviewer.requests) == 2
    assert len(supervisor.decision_requests) == 1
    assert "修复失败测试" in (
        developer.requests[1].previous_outputs["supervisor"]
    )
    assert [item.status for item in iterations] == [
        TaskStatus.FAILED,
        TaskStatus.PASSED,
    ]


def test_exceeding_max_retry_becomes_blocked(tmp_path) -> None:
    supervisor = SupervisorMock(
        [
            DecisionResult(
                action=DecisionAction.REWORK,
                developer_task="再次修复",
                output="FINAL_ACTION: REWORK",
            )
        ]
    )
    developer = SequenceRuntime("developer", ["开发1", "开发2"])
    reviewer = SequenceRuntime(
        "reviewer", ["FAIL\n失败1", "FAIL\n失败2"]
    )
    database, service = build_service(
        tmp_path, supervisor, developer, reviewer
    )
    created = service.create_task(task_input(max_retry=1))

    finished = service.run_task(created.task_id)
    iterations = database.list_task_iterations(created.task_id)

    assert finished.status is TaskStatus.BLOCKED
    assert finished.retry_count == 1
    assert len(developer.requests) == 2
    assert len(reviewer.requests) == 2
    assert len(supervisor.decision_requests) == 1
    assert len(iterations) == 2


def test_supervisor_blocked_decision_stops_loop(tmp_path) -> None:
    supervisor = SupervisorMock(
        [
            DecisionResult(
                action=DecisionAction.BLOCKED,
                output="FINAL_ACTION: BLOCKED",
            )
        ]
    )
    developer = SequenceRuntime("developer", ["开发结果"])
    reviewer = SequenceRuntime("reviewer", ["FAIL\n缺少需求"])
    database, service = build_service(
        tmp_path, supervisor, developer, reviewer
    )
    created = service.create_task(task_input())

    finished = service.run_task(created.task_id)

    assert finished.status is TaskStatus.BLOCKED
    assert finished.retry_count == 0
    assert len(developer.requests) == 1
    assert len(reviewer.requests) == 1
    assert len(supervisor.decision_requests) == 1
