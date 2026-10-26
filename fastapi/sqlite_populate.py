"""População inicial do banco com tickets de exemplo.

Uso, a partir da raiz do repositório:

    python fastapi/sqlite_populate.py

Garante as tabelas e os usuários do seed (`sqlite_database.init_db`) e cria
alguns tickets para cada usuário, tirados do Customer Support Ticket Dataset.
Cada usuário recebe tickets diferentes, para que o controle de ownership (BOLA)
possa ser demonstrado com o banco real: o `bob` não enxerga os tickets da
`alice`, e vice-versa.

O script é idempotente: rodar de novo não duplica tickets, porque cada um é
identificado pelo par (dono, assunto, descrição) antes de ser inserido.
"""

import csv
from pathlib import Path
from typing import Dict, List

from sqlmodel import Session, select

from core.config import BASE_DIR
from models.tables import Ticket
from security.users import ADMIN_USERNAME, get_user
from sqlite_database import engine, init_db

CSV_PATH = BASE_DIR.parent / "data" / "customer_support_tickets.csv"

# Linhas do dataset (coluna `Ticket ID`) usadas para cada usuário. Foram
# escolhidas para cobrir tipos de ticket diferentes por usuário.
TICKETS_POR_USUARIO: Dict[str, List[str]] = {
    "alice": ["1", "4", "6"],
    "bob": ["2", "5", "8"],
    ADMIN_USERNAME: ["3", "7"],
}


def _ler_linhas(ids: List[str]) -> Dict[str, dict]:
    """Lê do CSV apenas as linhas com os `Ticket ID` pedidos."""
    wanted = set(ids)
    with open(CSV_PATH, newline="", encoding="utf-8") as arquivo:
        return {row["Ticket ID"]: row for row in csv.DictReader(arquivo) if row["Ticket ID"] in wanted}


def _ticket_da_linha(row: dict, owner_id: int) -> Ticket:
    # O dataset traz o placeholder `{product_purchased}` no texto (insight I4 da
    # EDA); aqui ele é trocado pelo produto real para o exemplo ficar legível.
    descricao = row["Ticket Description"].replace("{product_purchased}", row["Product Purchased"])
    return Ticket(
        owner_id=owner_id,
        subject=row["Ticket Subject"][:200],
        description=descricao[:4000],
        ticket_type=row["Ticket Type"][:50],
        priority=row["Ticket Priority"][:20],
        channel=row["Ticket Channel"][:20],
        status=row["Ticket Status"][:30],
    )


def popular(session: Session) -> int:
    """Insere os tickets de exemplo que ainda não existem. Devolve quantos criou."""
    todos_ids = [i for ids in TICKETS_POR_USUARIO.values() for i in ids]
    linhas = _ler_linhas(todos_ids)
    criados = 0

    for username, ids in TICKETS_POR_USUARIO.items():
        user = get_user(session, username)
        if user is None:
            continue
        for ticket_id in ids:
            ticket = _ticket_da_linha(linhas[ticket_id], user.id)
            # Consulta parametrizada pelo SQLModel — nada de SQL cru (OWASP A03).
            existente = session.exec(
                select(Ticket).where(
                    Ticket.owner_id == user.id,
                    Ticket.subject == ticket.subject,
                    Ticket.description == ticket.description,
                )
            ).first()
            if existente is None:
                session.add(ticket)
                criados += 1

    session.commit()
    return criados


if __name__ == "__main__":
    init_db()
    with Session(engine) as session:
        criados = popular(session)
        total = len(session.exec(select(Ticket)).all())
    print(f"[populate] {criados} tickets criados ({total} no banco)")
