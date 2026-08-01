from types import SimpleNamespace

from backend.adapters.codex_cli_adapter import (
    CodexExecutionResult,
    CodexExecutionStatus,
)
from backend.adapters.claude_code_adapter import (
    ClaudeAgentResult,
    ClaudeAgentStatus,
    ClaudeReviewResult,
    ClaudeReviewStatus,
)
from backend.adapters.kimi_api_adapter import (
    KimiVerificationResult,
    KimiVerificationStatus,
)
from backend.runtime.agent_runtime import AgentRuntime, RuntimeRequest, RuntimeStatus
from backend.runtime.developer_runtime import DeveloperRuntime
from backend.runtime.requirement_analyst_runtime import (
    RequirementAnalystRuntime,
)
from backend.runtime.reviewer_runtime import ReviewerRuntime
from backend.runtime.supervisor_runtime import SupervisorRuntime
from backend.runtime.supervisor_runtime import DecisionAction, SupervisorDecisionRequest
from backend.runtime.verification_runtime import VerificationRuntime


class FakeAgent:
    def __init__(self, output: str) -> None:
        self.output = output
        self.messages: list[str] = []

    def kickoff(self, message: str) -> SimpleNamespace:
        self.messages.append(message)
        return SimpleNamespace(raw=self.output)


def request() -> RuntimeRequest:
    return RuntimeRequest(
        task_id="task-001",
        project_name="产品知识系统",
        workspace_path="/tmp/project",
        goal="实现 Knowledge API",
        requirements=["统一入口"],
        previous_outputs={
            "supervisor": "任务规划",
            "developer": "开发结果",
        },
    )


def test_runtime_classes_implement_common_interface() -> None:
    assert issubclass(SupervisorRuntime, AgentRuntime)
    assert issubclass(DeveloperRuntime, AgentRuntime)
    assert issubclass(ReviewerRuntime, AgentRuntime)
    assert issubclass(RequirementAnalystRuntime, AgentRuntime)
    assert issubclass(VerificationRuntime, AgentRuntime)


def test_requirement_analyst_requires_structured_ready_output() -> None:
    ready = RequirementAnalystRuntime(
        lambda: FakeAgent('{"ready_for_planning": true}')
    ).run(request())
    blocked = RequirementAnalystRuntime(
        lambda: FakeAgent(
            '{"ready_for_planning": false, "ambiguities": ["缺少范围"]}'
        )
    ).run(request())

    assert ready.status is RuntimeStatus.COMPLETED
    assert blocked.status is RuntimeStatus.REQUIREMENTS_REVISION
    assert blocked.error == "Requirements must return to requirement revision"


def test_verification_runtime_generates_independent_report(tmp_path) -> None:
    import json
    import subprocess

    workspace = tmp_path / "project"
    workspace.mkdir()
    subprocess.run(
        ["git", "init", str(workspace)],
        check=True,
        capture_output=True,
    )
    runtime_request = request().model_copy(
        update={
            "workspace_path": str(workspace),
            "previous_outputs": {
                "supervisor": '{"required_tests": []}',
                "developer": json.dumps(
                    {
                        "evidence": {
                            "git_commit": "abc123",
                            "changed_files": ["app.py"],
                        }
                    }
                ),
            },
        }
    )

    result = VerificationRuntime().run(runtime_request)
    report = json.loads(result.output)

    assert result.status is RuntimeStatus.COMPLETED
    assert report["verification_result"] == "PASS"
    assert report["git_commit"] == "abc123"
    assert report["workspace_status_before"] == ""
    assert report["workspace_status_after"] == ""


def test_supervisor_and_developer_use_injected_agents() -> None:
    supervisor = SupervisorRuntime(
        lambda: FakeAgent(
            '{"task_id":"task-1","ready_for_development":true}'
        )
    ).run(request())
    developer = DeveloperRuntime(
        lambda: FakeAgent("开发完成"), execution_mode="mock"
    ).run(request())

    assert supervisor.status is RuntimeStatus.COMPLETED
    assert '"ready_for_development":true' in supervisor.output
    assert developer.status is RuntimeStatus.COMPLETED
    assert developer.output == "开发完成"


def test_supervisor_returns_oversized_scope_to_requirements() -> None:
    result = SupervisorRuntime(
        lambda: FakeAgent(
            '{"task_id":"task-001","ready_for_development":false,'
            '"blockers":["范围过大，需要拆分为两个独立任务"]}'
        )
    ).run(request())

    assert result.status is RuntimeStatus.REQUIREMENTS_REVISION
    assert "returned task to requirements" in (result.error or "")


def test_supervisor_uses_claude_for_plan_and_decision() -> None:
    class FakeClaudeAdapter:
        def __init__(self) -> None:
            self.requests = []
            self.outputs = [
                '{"ready_for_development": true, "required_tests": []}',
                "DEVELOPER_TASK: 修复失败测试\nFINAL_ACTION: REWORK",
            ]

        def execute_readonly(self, claude_request):
            self.requests.append(claude_request)
            output = self.outputs.pop(0)
            return ClaudeAgentResult(
                status=ClaudeAgentStatus.COMPLETED,
                output=output,
                raw_output=output,
                exit_code=0,
            )

    adapter = FakeClaudeAdapter()
    runtime = SupervisorRuntime(
        plan_mode="claude",
        claude_adapter=adapter,  # type: ignore[arg-type]
    )

    plan = runtime.run(request())
    decision = runtime.decision(
        SupervisorDecisionRequest(
            task={
                "task_id": "task-001",
                "workspace_path": "/tmp/project",
            },
            review_result="FAIL\n测试失败",
            developer_evidence={},
            iteration=1,
        )
    )

    assert plan.status is RuntimeStatus.COMPLETED
    assert decision.action is DecisionAction.REWORK
    assert len(adapter.requests) == 2
    assert "只负责规划和管理" in adapter.requests[0].prompt
    assert "不得自行验收" in adapter.requests[1].prompt


def test_supervisor_empty_output_is_failed() -> None:
    result = SupervisorRuntime(lambda: FakeAgent("   ")).run(request())

    assert result.status is RuntimeStatus.FAILED
    assert result.output == ""
    assert result.error == "Agent returned empty output"


def test_reviewer_normalizes_supported_verdict() -> None:
    result = ReviewerRuntime(
        lambda: FakeAgent("验收报告\n发现 FAIL 原因，但最终建议 PASS\nFINAL_RESULT: PASS"),
        review_mode="mock",
    ).run(request())

    assert result.status is RuntimeStatus.COMPLETED
    assert result.output.startswith("PASS\n")


def test_reviewer_defaults_to_deepseek_independent_of_claude_flag(
    monkeypatch,
) -> None:
    monkeypatch.setenv("CLAUDE_ENABLED", "true")
    monkeypatch.delenv("REVIEWER_MODE", raising=False)
    runtime = ReviewerRuntime(
        lambda: FakeAgent("FINAL_RESULT: PASS")
    )

    result = runtime.run(request())

    assert runtime.review_mode == "deepseek"
    assert result.status is RuntimeStatus.COMPLETED


def test_deepseek_reviewer_prompt_excludes_codex_process_chatter() -> None:
    import json

    agent = FakeAgent("FINAL_RESULT: PASS")
    runtime_request = request().model_copy(
        update={
            "previous_outputs": {
                "supervisor": '{"acceptance_criteria":["tests pass"]}',
                "developer": json.dumps(
                    {
                        "execution": {
                            "output": "VERBOSE_CODEX_CHATTER"
                        },
                        "evidence": {
                            "git_diff": "+change",
                            "changed_files": ["app.py"],
                            "git_commit": "abc123",
                        },
                    }
                ),
                "verification_engineer": (
                    '{"verification_result":"PASS","test_results":[]}'
                ),
            }
        }
    )

    result = ReviewerRuntime(
        lambda: agent, review_mode="deepseek"
    ).run(runtime_request)

    assert result.status is RuntimeStatus.COMPLETED
    assert "+change" in agent.messages[0]
    assert "VERBOSE_CODEX_CHATTER" not in agent.messages[0]


def test_reviewer_returns_blocked_when_verdict_cannot_be_parsed() -> None:
    result = ReviewerRuntime(
        lambda: FakeAgent("验收内容没有明确结论"),
        review_mode="mock",
    ).run(request())

    assert result.status is RuntimeStatus.BLOCKED
    assert result.output.startswith("BLOCKED\n")


def test_reviewer_empty_output_is_failed() -> None:
    result = ReviewerRuntime(
        lambda: FakeAgent(""), review_mode="mock"
    ).run(request())

    assert result.status is RuntimeStatus.FAILED
    assert result.error == "Agent returned empty output"


def test_developer_runtime_switches_to_codex_mode(tmp_path) -> None:
    class FakeCodexAdapter:
        def __init__(self) -> None:
            self.requests = []

        def execute(self, execution_request):
            self.requests.append(execution_request)
            return CodexExecutionResult(
                status=CodexExecutionStatus.COMPLETED,
                output="代码修改完成",
                changed_files=["src/api.py"],
                commands=[["codex", "exec"]],
            )

    adapter = FakeCodexAdapter()
    workspace = tmp_path / "project"
    workspace.mkdir()
    import subprocess

    subprocess.run(
        ["git", "init", str(workspace)],
        check=True,
        capture_output=True,
    )
    runtime_request = request().model_copy(
        update={"workspace_path": str(workspace)}
    )
    result = DeveloperRuntime(
        execution_mode="codex",
        codex_adapter=adapter,  # type: ignore[arg-type]
    ).run(runtime_request)

    assert result.status is RuntimeStatus.COMPLETED
    assert '"changed_files": [' in result.output
    assert result.evidence is not None
    assert adapter.requests[0].acceptance_criteria == "任务规划"


