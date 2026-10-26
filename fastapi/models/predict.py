from pydantic import BaseModel, Field

from models.base import StrictModel


class PredictRequest(StrictModel):
    text: str = Field(
        ...,
        min_length=1,
        description="Texto do ticket enviado pelo cliente",
        examples=["I was charged twice for my order and want a refund."],
    )


class PredictResponse(BaseModel):
    intent: str = Field(..., description="Intenção prevista", examples=["refund_request"])
    confidence: float = Field(..., ge=0, le=1, description="Confiança da previsão (0 a 1)", examples=[0.5])
