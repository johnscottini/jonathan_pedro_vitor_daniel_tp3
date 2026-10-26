"""Modelo de resposta da rota GET /health.

A rota de health também tem um modelo de resposta declarado (em vez de devolver
um dicionário solto): assim o contrato aparece no OpenAPI/Swagger, o FastAPI
valida a saída e qualquer monitoramento externo pode confiar no formato.
"""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., description="'ok' quando a API está no ar", examples=["ok"])
    version: str = Field(..., description="Versão da API", examples=["0.3.0"])