def test_reviewer_runtime_switches_to_claude_mode() -> None:
    class FakeClaudeAdapter:
        def __init__(self) -> None:
            self.requests = []

        def review(self, review_request):
            self.requests.append(review_request)
            return ClaudeReviewResult(
                status=ClaudeReviewStatus.PASS,
                output="PASS\n\n验收通过",
                raw_output="FINAL_RESULT: PASS",
                exit_code=0,
            )

    adapter = FakeClaudeAdapter()
    runtime_request = request().model_copy(
        update={
            "previous_outputs": {
                "supervisor": "验收标准",
                "developer": (
                    '{"evidence":{"git_diff":"+changed",'
                    '"test_results":[{"exit_code":0}]}}'
                ),
            }
        }
    )
    result = ReviewerRuntime(
        review_mode="claude",
        claude_adapter=adapter,  # type: ignore[arg-type]
    ).run(runtime_request)

    assert result.status is RuntimeStatus.COMPLETED
    assert result.output.startswith("PASS")
    assert adapter.requests[0].acceptance_criteria == "验收标准"
    assert adapter.requests[0].git_diff == "+changed"
    assert adapter.requests[0].test_results == [{"exit_code": 0}]


def test_verification_runtime_uses_claude_after_independent_tests(
    tmp_path,
) -> None:
    import json
    import subprocess

    class FakeClaudeAdapter:
        def __init__(self) -> None:
            self.requests = []

        def execute_readonly(self, claude_request):
            self.requests.append(claude_request)
            output = json.dumps(
                {
                    "verification_result": "PASS",
                    "blocking_issues": [],
                    "warnings": ["建议清理缓存"],
                    "assessment": "代码与测试证据一致",
                }
            )
            return ClaudeAgentResult(
                status=ClaudeAgentStatus.COMPLETED,
                output=output,
                raw_output=output,
                exit_code=0,
            )

    workspace = tmp_path / "project"
    workspace.mkdir()
    subprocess.run(
        ["git", "init", str(workspace)],
        check=True,
        capture_output=True,
    )
    adapter = FakeClaudeAdapter()
    runtime_request = request().model_copy(
        update={
            "workspace_path": str(workspace),
            "previous_outputs": {
                "supervisor": '{"required_tests": []}',
                "developer": json.dumps(
                    {"evidence": {"changed_files": ["app.py"]}}
                ),
            },
        }
    )

    result = VerificationRuntime(
        verification_mode="claude",
        claude_adapter=adapter,  # type: ignore[arg-type]
    ).run(runtime_request)
    report = json.loads(result.output)

    assert result.status is RuntimeStatus.COMPLETED
    assert report["verification_result"] == "PASS"
    assert report["model_assessment"] == "代码与测试证据一致"
    assert report["verification_provider"] == "claude"
    assert report["issues"] == []
    assert report["warnings"] == ["建议清理缓存"]
    assert "deterministic_report" in adapter.requests[0].prompt


def test_verification_runtime_switches_to_kimi(tmp_path) -> None:
    import json
    import subprocess

    class FakeKimiAdapter:
        def __init__(self) -> None:
            self.requests = []

        def verify(self, kimi_request):
            self.requests.append(kimi_request)
            return KimiVerificationResult(
                status=KimiVerificationStatus.COMPLETED,
                output=json.dumps(
                    {
                        "verification_result": "PASS",
                        "blocking_issues": [],
                        "warnings": [],
                        "assessment": "Kimi核验通过",
                    }
                ),
                model="kimi-k3",
                usage={"total_tokens": 200},
            )

    workspace = tmp_path / "project"
    workspace.mkdir()
    subprocess.run(
        ["git", "init", str(workspace)],
        check=True,
        capture_output=True,
    )
    adapter = FakeKimiAdapter()
    runtime_request = request().model_copy(
        update={
            "workspace_path": str(workspace),
            "previous_outputs": {
                "supervisor": '{"required_tests": []}',
                "developer": json.dumps(
                    {"evidence": {"changed_files": ["app.py"]}}
                ),
            },
        }
    )

    result = VerificationRuntime(
        verification_mode="kimi",
        kimi_adapter=adapter,  # type: ignore[arg-type]
    ).run(runtime_request)
    report = json.loads(result.output)

    assert result.status is RuntimeStatus.COMPLETED
    assert report["verification_result"] == "PASS"
    assert report["verification_provider"] == "kimi"
    assert report["verification_model"] == "kimi-k3"
    assert report["model_assessment"] == "Kimi核验通过"
    assert report["model_usage"]["total_tokens"] == 200
    assert "Developer Evidence" in adapter.requests[0].prompt


def test_supervisor_decision_parses_rework_task() -> None:
    runtime = SupervisorRuntime(
        lambda: FakeAgent(
            "DEVELOPER_TASK: 修复失败测试\nFINAL_ACTION: REWORK"
        )
    )

    result = runtime.decision(
        SupervisorDecisionRequest(
            task={"task_id": "task-001"},
            review_result="FAIL\n测试失败",
            developer_evidence={"git_diff": "+changed"},
            iteration=1,
        )
    )

    assert result.action is DecisionAction.REWORK
    assert result.developer_task == "修复失败测试"
