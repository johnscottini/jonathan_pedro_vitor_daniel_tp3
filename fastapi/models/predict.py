from pydantic import BaseModel, Field

from models.base import StrictModel


class PredictRequest(StrictModel):
    text: str = Field(..., min_length=1, description="Texto do ticket enviado pelo cliente")


class PredictResponse(BaseModel):
    intent: str
    confidence: float
