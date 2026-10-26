"""Tabelas do banco (SQLModel) — definidas no contrato da fase 0.

Alterar os campos aqui quebra o trabalho das outras pessoas do time, então
qualquer mudança precisa ser combinada antes.

`Ticket.owner_id` é o campo que sustenta a verificação de ownership (BOLA,
OWASP A01): todo acesso a um ticket precisa comparar esse campo com o usuário
autenticado.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, max_length=50)
    hashed_password: str


class Ticket(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # Dono do recurso. NUNCA vem do body da requisição: é sempre preenchido a
    # partir do usuário autenticado.
    owner_id: int = Field(foreign_key="user.id", index=True)
    subject: str = Field(max_length=200)
    description: str = Field(max_length=4000)
    ticket_type: str = Field(max_length=50)
    priority: str = Field(default="Low", max_length=20)
    channel: str = Field(default="Email", max_length=20)
    status: str = Field(default="Open", max_length=30)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Prediction(SQLModel, table=True):
    """Cada chamada ao `POST /predict` fica registrada aqui, com o seu dono.

    Assim como em `Ticket`, o `owner_id` é a base do controle de BOLA: o
    `GET /predictions/{id}` só devolve a predição a quem a fez.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", index=True)
    text: str = Field(max_length=4000)
    intent: str = Field(max_length=50)
    confidence: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
