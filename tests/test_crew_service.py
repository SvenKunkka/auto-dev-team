from backend.database.sqlite import SQLiteDatabase
from backend.models.task import TaskCreate, TaskStatus
from backend.runtime.agent_runtime import (
    AgentRuntime,
    RuntimeRequest,
    RuntimeResult,
    RuntimeStatus,
)
from backend.services.crew_service import CrewService
from backend.services.task_service import TaskService


class FakeRuntime(AgentRuntime):
    def __init__(
        self,
        agent_name: str,
        output: str,
        status: RuntimeStatus = RuntimeStatus.COMPLETED,
        evidence=None,
    ) -> None:
        self.agent_name = agent_name
        self.output = output
        self.status = status
        self.evidence = evidence
        self.requests: list[RuntimeRequest] = []

    def run(self, request: RuntimeRequest) -> RuntimeResult:
        self.requests.append(request)
        return RuntimeResult(
            agent_name=self.agent_name,
            status=self.status,
            output=self.output,
            evidence=self.evidence,
        )


class RaisingRuntime(AgentRuntime):
    agent_name = "developer"

    def run(self, request: RuntimeRequest) -> RuntimeResult:
        raise RuntimeError("developer runtime crashed")


class TrackingDatabase(SQLiteDatabase):
    def __init__(self, database_path) -> None:
        super().__init__(database_path)
        self.statuses: list[TaskStatus] = []

    def update_task(self, task_id: str, **changes):
        if changes.get("status") is not None:
            self.statuses.append(changes["status"])
        return super().update_task(task_id, **changes)

    def transition_task_status(self, task_id: str, **changes):
        result = super().transition_task_status(task_id, **changes)
        if result.status is changes["status"]:
            self.statuses.append(changes["status"])
        return result


class OneShotFailingDatabase(TrackingDatabase):
    def __init__(self, database_path) -> None:
        super().__init__(database_path)
        self.failed_once = False

    def update_task(self, task_id: str, **changes):
        if changes.get("supervisor_output") and not self.failed_once:
            self.failed_once = True
            raise RuntimeError("temporary database failure")
        return super().update_task(task_id, **changes)


def build_service(tmp_path, reviewer_output: str = "PASS\n验收通过"):
    database = TrackingDatabase(tmp_path / "platform.db")
    database.initialize()
    supervisor = FakeRuntime("supervisor", "任务规划")
    developer = FakeRuntime("developer", "开发结果")
    reviewer = FakeRuntime("reviewer", reviewer_output)
    crew_service = CrewService(database, supervisor, developer, reviewer)
    return (
        database,
        TaskService(database, crew_service),
        supervisor,
        developer,
        reviewer,
    )


def task_input() -> TaskCreate:
    return TaskCreate(
        project_name="产品知识系统",
        workspace_path="/tmp/project",
        goal="实现 Knowledge API",
        requirements=["统一入口"],
        priority="high",
        execution_mode="execute",
    )


def test_task_lifecycle_persists_all_outputs(tmp_path) -> None:
    database, service, _, developer, reviewer = build_service(tmp_path)
    created = service.create_task(task_input())

    finished = service.run_task(created.task_id)

    assert finished.status is TaskStatus.PASSED
    assert finished.requirements_output is not None
    assert finished.supervisor_output == "任务规划"
    assert finished.developer_output == "开发结果"
    assert finished.verification_output is not None
    assert finished.reviewer_output == "PASS\n验收通过"
    assert developer.requests[0].previous_outputs["supervisor"] == "任务规划"
    assert reviewer.requests[0].previous_outputs["supervisor"] == "任务规划"
    assert reviewer.requests[0].previous_outputs["developer"] == "开发结果"
    assert "requirement_analyst" in reviewer.requests[0].previous_outputs
    assert "verification_engineer" in reviewer.requests[0].previous_outputs
    assert [run.agent_name for run in database.list_agent_runs(created.task_id)] == [
        "requirement_analyst",
        "supervisor",
        "developer",
        "verification_engineer",
        "reviewer",
    ]
    assert database.statuses == [
        TaskStatus.RUNNING,
        TaskStatus.ANALYZING,
        TaskStatus.PLANNING,
        TaskStatus.DEVELOPING,
        TaskStatus.VERIFYING,
        TaskStatus.REVIEWING,
        TaskStatus.PASSED,
    ]


