from fastapi import APIRouter, HTTPException, Request, status

from backend.models.agent import (
    AgentModelOption,
    ModelConfigCreate,
    ModelCredentialUpdate,
)
from backend.services.model_config_service import ModelConfigService

router = APIRouter(prefix="/models", tags=["models"])


def get_service(request: Request) -> ModelConfigService:
    return request.app.state.model_config_service


@router.get("", response_model=list[AgentModelOption])
def list_models(request: Request) -> list[AgentModelOption]:
    return get_service(request).list_models()


@router.post(
    "",
    response_model=AgentModelOption,
    status_code=status.HTTP_201_CREATED,
)
def create_model(
    payload: ModelConfigCreate, request: Request
) -> AgentModelOption:
    try:
        return get_service(request).create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="模型配置保存失败"
        ) from exc


@router.post(
    "/{model_id}/credential", response_model=AgentModelOption
)
def update_credential(
    model_id: str,
    payload: ModelCredentialUpdate,
    request: Request,
) -> AgentModelOption:
    try:
        return get_service(request).set_credential(
            model_id, payload.api_key
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="API Key写入Keychain失败"
        ) from exc


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(model_id: str, request: Request) -> None:
    try:
        get_service(request).delete(model_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
