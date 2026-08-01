from fastapi.testclient import TestClient

from backend.database.sqlite import SQLiteDatabase
from backend.main import create_app
from backend.adapters.openai_compatible_adapter import LLMExecutionResult
from backend.models.agent import AgentModel, WorkflowStep
from backend.models.task import TaskCreate, TaskStatus
from backend.runtime.agent_runtime import (
    AgentRuntime,
    RuntimeRequest,
    RuntimeResult,
    RuntimeStatus,
)
from backend.runtime.configurable_role_runtime import (
    ConfigurableRoleRuntime,
)
from backend.services.agent_catalog_service import AgentCatalogService
from backend.services.crew_service import CrewService
from backend.services.task_service import TaskService


class TrackingRuntime(AgentRuntime):
    def __init__(
        self,
        agent_name: str,
        calls: list[str],
        output: str,
    ) -> None:
        self.agent_name = agent_name
        self.calls = calls
        self.output = output

    def run(self, request: RuntimeRequest) -> RuntimeResult:
        self.calls.append(self.agent_name)
        return RuntimeResult(
            agent_name=self.agent_name,
            status=RuntimeStatus.COMPLETED,
            output=self.output,
        )


class CapturingAPIAdapter:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def execute(self, *, system_prompt: str, prompt: str):
        self.prompts.append(prompt)
        return LLMExecutionResult(
            completed=True,
            output="专业分析结果",
            model="kimi-k3",
            usage={"total_tokens": 100},
        )


def test_catalog_exposes_hardware_product_roles_and_presets(
    tmp_path,
) -> None:
    app = create_app(database_path=tmp_path / "platform.db")

    with TestClient(app) as client:
        response = client.get("/agents/catalog")

    assert response.status_code == 200
    catalog = response.json()
    role_ids = {item["id"] for item in catalog["templates"]}
    assert {
        "market_researcher",
        "user_insight_researcher",
        "competitive_analyst",
        "ux_ui_designer",
        "hardware_architect",
        "bom_cost_engineer",
        "compliance_specialist",
        "test_validation_planner",
    }.issubset(role_ids)
    assert {item["id"] for item in catalog["models"]} == {
        "deepseek",
        "claude",
        "kimi",
        "codex",
        "claude_opus_design",
        "claude_design_handoff",
    }
    templates = {item["id"]: item for item in catalog["templates"]}
    assert templates["ux_ui_designer"]["default_model"] == (
        "claude_opus_design"
    )
    assert templates["supervisor"]["name"] == "产品交付规划师"
    assert templates["developer"]["name"] == "软件实现工程师"
    assert templates["reviewer"]["name"] == "产品质量验收经理"
    assert {item["id"] for item in catalog["presets"]} == {
        "product_discovery",
        "hardware_definition",
        "software_delivery",
        "full_product_team",
    }


def test_catalog_rejects_incompatible_model_and_missing_dependency() -> None:
    catalog = AgentCatalogService()

    try:
        catalog.validate_selection(
            ["requirement_analyst", "supervisor", "developer"],
            {"developer": "deepseek"},
        )
    except ValueError as exc:
        assert "缺少依赖角色" in str(exc)
    else:
        raise AssertionError("missing delivery roles should be rejected")

    try:
        catalog.validate_selection(
            ["requirement_analyst", "supervisor"],
            {"requirement_analyst": "claude"},
        )
    except ValueError as exc:
        assert "不支持模型" in str(exc)
    else:
        raise AssertionError("incompatible model should be rejected")


def test_selected_specialists_run_in_template_order_and_are_saved(
    tmp_path,
) -> None:
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    calls: list[str] = []
    runtimes = {
        "requirement_analyst": TrackingRuntime(
            "requirement_analyst",
            calls,
            '{"ready_for_planning":true}',
        ),
        "market_researcher": TrackingRuntime(
            "market_researcher", calls, "市场研究结果"
        ),
        "competitive_analyst": TrackingRuntime(
            "competitive_analyst", calls, "竞品分析结果"
        ),
        "supervisor": TrackingRuntime(
            "supervisor", calls, '{"ready_for_development":true}'
        ),
    }
    catalog = AgentCatalogService()
    service = TaskService(
        database,
        CrewService(
            database,
            runtimes["supervisor"],
            TrackingRuntime("developer", calls, "unused"),
            TrackingRuntime("reviewer", calls, "unused"),
            requirement_analyst_runtime=runtimes[
                "requirement_analyst"
            ],
            runtime_resolver=lambda role_id, _: runtimes[role_id],
            agent_catalog_service=catalog,
        ),
        catalog,
    )
    created = service.create_task(
        TaskCreate(
            project_name="硬件新品",
            workspace_path="/tmp/hardware-product",
            goal="定义新一代输入设备",
            requirements=["分析市场与竞品"],
            execution_mode="execute",
            selected_agents=[
                "requirement_analyst",
                "competitive_analyst",
                "market_researcher",
                "supervisor",
            ],
            agent_models={
                "requirement_analyst": "deepseek",
                "competitive_analyst": "kimi",
                "market_researcher": "deepseek",
                "supervisor": "claude",
            },
        )
    )

    service.enqueue_task(created.task_id)
    finished = service.run_task(created.task_id)
    artifacts = database.list_task_artifacts(created.task_id)

    assert finished.status is TaskStatus.PASSED
    assert calls == [
        "requirement_analyst",
        "market_researcher",
        "competitive_analyst",
        "supervisor",
    ]
    assert [
        item.artifact_type for item in artifacts
    ] == ["specialist_output", "specialist_output"]
    assert finished.selected_agents[-1] == "supervisor"


