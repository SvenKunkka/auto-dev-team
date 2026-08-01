from __future__ import annotations

import json

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import ValidationError

from backend.models.task import TaskCreate, TaskCreated, TaskDetail, TaskRecord
from backend.services.document_service import (
    MAX_DOCUMENT_SIZE,
    DocumentUpload,
    DocumentValidationError,
)
from backend.services.task_service import (
    InvalidTaskTransition,
    TaskService,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


def get_task_service(request: Request) -> TaskService:
    return request.app.state.task_service


@router.post("", response_model=TaskCreated, status_code=status.HTTP_201_CREATED)
def create_task(
    task: TaskCreate,
    request: Request,
) -> TaskCreated:
    task_service = get_task_service(request)
    try:
        created = task_service.create_task(task)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    task_service.enqueue_task(created.task_id)
    return TaskCreated(task_id=created.task_id, status=created.status)


@router.post(
    "/with-documents",
    response_model=TaskCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_task_with_documents(
    request: Request,
    project_name: str = Form(...),
    workspace_path: str = Form(...),
    goal: str = Form(""),
    requirements: str = Form("[]"),
    priority: str = Form("normal"),
    execution_mode: str = Form("dry_run"),
    selected_agents: str = Form(
        '["requirement_analyst","supervisor","developer",'
        '"verification_engineer","reviewer"]'
    ),
    agent_models: str = Form("{}"),
    workflow_steps: str = Form("[]"),
    documents: list[UploadFile] = File(default=[]),
) -> TaskCreated:
    try:
        parsed_requirements = json.loads(requirements)
        task = TaskCreate(
            project_name=project_name,
            workspace_path=workspace_path,
            goal=goal,
            requirements=parsed_requirements,
            priority=priority,
            execution_mode=execution_mode,
            selected_agents=json.loads(selected_agents),
            agent_models=json.loads(agent_models),
            workflow_steps=json.loads(workflow_steps),
        )
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(
            status_code=422, detail="任务参数格式无效"
        ) from exc

    uploads = [
        DocumentUpload(
            filename=document.filename or "",
            content_type=document.content_type or "",
            content=await document.read(MAX_DOCUMENT_SIZE + 1),
        )
        for document in documents
    ]
    try:
        created = get_task_service(request).create_task_with_documents(
            task, uploads
        )
    except DocumentValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TaskCreated(task_id=created.task_id, status=created.status)


@router.get("", response_model=list[TaskRecord])
def list_tasks(request: Request) -> list[TaskRecord]:
    return get_task_service(request).list_tasks()


@router.get("/{task_id}", response_model=TaskDetail)
def get_task(task_id: str, request: Request) -> TaskDetail:
    task = get_task_service(request).get_task_detail(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


def _control_task(
    task_id: str,
    request: Request,
    action: str,
) -> TaskRecord:
    service = get_task_service(request)
    try:
        return getattr(service, f"{action}_task")(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="任务不存在") from exc
    except InvalidTaskTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{task_id}/cancel", response_model=TaskRecord)
def cancel_task(task_id: str, request: Request) -> TaskRecord:
    return _control_task(task_id, request, "cancel")


@router.post("/{task_id}/retry", response_model=TaskRecord)
def retry_task(task_id: str, request: Request) -> TaskRecord:
    return _control_task(task_id, request, "retry")


@router.post("/{task_id}/pause", response_model=TaskRecord)
def pause_task(task_id: str, request: Request) -> TaskRecord:
    return _control_task(task_id, request, "pause")
