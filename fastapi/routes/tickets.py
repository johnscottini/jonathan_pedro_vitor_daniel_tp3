"""Rotas de tickets — ownership / BOLA (OWASP A01).

Três regras sustentam o controle de acesso aqui:

1. `owner_id` **sempre** vem de `current_user.id`, nunca do corpo da requisição.
   Se viesse do body, qualquer cliente criaria ticket em nome de outro usuário
   (mass assignment). O schema `TicketCreate` nem sequer aceita o campo, porque
   herda de `StrictModel` (`extra="forbid"`).
2. A listagem filtra por `Ticket.owner_id == current_user.id`: ninguém vê ticket
   alheio nem por acidente.
3. Buscar um ticket de outro usuário devolve **404**, não 403. O 403 confirmaria
   que aquele ID existe, permitindo mapear a base por tentativa e erro
   (enumeração de identificadores).

Todas as consultas usam `select()`/`session.get()` do SQLModel, que geram SQL
parametrizado — não existe string de SQL concatenada no projeto (OWASP A03).
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from db import get_session
from models.errors import ErrorResponse
from models.tables import Ticket, User
from models.ticket import TicketCreate, TicketRead
from security.jwt import get_current_user

router = APIRouter(prefix="/tickets", tags=["tickets"])

_RESPOSTAS_PROTEGIDAS = {
    401: {"model": ErrorResponse, "description": "Token ausente, inválido ou expirado"},
    404: {"model": ErrorResponse, "description": "Ticket inexistente ou de outro usuário"},
    422: {"model": ErrorResponse, "description": "Corpo da requisição inválido"},
}


@router.post(
    "",
    response_model=TicketRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cria um ticket para o usuário autenticado",
    responses={k: v for k, v in _RESPOSTAS_PROTEGIDAS.items() if k != 404},
)
def criar_ticket(
    payload: TicketCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Ticket:
    ticket = Ticket(**payload.model_dump(), owner_id=current_user.id)
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


@router.get(
    "",
    response_model=List[TicketRead],
    summary="Lista os tickets do usuário autenticado",
    responses={401: _RESPOSTAS_PROTEGIDAS[401]},
)
def listar_tickets(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> List[Ticket]:
    consulta = select(Ticket).where(Ticket.owner_id == current_user.id).order_by(Ticket.id)
    return list(session.exec(consulta))


@router.get(
    "/{ticket_id}",
    response_model=TicketRead,
    summary="Busca um ticket por ID (somente do próprio usuário)",
    responses=_RESPOSTAS_PROTEGIDAS,
)
def obter_ticket(
    ticket_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Ticket:
    ticket = session.get(Ticket, ticket_id)

    # Ticket inexistente e ticket de outro usuário respondem exatamente igual.
    if ticket is None or ticket.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket não encontrado",
        )

    return ticket
