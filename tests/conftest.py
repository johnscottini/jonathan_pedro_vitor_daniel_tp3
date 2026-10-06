"""Infraestrutura de testes — montada na fase 0, usada pelas Pessoas 2 e 3.

Os nomes das fixtures fazem parte do contrato: `session`, `client`, `alice`,
`bob`, `token_alice`, `token_bob`, `ticket_de_bob`. Se precisar de outra
fixture, adicione aqui em vez de recriar a mesma coisa em cada arquivo.

Cada teste roda contra um SQLite **em memória**, isolado: o banco real
(`fastapi/app.db`) nunca é tocado.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from core.limiter import set_rate_limiting_enabled
from db import get_session
from main import app
from models.tables import Ticket, User
from security.users import ADMIN_USERNAME, hash_password

SENHA_PADRAO = "senha-de-teste-123"


@pytest.fixture(name="session")
def session_fixture():
    """Banco novo e vazio, em memória, para cada teste."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # mantém a mesma conexão (senão o :memory: some)
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session):
    """Cliente HTTP apontando para o banco de teste, com rate limit desligado."""
    app.dependency_overrides[get_session] = lambda: session
    set_rate_limiting_enabled(False)
    # TestClient sem `with` de propósito: assim o lifespan (init_db) não roda e
    # os testes não criam o banco real em disco.
    yield TestClient(app)
    app.dependency_overrides.clear()
    set_rate_limiting_enabled(True)


def criar_usuario(session: Session, username: str, password: str = SENHA_PADRAO) -> User:
    user = User(username=username, hashed_password=hash_password(password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def obter_token(client: TestClient, username: str, password: str = SENHA_PADRAO) -> str:
    response = client.post(
        "/auth/token", data={"username": username, "password": password}
    )
    assert response.status_code == 200, f"login de {username} falhou: {response.text}"
    return response.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": "Bearer " + token}


@pytest.fixture
def alice(session) -> User:
    return criar_usuario(session, "alice")


@pytest.fixture
def bob(session) -> User:
    return criar_usuario(session, "bob")


@pytest.fixture
def admin(session) -> User:
    """Usuário administrativo — usado nos testes de validação do JWT."""
    return criar_usuario(session, ADMIN_USERNAME)


@pytest.fixture
def token_alice(client, alice) -> str:
    return obter_token(client, alice.username)


@pytest.fixture
def token_bob(client, bob) -> str:
    return obter_token(client, bob.username)


@pytest.fixture
def ticket_de_bob(session, bob) -> Ticket:
    """Um ticket que pertence ao bob — a vítima do teste de BOLA."""
    ticket = Ticket(
        owner_id=bob.id,
        subject="Cobrança duplicada na fatura",
        description="Fui cobrado duas vezes pelo mesmo pedido.",
        ticket_type="Billing inquiry",
        priority="High",
        channel="Email",
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket
