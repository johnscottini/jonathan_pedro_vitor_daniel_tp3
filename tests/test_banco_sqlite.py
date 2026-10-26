"""Criação e população do banco com `sqlite3` (`sqlite_database.py` e `sqlite_populate.py`).

Os scripts rodam sobre um arquivo temporário: o `fastapi/database.db`
versionado nunca é tocado.
"""

import sqlite3
from contextlib import closing

from sqlmodel import SQLModel

import sqlite_populate
from sqlite_database import conectar, criar_banco


def _colunas(conn, tabela):
    return {linha[1] for linha in conn.execute(f"PRAGMA table_info({tabela})")}


def test_ddl_do_sqlite3_espelha_os_modelos_sqlmodel(tmp_path):
    """Se alguém mudar `models/tables.py`, o DDL do script precisa mudar junto."""
    banco = str(tmp_path / "teste.db")
    criar_banco(banco)

    with closing(sqlite3.connect(banco)) as conn:
        for tabela in SQLModel.metadata.sorted_tables:
            assert _colunas(conn, tabela.name) == {c.name for c in tabela.columns}, tabela.name


def test_banco_inicial_tem_predicoes_de_donos_diferentes(tmp_path):
    banco = str(tmp_path / "teste.db")
    criar_banco(banco)

    with closing(sqlite3.connect(banco)) as conn:
        usuarios = {u for (u,) in conn.execute("SELECT username FROM user")}
        donos = conn.execute(
            "SELECT u.username, COUNT(*) FROM prediction p JOIN user u ON u.id = p.owner_id "
            "GROUP BY u.username"
        ).fetchall()
        senhas = [h for (h,) in conn.execute("SELECT hashed_password FROM user")]

    assert {"alice", "bob", "admin"} <= usuarios
    assert {dono for dono, _ in donos} >= {"alice", "bob"}
    assert all(qtd >= 2 for dono, qtd in donos if dono in {"alice", "bob"})
    # Senha nunca em texto: só hash bcrypt.
    assert all(h.startswith("$2") for h in senhas)


def test_scripts_sao_idempotentes(tmp_path):
    banco = str(tmp_path / "teste.db")
    criar_banco(banco)
    with closing(conectar(banco)) as conn:
        with conn:
            primeira = sqlite_populate.popular(conn)
        with conn:
            segunda = sqlite_populate.popular(conn)
        totais = [conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("user", "ticket", "prediction")]
    criar_banco(banco)
    with closing(sqlite3.connect(banco)) as conn:
        depois = [conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("user", "ticket", "prediction")]

    assert primeira == (8, 8)
    assert segunda == (0, 0)
    assert totais == depois == [3, 8, 13]
