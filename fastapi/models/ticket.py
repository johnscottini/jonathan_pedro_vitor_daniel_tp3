"""Schemas de entrada e saída das rotas de ticket — contrato da fase 0.

`TicketCreate` não tem `owner_id` de propósito: o dono do ticket vem do token,
nunca do corpo da requisição. Se ele estivesse aqui, qualquer cliente poderia
criar ticket em nome de outro usuário.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from models.base import StrictModel


class TicketCreate(StrictModel):
    subject: str = Field(..., min_length=1, max_length=200, description="Assunto do ticket",
                         examples=["Payment issue"])
    description: str = Field(..., min_length=1, max_length=4000, description="Texto escrito pelo cliente",
                             examples=["I was charged twice for the same order."])
    ticket_type: str = Field(..., min_length=1, max_length=50, description="Tipo (intenção) declarado",
                             examples=["Billing inquiry"])
    priority: str = Field(default="Low", max_length=20, description="Low, Medium, High ou Critical",
                          examples=["High"])
    channel: str = Field(default="Email", max_length=20, description="Canal de abertura",
                         examples=["Email"])


class TicketRead(BaseModel):
    id: int
    owner_id: int
    subject: str
    description: str
    ticket_type: str
    priority: str
    channel: str
    status: str
    created_at: datetime
