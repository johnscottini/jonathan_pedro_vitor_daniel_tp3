"""Engine e sessão do SQLModel usados pela API.

Toda query da API passa por uma `Session` do SQLModel, ou seja, é parametrizada
pelo SQLAlchemy. Não existe SQL cru (string concatenada) nas rotas — é assim que
a API se defende de SQL Injection (OWASP A03).

A criação e a população do banco ficam fora da API, em `sqlite_database.py` e
`sqlite_populate.py`, escritos com o módulo `sqlite3` da biblioteca padrão.

A dependência `get_session` é o ponto que os testes substituem
(`app.dependency_overrides[get_session]`) para usar um banco em memória.
"""

from typing import Iterator

from sqlmodel import Session, create_engine

import models.tables  # noqa: F401  (import necessário para registrar as tabelas)
from core.config import DATABASE_URL

# `check_same_thread=False` é exigido pelo SQLite quando o FastAPI atende
# requisições em threads diferentes.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, echo=False, connect_args=_connect_args)


def get_session() -> Iterator[Session]:
    """Dependência do FastAPI: uma sessão de banco por requisição."""
    with Session(engine) as session:
        yield session
