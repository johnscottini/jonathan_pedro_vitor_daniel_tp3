"""Engine, sessão e inicialização do banco (SQLModel + SQLite).

Toda query do projeto passa por uma `Session` do SQLModel, ou seja, é
parametrizada pelo SQLAlchemy. Não existe SQL cru (string concatenada) em
lugar nenhum do código — é assim que a API se defende de SQL Injection
(OWASP A03). Se em algum momento parecer necessário escrever SQL na mão,
converse com o time antes.

A dependência `get_session` é o ponto que os testes substituem
(`app.dependency_overrides[get_session]`) para usar um banco em memória.
"""

from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

import models.tables  # noqa: F401  (import necessário para registrar as tabelas)
from core.config import DATABASE_URL

# `check_same_thread=False` é exigido pelo SQLite quando o FastAPI atende
# requisições em threads diferentes.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, echo=False, connect_args=_connect_args)


def init_db() -> None:
    """Cria as tabelas e os usuários iniciais. Chamado no startup da aplicação."""
    SQLModel.metadata.create_all(engine)

    # Import local: `security.users` importa `models.tables`, e importar aqui no
    # topo criaria um ciclo com `security.jwt`, que depende de `db.get_session`.
    from security.users import criar_usuarios_iniciais

    with Session(engine) as session:
        criar_usuarios_iniciais(session)


def get_session() -> Iterator[Session]:
    """Dependência do FastAPI: uma sessão de banco por requisição."""
    with Session(engine) as session:
        yield session
