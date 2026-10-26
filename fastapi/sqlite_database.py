"""Criação e população inicial do banco SQLite (`fastapi/database.db`) com `sqlite3`.

Uso, a partir da raiz do repositório:

    python fastapi/sqlite_database.py

O script usa o módulo `sqlite3` da biblioteca padrão do Python para:

1. criar as tabelas `user`, `ticket` e `prediction`;
2. criar os usuários iniciais (`admin`, `alice` e `bob`), com senha em hash bcrypt;
3. criar predições iniciais pertencentes a usuários diferentes. O campo
   `owner_id` de cada predição é a base da verificação de ownership (BOLA).

A API também chama este script quando sobe (`main.py`). Ele é idempotente:
rodar de novo não duplica nada. Dentro da API, as consultas são feitas só pelo
SQLModel (`core/database.py`). Aqui, todo valor entra no SQL como parâmetro
(`?`), nunca por concatenação de strings (OWASP A03).

O DDL abaixo espelha os modelos de `models/tables.py`, e o teste
`tests/test_banco_sqlite.py` confere que os dois continuam iguais.
"""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from typing import Dict, List, Optional

from core.config import SQLITE_PATH
from core.intencao import prever_intencao
from security.users import SEED_USERS, hash_password

DDL = """
CREATE TABLE IF NOT EXISTS user (
    id INTEGER NOT NULL,
    username VARCHAR(50) NOT NULL,
    hashed_password VARCHAR NOT NULL,
    PRIMARY KEY (id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_user_username ON user (username);

CREATE TABLE IF NOT EXISTS ticket (
    id INTEGER NOT NULL,
    owner_id INTEGER NOT NULL,
    subject VARCHAR(200) NOT NULL,
    description VARCHAR(4000) NOT NULL,
    ticket_type VARCHAR(50) NOT NULL,
    priority VARCHAR(20) NOT NULL,
    channel VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(owner_id) REFERENCES user (id)
);
CREATE INDEX IF NOT EXISTS ix_ticket_owner_id ON ticket (owner_id);

CREATE TABLE IF NOT EXISTS prediction (
    id INTEGER NOT NULL,
    owner_id INTEGER NOT NULL,
    text VARCHAR(4000) NOT NULL,
    intent VARCHAR(50) NOT NULL,
    confidence FLOAT NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(owner_id) REFERENCES user (id)
);
CREATE INDEX IF NOT EXISTS ix_prediction_owner_id ON prediction (owner_id);
"""

# Predições iniciais: pelo menos duas por usuário comum, para que o banco já
# tenha recursos de donos diferentes (a alice não pode ler as do bob, e vice-versa).
PREDICTIONS_INICIAIS: Dict[str, List[str]] = {
    "alice": [
        "I was charged twice for my last order, please check my bill.",
        "I want a refund for the headphones I returned last week.",
    ],
    "bob": [
        "Please cancel my subscription before the next renewal.",
        "The app shows an error every time I try to log in.",
    ],
    "admin": [
        "Does this laptop support an external 4K monitor?",
    ],
}


def agora() -> str:
    """Data e hora UTC no mesmo formato que o SQLModel grava no SQLite."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")


def conectar(path: str = SQLITE_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    # O SQLite só aplica as FOREIGN KEY quando isto está ligado na conexão.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def criar_tabelas(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)


def id_do_usuario(conn: sqlite3.Connection, username: str) -> Optional[int]:
    linha = conn.execute("SELECT id FROM user WHERE username = ?", (username,)).fetchone()
    return linha[0] if linha else None


def popular_usuarios(conn: sqlite3.Connection) -> List[str]:
    """Cria os usuários do `SEED_USERS` que ainda não existirem."""
    criados = []
    for username, senha in SEED_USERS.items():
        if id_do_usuario(conn, username) is None:
            conn.execute(
                "INSERT INTO user (username, hashed_password) VALUES (?, ?)",
                (username, hash_password(senha)),
            )
            criados.append(username)
    return criados


def inserir_prediction(conn: sqlite3.Connection, owner_id: int, texto: str) -> bool:
    """Insere a predição se ela ainda não existir para esse dono. Devolve se inseriu."""
    existe = conn.execute(
        "SELECT 1 FROM prediction WHERE owner_id = ? AND text = ?", (owner_id, texto)
    ).fetchone()
    if existe:
        return False
    intent, confidence = prever_intencao(texto)
    conn.execute(
        "INSERT INTO prediction (owner_id, text, intent, confidence, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (owner_id, texto, intent, confidence, agora()),
    )
    return True


def popular_predictions_iniciais(conn: sqlite3.Connection) -> int:
    criadas = 0
    for username, textos in PREDICTIONS_INICIAIS.items():
        owner_id = id_do_usuario(conn, username)
        if owner_id is not None:
            criadas += sum(inserir_prediction(conn, owner_id, texto) for texto in textos)
    return criadas


def criar_banco(path: str = SQLITE_PATH) -> None:
    """Cria tabelas, usuários e predições iniciais. Idempotente."""
    with closing(conectar(path)) as conn:
        with conn:  # commit no final; rollback se algo falhar
            criar_tabelas(conn)
            usuarios = popular_usuarios(conn)
            predictions = popular_predictions_iniciais(conn)
    if usuarios or predictions:
        print(f"[db] usuários criados: {usuarios or 'nenhum'} | predições criadas: {predictions}")


if __name__ == "__main__":
    criar_banco()
    print(f"[db] banco pronto em {SQLITE_PATH}")