def test_specialist_runtime_uses_only_template_relevant_upstream_context() -> None:
    catalog = AgentCatalogService()
    adapter = CapturingAPIAdapter()
    runtime = ConfigurableRoleRuntime(
        catalog.template("bom_cost_engineer"),
        AgentModel.KIMI,
        api_adapter=adapter,
    )

    result = runtime.run(
        RuntimeRequest(
            task_id="task-1",
            project_name="硬件产品",
            workspace_path="/tmp/project",
            goal="成本评估",
            requirements=["目标成本待确认"],
            previous_outputs={
                "product_strategist": "产品定义",
                "hardware_architect": "系统架构",
                "market_researcher": "不相关的超长市场过程",
            },
        )
    )

    assert result.status is RuntimeStatus.COMPLETED
    assert "产品定义" in adapter.prompts[0]
    assert "系统架构" in adapter.prompts[0]
    assert "不相关的超长市场过程" not in adapter.prompts[0]
    assert result.evidence["usage"]["total_tokens"] == 100


def test_workflow_can_repeat_role_with_different_models_in_exact_order(
    tmp_path,
) -> None:
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    calls: list[str] = []
    catalog = AgentCatalogService()

    def resolver(role_id: str, model_id: str) -> AgentRuntime:
        output = (
            '{"ready_for_planning":true}'
            if role_id == "requirement_analyst"
            else (
                '{"ready_for_development":true}'
                if role_id == "supervisor"
                else f"{role_id}-{model_id}-output"
            )
        )

        class ModelTrackingRuntime(AgentRuntime):
            agent_name = role_id

            def run(self, request: RuntimeRequest) -> RuntimeResult:
                calls.append(f"{role_id}:{model_id}")
                return RuntimeResult(
                    agent_name=role_id,
                    status=RuntimeStatus.COMPLETED,
                    output=output,
                )

        return ModelTrackingRuntime()

    service = TaskService(
        database,
        CrewService(
            database,
            resolver("supervisor", "claude"),
            TrackingRuntime("developer", [], "unused"),
            TrackingRuntime("reviewer", [], "unused"),
            requirement_analyst_runtime=resolver(
                "requirement_analyst", "deepseek"
            ),
            runtime_resolver=resolver,
            agent_catalog_service=catalog,
        ),
        catalog,
    )
    workflow = [
        WorkflowStep(
            step_id="requirements",
            role_id="requirement_analyst",
            model_id="deepseek",
            order=0,
        ),
        WorkflowStep(
            step_id="market-first",
            role_id="market_researcher",
            model_id="deepseek",
            order=1,
        ),
        WorkflowStep(
            step_id="market-challenge",
            role_id="market_researcher",
            model_id="kimi",
            order=2,
        ),
        WorkflowStep(
            step_id="supervision",
            role_id="supervisor",
            model_id="claude",
            order=3,
        ),
    ]
    created = service.create_task(
        TaskCreate(
            project_name="重复角色链",
            workspace_path="/tmp/repeated-role-chain",
            goal="先研究再反向质疑",
            requirements=["两轮市场分析必须顺序执行"],
            execution_mode="execute",
            workflow_steps=workflow,
        )
    )

    service.enqueue_task(created.task_id)
    finished = service.run_task(created.task_id)
    artifacts = [
        item
        for item in database.list_task_artifacts(created.task_id)
        if item.artifact_type == "specialist_output"
    ]

    assert finished.status is TaskStatus.PASSED
    assert [
        (step.step_id, step.role_id, step.model_id)
        for step in finished.workflow_steps
    ] == [
        ("requirements", "requirement_analyst", "deepseek"),
        ("market-first", "market_researcher", "deepseek"),
        ("market-challenge", "market_researcher", "kimi"),
        ("supervision", "supervisor", "claude"),
    ]
    assert calls == [
        "requirement_analyst:deepseek",
        "market_researcher:deepseek",
        "market_researcher:kimi",
        "supervisor:claude",
    ]
    assert [
        __import__("json").loads(item.content)["step_id"]
        for item in artifacts
    ] == ["market-first", "market-challenge"]


def test_workflow_rejects_duplicate_step_and_broken_delivery_order() -> None:
    catalog = AgentCatalogService()
    repeated_id = [
        WorkflowStep(
            step_id="same",
            role_id="requirement_analyst",
            model_id="deepseek",
            order=0,
        ),
        WorkflowStep(
            step_id="same",
            role_id="supervisor",
            model_id="claude",
            order=1,
        ),
    ]
    try:
        catalog.validate_workflow(repeated_id)
    except ValueError as exc:
        assert "步骤编号不能重复" in str(exc)
    else:
        raise AssertionError("duplicate workflow step must be rejected")

    broken_delivery = [
        WorkflowStep(
            step_id="requirements",
            role_id="requirement_analyst",
            model_id="deepseek",
            order=0,
        ),
        WorkflowStep(
            step_id="supervisor",
            role_id="supervisor",
            model_id="claude",
            order=1,
        ),
        WorkflowStep(
            step_id="reviewer",
            role_id="reviewer",
            model_id="deepseek",
            order=2,
        ),
    ]
    try:
        catalog.validate_workflow(broken_delivery)
    except ValueError as exc:
        assert "开发交付链必须严格保持" in str(exc)
    else:
        raise AssertionError("broken delivery suffix must be rejected")
