from datetime import datetime

from pydantic import BaseModel, Field

from models.base import StrictModel


class PredictRequest(StrictModel):
    text: str = Field(
        ...,
        min_length=1,
        # Mesmo teto da descrição de um ticket: sem limite, um corpo de vários MB
        # chegaria inteiro ao classificador (superfície de negação de serviço).
        max_length=4000,
        description="Texto do ticket enviado pelo cliente (até 4000 caracteres)",
        examples=["I was charged twice for my order and want a refund."],
    )


class PredictResponse(BaseModel):
    id: int = Field(..., description="ID da predição registrada, para consulta em `GET /predictions/{id}`", examples=[1])
    intent: str = Field(..., description="Intenção prevista", examples=["refund_request"])
    confidence: float = Field(..., ge=0, le=1, description="Confiança da previsão (0 a 1)", examples=[0.5])


class PredictionRead(BaseModel):
    """Uma predição registrada, como devolvida por `GET /predictions`."""

    id: int
    owner_id: int
    text: str
    intent: str
    confidence: float
    created_at: datetime
