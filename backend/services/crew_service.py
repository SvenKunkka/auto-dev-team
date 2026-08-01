from __future__ import annotations

import json

from backend.database.sqlite import SQLiteDatabase
from backend.database.sqlite import utc_now
from backend.models.agent import AgentKind, WorkflowStep
from backend.models.task import ExecutionMode, TaskRecord, TaskStatus
from backend.runtime.agent_runtime_factory import RuntimeResolver
from backend.services.agent_catalog_service import AgentCatalogService
from backend.observability.logger import EventType, StructuredLogger
from backend.reliability.workspace_lock_manager import WorkspaceLockManager
from backend.reliability.task_workspace_manager import (
    TaskWorkspaceContext,
    TaskWorkspaceManager,
)
from backend.runtime.agent_runtime import (
    AgentRuntime,
    RuntimeRequest,
    RuntimeResult,
    RuntimeStatus,
)
from backend.runtime.role_context_builder import RoleContextBuilder
from backend.runtime.supervisor_runtime import (
    DecisionAction,
    DecisionResult,
    SupervisorDecisionRequest,
)
from backend.safety.workspace_validator import WorkspaceValidator


class _CompatibilityRuntime(AgentRuntime):
    """Keep direct service construction deterministic outside create_app."""

    def __init__(self, agent_name: str, output: str) -> None:
        self.agent_name = agent_name
        self.output = output

    def run(self, request: RuntimeRequest) -> RuntimeResult:
        return RuntimeResult(
            agent_name=self.agent_name,
            status=RuntimeStatus.COMPLETED,
            output=self.output,
        )