def test_supervisor_scope_gate_stops_before_developer(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    supervisor = FakeRuntime(
        "supervisor",
        '{"ready_for_development":false,"blockers":["范围过大"]}',
        RuntimeStatus.REQUIREMENTS_REVISION,
    )
    developer = FakeRuntime("developer", "不应执行")
    service = TaskService(
        database,
        CrewService(
            database,
            supervisor,
            developer,
            FakeRuntime("reviewer", "PASS"),
        ),
    )
    created = service.create_task(task_input())

    finished = service.run_task(created.task_id)

    assert finished.status is TaskStatus.REQUIREMENTS_REVISION
    assert developer.requests == []
    assert finished.required_action is not None


def test_human_retry_uses_next_persisted_iteration(tmp_path) -> None:
    database, service, _, _, _ = build_service(tmp_path)
    created = service.create_task(task_input())
    database.create_task_iteration(
        task_id=created.task_id,
        iteration=1,
        supervisor_output="旧计划",
        developer_output="旧开发结果",
        reviewer_output="FAIL",
        status=TaskStatus.FAILED,
    )
    database.update_task(created.task_id, status=TaskStatus.FAILED)

    service.retry_task(created.task_id)
    finished = service.run_task(created.task_id)

    assert finished.status is TaskStatus.PASSED
    assert [
        item.iteration
        for item in database.list_task_iterations(created.task_id)
    ] == [1, 2]
    assert database.list_workspace_locks()[-1].status == "RELEASED"


def test_retry_resumes_from_failed_verification_stage(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    analyst = FakeRuntime("requirement_analyst", "结构化需求")
    supervisor = FakeRuntime("supervisor", "任务规划")
    developer = FakeRuntime("developer", "开发结果")
    verification = FakeRuntime(
        "verification_engineer",
        "",
        status=RuntimeStatus.FAILED,
    )
    reviewer = FakeRuntime("reviewer", "PASS")
    service = TaskService(
        database,
        CrewService(
            database,
            supervisor,
            developer,
            reviewer,
            requirement_analyst_runtime=analyst,
            verification_runtime=verification,
        ),
    )
    created = service.create_task(task_input())

    failed = service.run_task(created.task_id)
    verification.status = RuntimeStatus.COMPLETED
    verification.output = "PASS"
    service.retry_task(created.task_id)
    finished = service.run_task(created.task_id)

    assert failed.status is TaskStatus.FAILED
    assert failed.resume_stage is TaskStatus.VERIFYING
    assert finished.status is TaskStatus.PASSED
    assert len(analyst.requests) == 1
    assert len(supervisor.requests) == 1
    assert len(developer.requests) == 1
    assert len(verification.requests) == 2
    assert len(reviewer.requests) == 1


def test_retry_resumes_from_failed_reviewer_stage(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    analyst = FakeRuntime("requirement_analyst", "结构化需求")
    supervisor = FakeRuntime("supervisor", "任务规划")
    developer = FakeRuntime("developer", "开发结果")
    verification = FakeRuntime("verification_engineer", "PASS")
    reviewer = FakeRuntime(
        "reviewer",
        "",
        status=RuntimeStatus.FAILED,
    )
    service = TaskService(
        database,
        CrewService(
            database,
            supervisor,
            developer,
            reviewer,
            requirement_analyst_runtime=analyst,
            verification_runtime=verification,
        ),
    )
    created = service.create_task(task_input())

    failed = service.run_task(created.task_id)
    reviewer.status = RuntimeStatus.COMPLETED
    reviewer.output = "PASS"
    service.retry_task(created.task_id)
    finished = service.run_task(created.task_id)

    assert failed.status is TaskStatus.FAILED
    assert failed.resume_stage is TaskStatus.REVIEWING
    assert finished.status is TaskStatus.PASSED
    assert len(analyst.requests) == 1
    assert len(supervisor.requests) == 1
    assert len(developer.requests) == 1
    assert len(verification.requests) == 1
    assert len(reviewer.requests) == 2


def test_reviewer_fail_without_decision_support_is_blocked(tmp_path) -> None:
    _, service, *_ = build_service(tmp_path, "FAIL\n测试失败")
    created = service.create_task(task_input())

    assert service.run_task(created.task_id).status is TaskStatus.BLOCKED


def test_runtime_failure_marks_lifecycle_failed(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    supervisor = FakeRuntime(
        "supervisor", "", status=RuntimeStatus.FAILED
    )
    crew_service = CrewService(
        database,
        supervisor,
        FakeRuntime("developer", "不应执行"),
        FakeRuntime("reviewer", "PASS"),
    )
    service = TaskService(database, crew_service)
    created = service.create_task(task_input())

    finished = service.run_task(created.task_id)

    assert finished.status is TaskStatus.FAILED
    assert len(database.list_agent_runs(created.task_id)) == 2


def test_developer_runtime_exception_is_saved_and_marks_task_failed(
    tmp_path,
) -> None:
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    service = TaskService(
        database,
        CrewService(
            database,
            FakeRuntime("supervisor", "任务规划"),
            RaisingRuntime(),
            FakeRuntime("reviewer", "PASS"),
        ),
    )
    created = service.create_task(task_input())

    finished = service.run_task(created.task_id)
    runs = database.list_agent_runs(created.task_id)

    assert finished.status is TaskStatus.FAILED
    assert finished.developer_output == "developer runtime crashed"
    assert [run.status for run in runs] == [
        "COMPLETED",
        "COMPLETED",
        "FAILED",
    ]
    assert runs[-1].output == "developer runtime crashed"


def test_transient_database_error_does_not_leave_task_in_progress(
    tmp_path,
) -> None:
    database = OneShotFailingDatabase(tmp_path / "platform.db")
    database.initialize()
    service = TaskService(
        database,
        CrewService(
            database,
            FakeRuntime("supervisor", "任务规划"),
            FakeRuntime("developer", "开发结果"),
            FakeRuntime("reviewer", "PASS"),
        ),
    )
    created = service.create_task(task_input())

    finished = service.run_task(created.task_id)

    assert finished.status is TaskStatus.FAILED
    assert finished.status not in {
        TaskStatus.ANALYZING,
        TaskStatus.PLANNING,
        TaskStatus.DEVELOPING,
        TaskStatus.VERIFYING,
        TaskStatus.REVIEWING,
    }


def test_developer_evidence_is_saved_as_task_artifacts(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    evidence = {
        "changed_files": ["src/app.py"],
        "git_diff": "+changed",
        "test_results": [{"command": ["pytest"], "exit_code": 0}],
        "commands": [["codex", "exec"], ["pytest"]],
        "codex_output": "实现完成",
    }
    service = TaskService(
        database,
        CrewService(
            database,
            FakeRuntime("supervisor", "任务规划"),
            FakeRuntime("developer", "开发结果", evidence=evidence),
            FakeRuntime("reviewer", "PASS"),
        ),
    )
    created = service.create_task(task_input())

    finished = service.run_task(created.task_id)
    artifacts = database.list_task_artifacts(created.task_id)

    assert finished.status is TaskStatus.PASSED
    assert {artifact.artifact_type for artifact in artifacts} == {
        "git_diff",
        "changed_files",
        "test_results",
        "codex_output",
    }
