from fastapi import APIRouter

from core.config import API_VERSION
from models.errors import ErrorResponse
from models.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Verifica se a API está ativa",
    description="Rota pública (sem autenticação) para monitoramento. Devolve o status e a versão da API.",
    responses={500: {"model": ErrorResponse, "description": "Erro interno"}},
)
def health_check() -> HealthResponse:
    """Endpoint público, sem autenticação necessária.

    Devolve uma resposta estruturada (`HealthResponse`) em vez de um dicionário
    solto: o formato fica declarado no OpenAPI e o monitoramento externo pode
    checar `status` e `version` sem depender de um JSON ad-hoc.
    """
    return HealthResponse(status="ok", version=API_VERSION)
