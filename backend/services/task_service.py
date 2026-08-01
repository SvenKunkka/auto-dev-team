from __future__ import annotations

import json
from uuid import uuid4

from backend.database.sqlite import SQLiteDatabase
from backend.models.task import (
    EvidenceSummary,
    TaskCreate,
    TaskDetail,
    TaskDocument,
    TaskRecord,
    SpecialistOutput,
    TaskStatus,
)
from backend.observability.logger import EventType, StructuredLogger
from backend.services.crew_service import CrewService
from backend.services.agent_catalog_service import AgentCatalogService
from backend.services.document_service import (
    DocumentService,
    DocumentUpload,
)


class InvalidTaskTransition(ValueError):
    pass


class TaskService:
    def __init__(
        self,
        database: SQLiteDatabase,
        crew_service: CrewService,
        agent_catalog_service: AgentCatalogService | None = None,
    ) -> None:
        self.database = database
        self.crew_service = crew_service
        self.logger = StructuredLogger(database)
        self.document_service = DocumentService(
            database.database_path.parent / "uploads"
        )
        self.agent_catalog_service = (
            agent_catalog_service or AgentCatalogService()
        )

    def create_task(
        self, task: TaskCreate, *, has_documents: bool = False
    ) -> TaskRecord:
        workflow_steps = self.agent_catalog_service.normalize_workflow(
            task.workflow_steps,
            task.selected_agents,
            task.agent_models,
        )
        selected_agents = list(
            dict.fromkeys(step.role_id for step in workflow_steps)
        )
        normalized_models = {
            step.role_id: step.model_id for step in workflow_steps
        }
        task = task.model_copy(
            update={
                "selected_agents": selected_agents,
                "agent_models": normalized_models,
                "workflow_steps": workflow_steps,
            }
        )
        if (
            not task.goal.strip()
            and not any(item.strip() for item in task.requirements)
            and not has_documents
        ):
            raise ValueError(
                "任务目标、需求列表或需求文档至少需要提供一项"
            )
        task_id = str(uuid4())
        created = self.database.create_task(task_id, task)
        self.logger.log(
            task_id=task_id,
            event_type=EventType.TASK_CREATED,
            message=f"Task created for project {task.project_name}",
        )
        return created

    def create_task_with_documents(
        self, task: TaskCreate, uploads: list[DocumentUpload]
    ) -> TaskRecord:
        self.document_service.validate_documents(uploads)
        created = self.create_task(
            task, has_documents=bool(uploads)
        )
        try:
            self.attach_documents(created.task_id, uploads)
        except Exception as exc:
            self.database.update_task(
                created.task_id,
                status=TaskStatus.FAILED,
            )
            self.logger.log(
                task_id=created.task_id,
                event_type=EventType.ERROR,
                level="ERROR",
                message=f"Document storage failed: {exc}",
            )
            raise
        self.enqueue_task(created.task_id)
        return created

    def run_task(self, task_id: str) -> TaskRecord:
        task = self.database.get_task(task_id)
        if task is None:
            raise KeyError(f"任务不存在：{task_id}")
        if task.status in {
            TaskStatus.PASSED,
            TaskStatus.FAILED,
            TaskStatus.BLOCKED,
            TaskStatus.REQUIREMENTS_REVISION,
            TaskStatus.PAUSED,
            TaskStatus.CANCELED,
        }:
            return task
        if task.status is TaskStatus.WAITING_DEPENDENCY:
            return task
        if task.status is not TaskStatus.QUEUED:
            task = self.database.enqueue_task_in_order(task_id)
            if task.status is TaskStatus.WAITING_DEPENDENCY:
                return task
        return self.crew_service.run_task(task_id)

    def attach_documents(
        self, task_id: str, uploads: list[DocumentUpload]
    ) -> list[TaskDocument]:
        task = self._require_task(task_id)
        if task.status is not TaskStatus.CREATED:
            raise InvalidTaskTransition(
                "只能在任务进入队列前上传文档"
            )
        stored = self.document_service.save_documents(task_id, uploads)
        for document in stored:
            self.database.create_task_artifact(
                task_id=task_id,
                artifact_type="input_document",
                content=document.artifact_content(),
            )
            self.logger.log(
                task_id=task_id,
                event_type=EventType.DOCUMENT_UPLOADED,
                message=(
                    f"Document uploaded: "
                    f"{document.metadata.filename} "
                    f"({document.metadata.size} bytes)"
                ),
            )
        return [document.metadata for document in stored]

    def enqueue_task(self, task_id: str) -> TaskRecord:
        task = self.database.get_task(task_id)
        if task is None:
            raise KeyError(f"任务不存在：{task_id}")
        if task.status in {
            TaskStatus.PASSED,
            TaskStatus.FAILED,
            TaskStatus.BLOCKED,
            TaskStatus.REQUIREMENTS_REVISION,
            TaskStatus.PAUSED,
            TaskStatus.CANCELED,
        }:
            return task
        if task.status in {
            TaskStatus.QUEUED,
            TaskStatus.WAITING_DEPENDENCY,
        }:
            return task
        return self.database.enqueue_task_in_order(task_id)

    def list_tasks(self) -> list[TaskRecord]:
        return self.database.list_tasks()

    def get_task(self, task_id: str) -> TaskRecord | None:
        return self.database.get_task(task_id)

    def get_task_detail(self, task_id: str) -> TaskDetail | None:
        task = self.database.get_task(task_id)
        if task is None:
            return None
        artifacts = self.database.list_task_artifacts(task_id)
        iterations = self.database.list_task_iterations(task_id)
        artifact_types = sorted({item.artifact_type for item in artifacts})
        changed_files_count = 0
        test_count = 0
        failed_test_count = 0
        documents: list[TaskDocument] = []
        specialist_outputs: list[SpecialistOutput] = []
        for artifact in artifacts:
            if artifact.artifact_type == "changed_files":
                try:
                    changed_files_count += len(json.loads(artifact.content))
                except (TypeError, ValueError):
                    pass
            elif artifact.artifact_type == "test_results":
                try:
                    results = json.loads(artifact.content)
                except (TypeError, ValueError):
                    continue
                test_count += len(results)
                failed_test_count += sum(
                    1
                    for result in results
                    if result.get("exit_code", 0) != 0
                )
            elif artifact.artifact_type == "input_document":
                try:
                    content = json.loads(artifact.content)
                    documents.append(
                        TaskDocument(
                            filename=content["filename"],
                            content_type=content["content_type"],
                            size=content["size"],
                            sha256=content["sha256"],
                            storage_path=content["storage_path"],
                        )
                    )
                except (KeyError, TypeError, ValueError):
                    pass
            elif artifact.artifact_type == "specialist_output":
                try:
                    specialist_outputs.append(
                        SpecialistOutput.model_validate_json(
                            artifact.content
                        )
                    )
                except (TypeError, ValueError):
                    pass
        current_agent = {
            TaskStatus.ANALYZING: "requirement_analyst",
            TaskStatus.RESEARCHING: task.active_agent,
            TaskStatus.PLANNING: "supervisor",
            TaskStatus.REQUIREMENTS_REVISION: "requirement_analyst",
            TaskStatus.DEVELOPING: "developer",
            TaskStatus.VERIFYING: "verification_engineer",
            TaskStatus.REVIEWING: "reviewer",
            TaskStatus.REWORKING: "supervisor",
        }.get(task.status) or task.active_agent
        iteration = max(
            [task.retry_count + 1, *(item.iteration for item in iterations)]
        )
        return TaskDetail(
            **task.model_dump(),
            current_agent=current_agent,
            iteration=iteration,
            heartbeat=task.last_heartbeat,
            evidence_summary=EvidenceSummary(
                artifact_count=len(artifacts),
                artifact_types=artifact_types,
                changed_files_count=changed_files_count,
                test_count=test_count,
                failed_test_count=failed_test_count,
            ),
            documents=documents,
            specialist_outputs=specialist_outputs,
            logs=self.database.list_execution_logs(task_id),
        )

    def cancel_task(self, task_id: str) -> TaskRecord:
        task = self._require_task(task_id)
        if task.status in {
            TaskStatus.PASSED,
            TaskStatus.CANCELED,
        }:
            raise InvalidTaskTransition(
                f"Cannot cancel task in {task.status.value}"
            )
        updated = self.database.update_task(
            task_id, status=TaskStatus.CANCELED
        )
        self.logger.log(
            task_id=task_id,
            event_type=EventType.TASK_CANCELED,
            message="Task cancellation requested",
        )
        return updated

    def pause_task(self, task_id: str) -> TaskRecord:
        task = self._require_task(task_id)
        if task.status in {
            TaskStatus.PASSED,
            TaskStatus.FAILED,
            TaskStatus.BLOCKED,
            TaskStatus.REQUIREMENTS_REVISION,
            TaskStatus.CANCELED,
            TaskStatus.PAUSED,
        }:
            raise InvalidTaskTransition(
                f"Cannot pause task in {task.status.value}"
            )
        updated = self.database.update_task(
            task_id, status=TaskStatus.PAUSED
        )
        self.logger.log(
            task_id=task_id,
            event_type=EventType.TASK_PAUSED,
            message="Task pause requested",
        )
        return updated

    def retry_task(self, task_id: str) -> TaskRecord:
        task = self._require_task(task_id)
        if task.status not in {
            TaskStatus.FAILED,
            TaskStatus.BLOCKED,
            TaskStatus.REQUIREMENTS_REVISION,
            TaskStatus.CANCELED,
            TaskStatus.PAUSED,
        }:
            raise InvalidTaskTransition(
                f"Cannot retry task in {task.status.value}"
            )
        updated = self.database.reset_task_for_retry(task_id)
        self.logger.log(
            task_id=task_id,
            event_type=EventType.TASK_RETRIED,
            message="Task requeued by human control",
        )
        return updated

    def _require_task(self, task_id: str) -> TaskRecord:
        task = self.database.get_task(task_id)
        if task is None:
            raise KeyError(f"任务不存在：{task_id}")
        return task