class CrewService:
    """通过Runtime接口编排五角色线性生命周期。"""

    def __init__(
        self,
        database: SQLiteDatabase,
        supervisor_runtime: AgentRuntime,
        developer_runtime: AgentRuntime,
        reviewer_runtime: AgentRuntime,
        workspace_lock_manager: WorkspaceLockManager | None = None,
        workspace_validator: WorkspaceValidator | None = None,
        task_workspace_manager: TaskWorkspaceManager | None = None,
        *,
        requirement_analyst_runtime: AgentRuntime | None = None,
        verification_runtime: AgentRuntime | None = None,
        runtime_resolver: RuntimeResolver | None = None,
        agent_catalog_service: AgentCatalogService | None = None,
    ) -> None:
        self.database = database
        self.requirement_analyst_runtime = (
            requirement_analyst_runtime
            or _CompatibilityRuntime(
                "requirement_analyst",
                json.dumps(
                    {
                        "ready_for_planning": True,
                        "source": "compatibility",
                    }
                ),
            )
        )
        self.supervisor_runtime = supervisor_runtime
        self.developer_runtime = developer_runtime
        self.verification_runtime = (
            verification_runtime
            or _CompatibilityRuntime(
                "verification_engineer",
                json.dumps({"verification_result": "PASS"}),
            )
        )
        self.reviewer_runtime = reviewer_runtime
        self.workspace_lock_manager = (
            workspace_lock_manager or WorkspaceLockManager(database)
        )
        self.logger = StructuredLogger(database)
        self.workspace_validator = workspace_validator or WorkspaceValidator()
        self.task_workspace_manager = (
            task_workspace_manager or TaskWorkspaceManager()
        )
        self.runtime_resolver = runtime_resolver
        self.agent_catalog_service = (
            agent_catalog_service or AgentCatalogService()
        )

    def run_task(self, task_id: str) -> TaskRecord:
        task = self.database.get_task(task_id)
        if task is None:
            raise KeyError(f"任务不存在：{task_id}")
        lock = self.workspace_lock_manager.acquire(
            workspace_path=task.workspace_path,
            task_id=task_id,
        )
        if lock is None:
            return self.database.update_task(
                task_id, status=TaskStatus.QUEUED
            )

        try:
            self.logger.log(
                task_id=task_id,
                event_type=EventType.TASK_STARTED,
                message="Task execution started",
            )
            running = self.database.transition_task_status(
                task_id,
                status=TaskStatus.RUNNING,
                allowed_from={TaskStatus.CREATED, TaskStatus.QUEUED},
                started_at=(
                    task.started_at.isoformat()
                    if task.started_at is not None
                    else utc_now()
                ),
            )
            if running.status is not TaskStatus.RUNNING:
                return running
            try:
                result = self._run_lifecycle(task_id)
                result = self._finalize_task_workspace(result)
                if result.status is not TaskStatus.PAUSED:
                    self.logger.log(
                        task_id=task_id,
                        event_type=EventType.TASK_FINISHED,
                        message=f"Task finished with {result.status.value}",
                    )
                return result
            except KeyError:
                raise
            except Exception as exc:
                self._preserve_task_workspace(task_id)
                try:
                    self.logger.log(
                        task_id=task_id,
                        event_type=EventType.ERROR,
                        level="ERROR",
                        message=f"Lifecycle failed: {exc}",
                    )
                except Exception:
                    pass
                # A transient persistence failure must not leave a task in an
                # in-progress state. Persistent SQLite failure is surfaced.
                controlled = self._human_control_state(task_id)
                if controlled is not None:
                    return controlled
                return self.database.update_task(
                    task_id, status=TaskStatus.FAILED
                )
        finally:
            self.workspace_lock_manager.release(task_id=task_id)

    def _run_lifecycle(self, task_id: str) -> TaskRecord:
        task = self.database.get_task(task_id)
        if task is None:
            raise KeyError(f"任务不存在：{task_id}")

        resume_stage = task.resume_stage
        if (
            self._stage_at_or_before(resume_stage, TaskStatus.ANALYZING)
            or not task.requirements_output
        ):
            analyzing = self.database.transition_task_status(
                task_id,
                status=TaskStatus.ANALYZING,
                allowed_from={TaskStatus.RUNNING},
            )
            if analyzing.status is not TaskStatus.ANALYZING:
                return analyzing
            self.database.update_task(
                task_id, active_agent="requirement_analyst"
            )
            self.logger.log(
                task_id=task_id,
                event_type=EventType.REQUIREMENT_ANALYSIS_STARTED,
                agent_name="requirement_analyst",
                message="Requirement analysis started",
            )
            analyst_request = self._request(
                task, {}, include_documents=True
            )
            analyst_runtime = self._runtime_for(
                task,
                "requirement_analyst",
                self.requirement_analyst_runtime,
            )
            analyst_result = self._run_runtime(
                analyst_runtime, analyst_request
            )
            self._save_run(task_id, analyst_request, analyst_result)
            self.logger.log(
                task_id=task_id,
                event_type=EventType.REQUIREMENT_ANALYSIS_FINISHED,
                agent_name="requirement_analyst",
                message=(
                    "Requirement analysis finished with "
                    f"{analyst_result.status.value}"
                ),
            )
            if analyst_result.status is not RuntimeStatus.COMPLETED:
                self._log_runtime_error(task_id, analyst_result)
            controlled = self._human_control_state(task_id)
            if controlled is not None:
                return controlled
            analyst_output = self._result_text(analyst_result)
            if analyst_result.status is not RuntimeStatus.COMPLETED:
                if (
                    analyst_result.status
                    is RuntimeStatus.REQUIREMENTS_REVISION
                ):
                    self.logger.log(
                        task_id=task_id,
                        event_type=EventType.REQUIREMENTS_REVISION_REQUIRED,
                        agent_name="requirement_analyst",
                        message=(
                            "Requirement analysis requested clarification or "
                            "scope decomposition"
                        ),
                    )
                    return self.database.update_task(
                        task_id,
                        status=TaskStatus.REQUIREMENTS_REVISION,
                        resume_stage=TaskStatus.ANALYZING,
                        requirements_output=analyst_output,
                        blocked_reason=analyst_output,
                        required_action=(
                            "Clarify or split the requirement into ordered, "
                            "independently acceptable tasks, then retry"
                        ),
                    )
                failure_status = self._runtime_failure_status(analyst_result)
                return self.database.update_task(
                    task_id,
                    status=failure_status,
                    resume_stage=TaskStatus.ANALYZING,
                    requirements_output=analyst_output,
                    **self._blocked_details(
                        failure_status,
                        analyst_output,
                        "Clarify requirements and retry",
                    ),
                )
            has_specialists = bool(self._specialist_steps(task))
            next_stage = (
                TaskStatus.RESEARCHING
                if has_specialists
                else TaskStatus.PLANNING
            )
            self.database.update_task(
                task_id,
                requirements_output=analyst_result.output,
                resume_stage=next_stage,
            )
            resume_stage = next_stage
        else:
            analyst_result = self._persisted_result(
                "requirement_analyst", task.requirements_output
            )

        specialist_outputs, terminal = self._run_specialists(
            task=task,
            resume_stage=resume_stage,
            analyst_output=analyst_result.output,
        )
        if terminal is not None:
            return terminal
        if specialist_outputs:
            resume_stage = TaskStatus.PLANNING

        if (
            self._stage_at_or_before(resume_stage, TaskStatus.PLANNING)
            or not task.supervisor_output
        ):
            planning = self.database.transition_task_status(
                task_id,
                status=TaskStatus.PLANNING,
                allowed_from={
                    TaskStatus.ANALYZING,
                    TaskStatus.RESEARCHING,
                    TaskStatus.RUNNING,
                },
            )
            if planning.status is not TaskStatus.PLANNING:
                return planning
            self.database.update_task(
                task_id, active_agent="supervisor"
            )
            self.logger.log(
                task_id=task_id,
                event_type=EventType.SUPERVISOR_STARTED,
                agent_name="supervisor",
                message="Supervisor planning started",
            )
            supervisor_context = {
                "requirement_analyst": analyst_result.output,
                **specialist_outputs,
            }
            supervisor_request = self._request(task, supervisor_context)
            supervisor_runtime = self._runtime_for(
                task, "supervisor", self.supervisor_runtime
            )
            supervisor_result = self._run_runtime(
                supervisor_runtime, supervisor_request
            )
            self._save_run(task_id, supervisor_request, supervisor_result)
            self.logger.log(
                task_id=task_id,
                event_type=EventType.SUPERVISOR_FINISHED,
                agent_name="supervisor",
                message=(
                    "Supervisor finished with "
                    f"{supervisor_result.status.value}"
                ),
            )
            if supervisor_result.status is not RuntimeStatus.COMPLETED:
                self._log_runtime_error(task_id, supervisor_result)
            controlled = self._human_control_state(task_id)
            if controlled is not None:
                return controlled
            if supervisor_result.status is not RuntimeStatus.COMPLETED:
                if (
                    supervisor_result.status
                    is RuntimeStatus.REQUIREMENTS_REVISION
                ):
                    self.logger.log(
                        task_id=task_id,
                        event_type=EventType.REQUIREMENTS_REVISION_REQUIRED,
                        agent_name="supervisor",
                        message=(
                            "Scope gate returned the task to requirement "
                            "analysis"
                        ),
                    )
                    return self.database.update_task(
                        task_id,
                        status=TaskStatus.REQUIREMENTS_REVISION,
                        resume_stage=TaskStatus.ANALYZING,
                        supervisor_output=self._result_text(
                            supervisor_result
                        ),
                        blocked_reason=(
                            "Supervisor determined that the requirement is too "
                            "large or insufficiently defined for one safe "
                            "delivery"
                        ),
                        required_action=(
                            "Return to requirement analysis, split the scope "
                            "into ordered independently acceptable tasks, then "
                            "retry"
                        ),
                    )
                failure_status = self._runtime_failure_status(
                    supervisor_result
                )
                return self.database.update_task(
                    task_id,
                    status=failure_status,
                    resume_stage=TaskStatus.PLANNING,
                    supervisor_output=self._result_text(supervisor_result),
                    **self._blocked_details(
                        failure_status,
                        self._result_text(supervisor_result),
                        "Resolve Supervisor blocker and retry",
                    ),
                )
            self.database.update_task(
                task_id,
                supervisor_output=supervisor_result.output,
                resume_stage=TaskStatus.DEVELOPING,
            )
            resume_stage = TaskStatus.DEVELOPING
        else:
            supervisor_result = self._persisted_result(
                "supervisor", task.supervisor_output
            )
        original_plan = supervisor_result.output
        current_supervisor_output = original_plan
        if (
            task.execution_mode is ExecutionMode.DRY_RUN
            or "developer" not in task.selected_agents
        ):
            return self.database.update_task(
                task_id,
                status=TaskStatus.PASSED,
                active_agent="completed",
            )

        execution_task = task
        developer_runtime = self._runtime_for(
            task, "developer", self.developer_runtime
        )
        codex_mode = (
            getattr(developer_runtime, "execution_mode", None)
            == "codex"
        )
        if codex_mode:
            base_validation = self.workspace_validator.validate(
                task.workspace_path
            )
            self.database.create_task_artifact(
                task_id=task_id,
                artifact_type="workspace_validation",
                content=base_validation.model_dump_json(),
            )
            if not base_validation.valid:
                return self.database.update_task(
                    task_id,
                    status=TaskStatus.BLOCKED,
                    blocked_reason=(
                        base_validation.error
                        or "Delivery workspace validation failed"
                    ),
                    required_action=(
                        "Provide an existing clean Git repository workspace"
                    ),
                )
            prepared = self._prepare_task_workspace(task)
            if not prepared.success or prepared.context is None:
                reason = prepared.error or "Task workspace preparation failed"
                self.logger.log(
                    task_id=task_id,
                    event_type=EventType.ERROR,
                    agent_name="developer",
                    level="ERROR",
                    message=reason,
                )
                return self.database.update_task(
                    task_id,
                    status=TaskStatus.BLOCKED,
                    blocked_reason=reason,
                    required_action=(
                        "Clean the delivery workspace or repair the task "
                        "worktree, then retry"
                    ),
                )
            execution_task = task.model_copy(
                update={"workspace_path": prepared.context.worktree_path}
            )

        retry_count = task.retry_count
        existing_iterations = self.database.list_task_iterations(task_id)
        iteration = max(
            [
                retry_count + 1,
                *(item.iteration + 1 for item in existing_iterations),
            ]
        )
        while True:
            previous_outputs = {
                "requirement_analyst": analyst_result.output,
                "supervisor": current_supervisor_output,
            }
            reuse_developer = (
                not self._stage_at_or_before(
                    resume_stage, TaskStatus.DEVELOPING
                )
                and bool(task.developer_output)
            )
            if reuse_developer:
                developer_result = self._persisted_developer_result(
                    task.developer_output or ""
                )
            else:
                developer_result, terminal = self._execute_developer_stage(
                    task_id=task_id,
                    execution_task=execution_task,
                    previous_outputs=previous_outputs,
                    codex_mode=codex_mode,
                    iteration=iteration,
                    supervisor_output=current_supervisor_output,
                    developer_runtime=developer_runtime,
                )
                if terminal is not None:
                    return terminal
                self.database.update_task(
                    task_id,
                    developer_output=developer_result.output,
                    resume_stage=TaskStatus.VERIFYING,
                )
                resume_stage = TaskStatus.VERIFYING
            previous_outputs["developer"] = developer_result.output

            reuse_verification = (
                not self._stage_at_or_before(
                    resume_stage, TaskStatus.VERIFYING
                )
                and bool(task.verification_output)
            )
            if reuse_verification:
                verification_result = self._persisted_result(
                    "verification_engineer",
                    task.verification_output or "",
                )
                verification_output = verification_result.output
            else:
                (
                    verification_result,
                    verification_output,
                    terminal,
                ) = self._execute_verification_stage(
                    task_id=task_id,
                    execution_task=execution_task,
                    previous_outputs=previous_outputs,
                    iteration=iteration,
                    supervisor_output=current_supervisor_output,
                    developer_output=developer_result.output,
                    verification_runtime=self._runtime_for(
                        task,
                        "verification_engineer",
                        self.verification_runtime,
                    ),
                )
                if terminal is not None:
                    return terminal
                self.database.update_task(
                    task_id,
                    verification_output=verification_output,
                    resume_stage=TaskStatus.REVIEWING,
                )
                resume_stage = TaskStatus.REVIEWING
            previous_outputs["verification_engineer"] = (
                verification_result.output
            )

            reviewing = self.database.transition_task_status(
                task_id,
                status=TaskStatus.REVIEWING,
                allowed_from={TaskStatus.VERIFYING, TaskStatus.RUNNING},
            )
            if reviewing.status is not TaskStatus.REVIEWING:
                return reviewing
            self.database.update_task(
                task_id, active_agent="reviewer"
            )
            self.logger.log(
                task_id=task_id,
                event_type=EventType.REVIEW_STARTED,
                agent_name="reviewer",
                message=f"Review iteration {iteration} started",
            )
            reviewer_request = self._request(
                execution_task, previous_outputs
            )
            reviewer_result = self._run_runtime(
                self._runtime_for(
                    task, "reviewer", self.reviewer_runtime
                ),
                reviewer_request,
            )
            self._save_run(task_id, reviewer_request, reviewer_result)
            if reviewer_result.status is RuntimeStatus.FAILED:
                self._log_runtime_error(task_id, reviewer_result)
            controlled = self._human_control_state(task_id)
            if controlled is not None:
                return controlled
            reviewer_output = self._result_text(reviewer_result)
            review_status = self._review_status(reviewer_result)
            self._save_iteration(
                task_id,
                iteration=iteration,
                supervisor_output=current_supervisor_output,
                developer_output=developer_result.output,
                verification_output=verification_output,
                reviewer_output=reviewer_output,
                status=review_status,
            )
            current_task = self.database.transition_task_status(
                task_id,
                status=review_status,
                allowed_from={TaskStatus.REVIEWING},
            )
            if current_task.status is not review_status:
                return current_task
            current_task = self.database.update_task(
                task_id,
                reviewer_output=reviewer_output,
                resume_stage=TaskStatus.REVIEWING,
                **self._blocked_details(
                    review_status,
                    reviewer_output,
                    "Resolve Reviewer blocker and retry",
                ),
            )

            if review_status is TaskStatus.PASSED:
                return self.database.update_task(
                    task_id, active_agent="completed"
                )
            if (
                review_status is TaskStatus.BLOCKED
                or reviewer_result.status is RuntimeStatus.FAILED
            ):
                return current_task

            if retry_count >= task.max_retry:
                return self.database.update_task(
                    task_id,
                    status=TaskStatus.BLOCKED,
                    blocked_reason="Maximum retry count reached",
                    required_action="Review iterations and intervene manually",
                )

            decision_request = SupervisorDecisionRequest(
                task=task.model_dump(mode="json"),
                review_result=reviewer_output,
                developer_evidence=developer_result.evidence or {},
                iteration=iteration,
            )
            decision = self._run_decision(decision_request)
            self._save_decision_run(
                task_id, decision_request, decision
            )
            if decision.error:
                self.logger.log(
                    task_id=task_id,
                    event_type=EventType.ERROR,
                    agent_name="supervisor",
                    level="ERROR",
                    message=decision.error,
                )
            if decision.action is DecisionAction.BLOCKED:
                return self.database.update_task(
                    task_id,
                    status=TaskStatus.BLOCKED,
                    supervisor_output=decision.output or decision.error or "",
                    blocked_reason=decision.output
                    or decision.error
                    or "Supervisor blocked the task",
                    required_action="Resolve Supervisor required action",
                )
            if decision.action is DecisionAction.COMPLETE:
                # Supervisor may close the workflow, but cannot override a
                # Reviewer FAIL into a successful task.
                return self.database.update_task(
                    task_id,
                    status=TaskStatus.FAILED,
                    supervisor_output=decision.output,
                )

            retry_count += 1
            iteration += 1
            current_supervisor_output = self._rework_context(
                original_plan=original_plan,
                review_result=reviewer_output,
                decision=decision,
            )
            reworking = self.database.transition_task_status(
                task_id,
                status=TaskStatus.REWORKING,
                allowed_from={TaskStatus.FAILED},
            )
            if reworking.status is not TaskStatus.REWORKING:
                return reworking
            self.database.update_task(
                task_id,
                retry_count=retry_count,
                supervisor_output=current_supervisor_output,
                resume_stage=TaskStatus.DEVELOPING,
                active_agent="supervisor",
            )
            self.logger.log(
                task_id=task_id,
                event_type=EventType.REWORK_STARTED,
                agent_name="supervisor",
                message=f"Rework iteration {iteration} started",
            )
            resume_stage = TaskStatus.DEVELOPING

    def _run_specialists(
        self,
        *,
        task: TaskRecord,
        resume_stage: TaskStatus,
        analyst_output: str,
    ) -> tuple[dict[str, str], TaskRecord | None]:
        steps = self._specialist_steps(task)
        outputs, completed_steps = self._load_specialist_outputs(
            task.task_id
        )
        if not steps:
            return outputs, None
        if not self._stage_at_or_before(
            resume_stage, TaskStatus.RESEARCHING
        ):
            return outputs, None

        researching = self.database.transition_task_status(
            task.task_id,
            status=TaskStatus.RESEARCHING,
            allowed_from={TaskStatus.ANALYZING, TaskStatus.RUNNING},
        )
        if researching.status is not TaskStatus.RESEARCHING:
            return outputs, researching
        for step in steps:
            template = self.agent_catalog_service.template(step.role_id)
            if step.step_id in completed_steps:
                continue
            model_id = step.model_id
            self.database.update_task(
                task.task_id, active_agent=template.id
            )
            self.logger.log(
                task_id=task.task_id,
                event_type=EventType.SPECIALIST_STARTED,
                agent_name=template.id,
                message=f"{template.name} started with {model_id}",
            )
            request = self._request(
                task,
                {
                    "requirement_analyst": analyst_output,
                    **outputs,
                },
            )
            try:
                if self.runtime_resolver is None:
                    raise ValueError(
                        f"No runtime configured for role: {template.id}"
                    )
                runtime = self.runtime_resolver(template.id, model_id)
            except ValueError as exc:
                result = RuntimeResult(
                    agent_name=template.id,
                    status=RuntimeStatus.FAILED,
                    output="",
                    error=str(exc),
                )
            else:
                result = self._run_runtime(runtime, request)
            self._save_run(task.task_id, request, result)
            self.logger.log(
                task_id=task.task_id,
                event_type=EventType.SPECIALIST_FINISHED,
                agent_name=template.id,
                message=(
                    f"{template.name} finished with "
                    f"{result.status.value}"
                ),
            )
            if result.status is not RuntimeStatus.COMPLETED:
                self._log_runtime_error(task.task_id, result)
                status = self._runtime_failure_status(result)
                output = self._result_text(result)
                return outputs, self.database.update_task(
                    task.task_id,
                    status=status,
                    resume_stage=TaskStatus.RESEARCHING,
                    active_agent=template.id,
                    **self._blocked_details(
                        status,
                        output,
                        f"Resolve {template.name} blocker and retry",
                    ),
                )
            workflow_key = (
                f"workflow:{step.order}:{step.step_id}:{template.id}"
            )
            outputs[workflow_key] = result.output
            outputs[template.id] = result.output
            completed_steps.add(step.step_id)
            self.database.create_task_artifact(
                task_id=task.task_id,
                artifact_type="specialist_output",
                content=json.dumps(
                    {
                        "step_id": step.step_id,
                        "order": step.order,
                        "agent_id": template.id,
                        "agent_name": template.name,
                        "model": model_id,
                        "output": result.output,
                        "evidence": result.evidence or {},
                    },
                    ensure_ascii=False,
                ),
            )
            controlled = self._human_control_state(task.task_id)
            if controlled is not None:
                return outputs, controlled
        self.database.update_task(
            task.task_id,
            resume_stage=TaskStatus.PLANNING,
            active_agent="supervisor",
        )
        return outputs, None

    def _load_specialist_outputs(
        self, task_id: str
    ) -> tuple[dict[str, str], set[str]]:
        outputs: dict[str, str] = {}
        completed_steps: set[str] = set()
        for artifact in self.database.list_task_artifacts(task_id):
            if artifact.artifact_type != "specialist_output":
                continue
            try:
                content = json.loads(artifact.content)
            except (json.JSONDecodeError, TypeError):
                continue
            if (
                isinstance(content, dict)
                and content.get("agent_id")
                and isinstance(content.get("output"), str)
            ):
                role_id = str(content["agent_id"])
                step_id = str(content.get("step_id") or role_id)
                order = int(content.get("order") or 0)
                outputs[
                    f"workflow:{order}:{step_id}:{role_id}"
                ] = content["output"]
                outputs[role_id] = content["output"]
                completed_steps.add(step_id)
        return outputs, completed_steps

    def _workflow_steps(self, task: TaskRecord) -> list[WorkflowStep]:
        return self.agent_catalog_service.normalize_workflow(
            task.workflow_steps,
            task.selected_agents,
            task.agent_models,
        )

    def _specialist_steps(
        self, task: TaskRecord
    ) -> list[WorkflowStep]:
        return [
            step
            for step in self._workflow_steps(task)
            if self.agent_catalog_service.template(step.role_id).kind
            is AgentKind.SPECIALIST
        ]

    def _runtime_for(
        self,
        task: TaskRecord,
        role_id: str,
        fallback: AgentRuntime | None,
    ) -> AgentRuntime:
        if self.runtime_resolver is None:
            if fallback is None:
                raise ValueError(
                    f"No runtime configured for role: {role_id}"
                )
            return fallback
        template = self.agent_catalog_service.template(role_id)
        model_id = next(
            (
                step.model_id
                for step in self._workflow_steps(task)
                if step.role_id == role_id
            ),
            task.agent_models.get(role_id, template.default_model),
        )
        return self.runtime_resolver(role_id, model_id)

    def _execute_developer_stage(
        self,
        *,
        task_id: str,
        execution_task: TaskRecord,
        previous_outputs: dict[str, str],
        codex_mode: bool,
        iteration: int,
        supervisor_output: str,
        developer_runtime: AgentRuntime,
    ) -> tuple[RuntimeResult, TaskRecord | None]:
        developing = self.database.transition_task_status(
            task_id,
            status=TaskStatus.DEVELOPING,
            allowed_from={
                TaskStatus.PLANNING,
                TaskStatus.REWORKING,
                TaskStatus.RUNNING,
            },
        )
        if developing.status is not TaskStatus.DEVELOPING:
            return self._persisted_result("developer", ""), developing
        self.database.update_task(
            task_id, active_agent="developer"
        )
        developer_request = self._request(execution_task, previous_outputs)
        if codex_mode:
            validation = self.workspace_validator.validate(
                execution_task.workspace_path
            )
            self.database.create_task_artifact(
                task_id=task_id,
                artifact_type="workspace_validation",
                content=validation.model_dump_json(),
            )
            if not validation.valid:
                result = RuntimeResult(
                    agent_name="developer",
                    status=RuntimeStatus.BLOCKED,
                    output="",
                    error=validation.error,
                    evidence={
                        "workspace_validation": validation.model_dump(
                            mode="json"
                        )
                    },
                )
                self._save_run(task_id, developer_request, result)
                self._log_runtime_error(task_id, result)
                blocked_output = self._result_text(result)
                self._save_iteration(
                    task_id=task_id,
                    iteration=iteration,
                    supervisor_output=supervisor_output,
                    developer_output=blocked_output,
                    verification_output="",
                    reviewer_output="",
                    status=TaskStatus.BLOCKED,
                )
                terminal = self.database.update_task(
                    task_id,
                    status=TaskStatus.BLOCKED,
                    resume_stage=TaskStatus.DEVELOPING,
                    developer_output=blocked_output,
                    blocked_reason=blocked_output,
                    required_action=(
                        "Provide an existing Git repository workspace"
                    ),
                )
                return result, terminal
            self.logger.log(
                task_id=task_id,
                event_type=EventType.WORKSPACE_VALIDATED,
                agent_name="developer",
                message=(
                    f"Git workspace validated: {validation.workspace_path}"
                ),
            )
        self.logger.log(
            task_id=task_id,
            event_type=EventType.DEVELOPER_STARTED,
            agent_name="developer",
            message=f"Developer iteration {iteration} started",
        )
        if codex_mode:
            self.logger.log(
                task_id=task_id,
                event_type=EventType.CODE_CHANGE_STARTED,
                agent_name="developer",
                message=f"Code change iteration {iteration} started",
            )
            self.logger.log(
                task_id=task_id,
                event_type=EventType.CODEX_STARTED,
                agent_name="developer",
                message=f"Codex iteration {iteration} started",
            )
            self.logger.log(
                task_id=task_id,
                event_type=EventType.TEST_STARTED,
                agent_name="developer",
                message=(
                    "Evidence test collection scheduled for iteration "
                    f"{iteration}"
                ),
            )
        result = self._run_runtime(developer_runtime, developer_request)
        if codex_mode:
            self.logger.log(
                task_id=task_id,
                event_type=EventType.CODE_CHANGE_FINISHED,
                agent_name="developer",
                message=(
                    f"Code change iteration {iteration} finished with "
                    f"{result.status.value}"
                ),
            )
        self._save_run(task_id, developer_request, result)
        if result.status is not RuntimeStatus.COMPLETED:
            self._log_runtime_error(task_id, result)
        self._save_evidence(task_id, result)
        if result.evidence:
            commit_hash = result.evidence.get("git_commit")
            commit_error = result.evidence.get("git_commit_error")
            if commit_hash:
                self.logger.log(
                    task_id=task_id,
                    event_type=EventType.GIT_COMMIT_CREATED,
                    agent_name="developer",
                    message=f"Git commit created: {commit_hash}",
                )
            elif commit_error:
                self.logger.log(
                    task_id=task_id,
                    event_type=EventType.ERROR,
                    agent_name="developer",
                    level="ERROR",
                    message=f"Git commit failed: {commit_error}",
                )
        controlled = self._human_control_state(task_id)
        if controlled is not None:
            return result, controlled
        developer_output = self._result_text(result)
        if result.status is not RuntimeStatus.COMPLETED:
            failure_status = self._runtime_failure_status(result)
            self._save_iteration(
                task_id=task_id,
                iteration=iteration,
                supervisor_output=supervisor_output,
                developer_output=developer_output,
                verification_output="",
                reviewer_output="",
                status=failure_status,
            )
            terminal = self.database.update_task(
                task_id,
                status=failure_status,
                resume_stage=TaskStatus.DEVELOPING,
                developer_output=developer_output,
                **self._blocked_details(
                    failure_status,
                    developer_output,
                    "Resolve Developer blocker and retry",
                ),
            )
            return result, terminal
        return result, None

    def _execute_verification_stage(
        self,
        *,
        task_id: str,
        execution_task: TaskRecord,
        previous_outputs: dict[str, str],
        iteration: int,
        supervisor_output: str,
        developer_output: str,
        verification_runtime: AgentRuntime,
    ) -> tuple[RuntimeResult, str, TaskRecord | None]:
        verifying = self.database.transition_task_status(
            task_id,
            status=TaskStatus.VERIFYING,
            allowed_from={TaskStatus.DEVELOPING, TaskStatus.RUNNING},
        )
        if verifying.status is not TaskStatus.VERIFYING:
            result = self._persisted_result("verification_engineer", "")
            return result, "", verifying
        self.database.update_task(
            task_id, active_agent="verification_engineer"
        )
        self.logger.log(
            task_id=task_id,
            event_type=EventType.VERIFICATION_STARTED,
            agent_name="verification_engineer",
            message=f"Verification iteration {iteration} started",
        )
        request = self._request(execution_task, previous_outputs)
        result = self._run_runtime(verification_runtime, request)
        self._save_run(task_id, request, result)
        self.logger.log(
            task_id=task_id,
            event_type=EventType.VERIFICATION_FINISHED,
            agent_name="verification_engineer",
            message=(
                f"Verification iteration {iteration} finished with "
                f"{result.status.value}"
            ),
        )
        output = self._result_text(result)
        if result.evidence:
            report = result.evidence.get("verification_report")
            if report is not None:
                self.database.create_task_artifact(
                    task_id=task_id,
                    artifact_type="verification_report",
                    content=json.dumps(report, ensure_ascii=False),
                )
        if result.status is not RuntimeStatus.COMPLETED:
            self._log_runtime_error(task_id, result)
            failure_status = self._runtime_failure_status(result)
            self._save_iteration(
                task_id=task_id,
                iteration=iteration,
                supervisor_output=supervisor_output,
                developer_output=developer_output,
                verification_output=output,
                reviewer_output="",
                status=failure_status,
            )
            terminal = self.database.update_task(
                task_id,
                status=failure_status,
                resume_stage=TaskStatus.VERIFYING,
                verification_output=output,
                **self._blocked_details(
                    failure_status,
                    output,
                    "Resolve verification blocker and retry",
                ),
            )
            return result, output, terminal
        controlled = self._human_control_state(task_id)
        if controlled is not None:
            return result, output, controlled
        return result, output, None

    def _request(
        self,
        task: TaskRecord,
        previous_outputs: dict[str, str],
        *,
        include_documents: bool = False,
    ) -> RuntimeRequest:
        requirements = task.requirements.copy()
        artifacts = (
            self.database.list_task_artifacts(task.task_id)
            if include_documents
            else []
        )
        for artifact in artifacts:
            if artifact.artifact_type != "input_document":
                continue
            try:
                document = json.loads(artifact.content)
            except (TypeError, ValueError):
                continue
            filename = document.get("filename", "未命名文档")
            extracted_text = str(document.get("extracted_text", "")).strip()
            storage_path = document.get("storage_path", "")
            document_context = (
                f"上传文档：{filename}\n"
                f"只读文件路径：{storage_path}\n"
                f"文档内容：\n"
                f"{extracted_text or '[未提取到文本，请按只读方式检查原文件]'}"
            )
            requirements.append(document_context)
        return RuntimeRequest(
            task_id=task.task_id,
            project_name=task.project_name,
            workspace_path=task.workspace_path,
            goal=task.goal,
            requirements=requirements,
            previous_outputs=previous_outputs.copy(),
        )

    def _save_run(
        self,
        task_id: str,
        request: RuntimeRequest,
        result: RuntimeResult,
    ) -> None:
        if result.agent_name == "reviewer":
            input_text = RoleContextBuilder.compact_json(
                RoleContextBuilder.review_context(request)
            )
        elif result.agent_name == "verification_engineer":
            report = (
                result.evidence.get("verification_report", {})
                if result.evidence
                else {}
            )
            input_text = RoleContextBuilder.compact_json(
                RoleContextBuilder.verification_context(request, report)
            )
        else:
            input_text = request.model_dump_json()
        self.database.create_agent_run(
            task_id=task_id,
            agent_name=result.agent_name,
            input_text=input_text,
            output=self._result_text(result),
            status=result.status.value,
        )

    def _save_evidence(
        self, task_id: str, result: RuntimeResult
    ) -> None:
        if result.evidence is None:
            return

        evidence = result.evidence
        artifacts = {
            "git_diff": evidence.get("git_diff", ""),
            "changed_files": json.dumps(
                evidence.get("changed_files", []),
                ensure_ascii=False,
            ),
            "test_results": json.dumps(
                evidence.get("test_results", []),
                ensure_ascii=False,
            ),
            "codex_output": evidence.get("codex_output", ""),
        }
        if evidence.get("git_commit"):
            artifacts["git_commit"] = str(evidence["git_commit"])
        for artifact_type, content in artifacts.items():
            self.database.create_task_artifact(
                task_id=task_id,
                artifact_type=artifact_type,
                content=str(content),
            )

    def _prepare_task_workspace(
        self, task: TaskRecord
    ):
        existing_context = None
        for artifact in reversed(
            self.database.list_task_artifacts(task.task_id)
        ):
            if artifact.artifact_type == "task_workspace":
                existing_context = artifact.content
                break
        result = self.task_workspace_manager.prepare(
            workspace_path=task.workspace_path,
            task_id=task.task_id,
            existing_context=existing_context,
        )
        if (
            result.success
            and result.context is not None
            and existing_context is None
        ):
            self.database.create_task_artifact(
                task_id=task.task_id,
                artifact_type="task_workspace",
                content=self.task_workspace_manager.serialize(
                    result.context
                ),
            )
            self.logger.log(
                task_id=task.task_id,
                event_type=EventType.TASK_WORKSPACE_PREPARED,
                agent_name="developer",
                message=(
                    f"Task branch {result.context.task_branch} prepared in "
                    f"{result.context.worktree_path}"
                ),
            )
        return result

    def _task_workspace_context(
        self, task_id: str
    ) -> TaskWorkspaceContext | None:
        for artifact in reversed(
            self.database.list_task_artifacts(task_id)
        ):
            if artifact.artifact_type != "task_workspace":
                continue
            try:
                return TaskWorkspaceContext.model_validate_json(
                    artifact.content
                )
            except (ValueError, TypeError):
                return None
        return None

    def _finalize_task_workspace(
        self, task: TaskRecord
    ) -> TaskRecord:
        context = self._task_workspace_context(task.task_id)
        if context is None:
            return task
        if task.status is not TaskStatus.PASSED:
            self._preserve_task_workspace(task.task_id)
            return task
        integrated = self.task_workspace_manager.integrate(context)
        if not integrated.success:
            reason = integrated.error or "Task commit integration failed"
            self.logger.log(
                task_id=task.task_id,
                event_type=EventType.ERROR,
                agent_name="developer",
                level="ERROR",
                message=reason,
            )
            return self.database.update_task(
                task.task_id,
                status=TaskStatus.BLOCKED,
                blocked_reason=reason,
                required_action=(
                    "Resolve delivery branch divergence and integrate the "
                    "preserved task branch manually"
                ),
            )
        commit_hash = integrated.integrated_commit or ""
        self.database.create_task_artifact(
            task_id=task.task_id,
            artifact_type="integrated_commit",
            content=commit_hash,
        )
        self.logger.log(
            task_id=task.task_id,
            event_type=EventType.TASK_COMMIT_INTEGRATED,
            agent_name="developer",
            message=(
                f"Accepted task commit {commit_hash} integrated into "
                f"{context.delivery_branch}"
            ),
        )
        return task

    def _preserve_task_workspace(self, task_id: str) -> None:
        context = self._task_workspace_context(task_id)
        if context is None:
            return
        self.logger.log(
            task_id=task_id,
            event_type=EventType.TASK_WORKSPACE_PRESERVED,
            agent_name="developer",
            message=(
                f"Unaccepted changes preserved on {context.task_branch}; "
                "delivery workspace was not modified"
            ),
        )

    def _save_iteration(
        self,
        task_id: str,
        *,
        iteration: int,
        supervisor_output: str,
        developer_output: str,
        verification_output: str,
        reviewer_output: str,
        status: TaskStatus,
    ) -> None:
        self.database.create_task_iteration(
            task_id=task_id,
            iteration=iteration,
            supervisor_output=supervisor_output,
            developer_output=developer_output,
            verification_output=verification_output,
            reviewer_output=reviewer_output,
            status=status,
        )

    def _run_decision(
        self, request: SupervisorDecisionRequest
    ) -> DecisionResult:
        decision_method = getattr(
            self.supervisor_runtime, "decision", None
        )
        if decision_method is None:
            return DecisionResult(
                action=DecisionAction.BLOCKED,
                output="",
                error="Supervisor runtime does not support decision",
            )
        try:
            return decision_method(request)
        except Exception as exc:
            return DecisionResult(
                action=DecisionAction.BLOCKED,
                output="",
                error=str(exc),
            )

    def _save_decision_run(
        self,
        task_id: str,
        request: SupervisorDecisionRequest,
        result: DecisionResult,
    ) -> None:
        self.database.create_agent_run(
            task_id=task_id,
            agent_name="supervisor",
            input_text=request.model_dump_json(),
            output=result.output or result.error,
            status="FAILED" if result.error else "COMPLETED",
        )

    @staticmethod
    def _rework_context(
        *,
        original_plan: str,
        review_result: str,
        decision: DecisionResult,
    ) -> str:
        return (
            f"原始任务计划：\n{original_plan}\n\n"
            f"上一轮Reviewer结果：\n{review_result}\n\n"
            f"Supervisor修复任务：\n{decision.developer_task or ''}"
        )

    @staticmethod
    def _run_runtime(
        runtime: AgentRuntime, request: RuntimeRequest
    ) -> RuntimeResult:
        try:
            return runtime.run(request)
        except Exception as exc:
            return RuntimeResult(
                agent_name=runtime.agent_name,
                status=RuntimeStatus.FAILED,
                output="",
                error=str(exc),
            )

    @staticmethod
    def _result_text(result: RuntimeResult) -> str:
        if result.output:
            return result.output
        return result.error or ""

    @staticmethod
    def _persisted_result(agent_name: str, output: str) -> RuntimeResult:
        return RuntimeResult(
            agent_name=agent_name,
            status=RuntimeStatus.COMPLETED,
            output=output,
        )

    @classmethod
    def _persisted_developer_result(cls, output: str) -> RuntimeResult:
        evidence: dict[str, object] | None = None
        try:
            payload = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            payload = None
        if isinstance(payload, dict) and isinstance(
            payload.get("evidence"), dict
        ):
            evidence = payload["evidence"]
        return RuntimeResult(
            agent_name="developer",
            status=RuntimeStatus.COMPLETED,
            output=output,
            evidence=evidence,
        )

    @staticmethod
    def _stage_at_or_before(
        resume_stage: TaskStatus, target: TaskStatus
    ) -> bool:
        order = {
            TaskStatus.ANALYZING: 0,
            TaskStatus.RESEARCHING: 1,
            TaskStatus.PLANNING: 2,
            TaskStatus.DEVELOPING: 3,
            TaskStatus.VERIFYING: 4,
            TaskStatus.REVIEWING: 5,
        }
        return order.get(resume_stage, 0) <= order[target]

    @staticmethod
    def _review_status(result: RuntimeResult) -> TaskStatus:
        if result.status is RuntimeStatus.FAILED:
            return TaskStatus.FAILED
        if result.status is RuntimeStatus.BLOCKED:
            return TaskStatus.BLOCKED
        verdict = result.output.lstrip().split(maxsplit=1)[0].upper()
        return {
            "PASS": TaskStatus.PASSED,
            "FAIL": TaskStatus.FAILED,
            "BLOCKED": TaskStatus.BLOCKED,
        }.get(verdict, TaskStatus.BLOCKED)

    @staticmethod
    def _runtime_failure_status(result: RuntimeResult) -> TaskStatus:
        if result.status is RuntimeStatus.FAILED:
            return TaskStatus.FAILED
        if result.status is RuntimeStatus.REQUIREMENTS_REVISION:
            return TaskStatus.REQUIREMENTS_REVISION
        return TaskStatus.BLOCKED

    @staticmethod
    def _blocked_details(
        status: TaskStatus,
        reason: str,
        required_action: str,
    ) -> dict[str, str]:
        if status is not TaskStatus.BLOCKED:
            return {}
        return {
            "blocked_reason": reason or "Task is blocked",
            "required_action": required_action,
        }

    def _human_control_state(self, task_id: str) -> TaskRecord | None:
        task = self.database.get_task(task_id)
        if task is None:
            raise KeyError(f"任务不存在：{task_id}")
        if task.status in {TaskStatus.PAUSED, TaskStatus.CANCELED}:
            return task
        return None

    def _log_runtime_error(
        self, task_id: str, result: RuntimeResult
    ) -> None:
        self.logger.log(
            task_id=task_id,
            event_type=EventType.ERROR,
            agent_name=result.agent_name,
            level="ERROR",
            message=result.error or result.output or "Runtime failed",
        )
