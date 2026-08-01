from fastapi import APIRouter, Request

from backend.models.agent import AgentCatalog
from backend.services.agent_catalog_service import AgentCatalogService

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/catalog", response_model=AgentCatalog)
def get_agent_catalog(request: Request) -> AgentCatalog:
    service: AgentCatalogService = request.app.state.agent_catalog_service
    return service.catalog()
