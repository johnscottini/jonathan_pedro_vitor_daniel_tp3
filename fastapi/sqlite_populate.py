"""População do banco com tickets e predições de exemplo, usando `sqlite3`.

Uso, a partir da raiz do repositório:

    python fastapi/sqlite_populate.py

Primeiro garante as tabelas e os dados iniciais (`sqlite_database.criar_banco`).
Depois insere, para cada usuário, alguns tickets tirados do Customer Support
Ticket Dataset, além de uma predição feita sobre a descrição de cada ticket.
Cada usuário recebe recursos diferentes, para que o controle de ownership (BOLA)
possa ser demonstrado com o banco real: o `bob` não enxerga os tickets nem as
predições da `alice`, e vice-versa.

O script é idempotente: antes de inserir, confere se o mesmo recurso já existe
para aquele dono. Todo valor entra no SQL como parâmetro (`?`).
"""

import csv
import sqlite3
from contextlib import closing
from typing import Dict, List, Tuple

from core.config import BASE_DIR, SQLITE_PATH
from security.users import ADMIN_USERNAME
from sqlite_database import agora, conectar, criar_banco, id_do_usuario, inserir_prediction

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


def _valores_do_ticket(row: dict, owner_id: int) -> Tuple:
    # O dataset traz o placeholder `{product_purchased}` no texto (insight I4 da
    # EDA); aqui ele é trocado pelo produto real para o exemplo ficar legível.
    descricao = row["Ticket Description"].replace("{product_purchased}", row["Product Purchased"])
    return (
        owner_id,
        row["Ticket Subject"][:200],
        descricao[:4000],
        row["Ticket Type"][:50],
        row["Ticket Priority"][:20],
        row["Ticket Channel"][:20],
        row["Ticket Status"][:30],
        agora(),
    )


def popular(conn: sqlite3.Connection) -> Tuple[int, int]:
    """Insere os tickets e as predições que ainda não existem. Devolve (tickets, predições)."""
    todos_ids = [i for ids in TICKETS_POR_USUARIO.values() for i in ids]
    linhas = _ler_linhas(todos_ids)
    tickets = predictions = 0

    for username, ids in TICKETS_POR_USUARIO.items():
        owner_id = id_do_usuario(conn, username)
        if owner_id is None:
            continue
        for ticket_id in ids:
            valores = _valores_do_ticket(linhas[ticket_id], owner_id)
            existe = conn.execute(
                "SELECT 1 FROM ticket WHERE owner_id = ? AND subject = ? AND description = ?",
                valores[:3],
            ).fetchone()
            if not existe:
                conn.execute(
                    "INSERT INTO ticket (owner_id, subject, description, ticket_type, "
                    "priority, channel, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    valores,
                )
                tickets += 1
            # Uma predição feita pelo mesmo usuário sobre o texto do ticket.
            predictions += inserir_prediction(conn, owner_id, valores[2])

    return tickets, predictions


if __name__ == "__main__":
    criar_banco()
    with closing(conectar()) as conn:
        with conn:
            tickets, predictions = popular(conn)
        total_t = conn.execute("SELECT COUNT(*) FROM ticket").fetchone()[0]
        total_p = conn.execute("SELECT COUNT(*) FROM prediction").fetchone()[0]
    print(
        f"[populate] {tickets} tickets e {predictions} predições criados "
        f"({total_t} tickets e {total_p} predições em {SQLITE_PATH})"
    )
