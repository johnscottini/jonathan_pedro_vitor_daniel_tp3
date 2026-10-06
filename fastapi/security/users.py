"""Usuários da API: hash de senha, consulta e autenticação.

No TP1 havia um único usuário `admin` fixo no código. No TP2 os usuários passam
a viver na tabela `User` (SQLModel): a verificação de ownership (BOLA, OWASP
A01) só existe se houver mais de um usuário, cada um dono dos seus tickets.

Senhas nunca são guardadas em texto: só o hash bcrypt (OWASP A02).
"""

from typing import Optional

import bcrypt
from sqlmodel import Session, select

from models.tables import User

ADMIN_USERNAME = "admin"

# Usuários criados na primeira execução. São credenciais de desenvolvimento,
# documentadas no README; em produção viriam de um fluxo de cadastro.
SEED_USERS = {
    ADMIN_USERNAME: "admin123",
    "alice": "alice123",
    "bob": "bob123",
}

# Hash descartável usado quando o usuário não existe: assim a resposta leva o
# mesmo tempo com usuário inexistente e com senha errada, e o atacante não
# consegue descobrir quais usuários existem medindo o tempo de resposta
# (enumeração por timing).
_DUMMY_HASH = bcrypt.hashpw(b"usuario-inexistente", bcrypt.gensalt())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def get_user(session: Session, username: str) -> Optional[User]:
    """Consulta parametrizada pelo SQLModel — nunca SQL concatenado (OWASP A03)."""
    return session.exec(select(User).where(User.username == username)).first()


def authenticate_user(session: Session, username: str, password: str) -> Optional[User]:
    """Devolve o `User` quando as credenciais conferem, senão `None`."""
    user = get_user(session, username)
    if user is None:
        bcrypt.checkpw(password.encode("utf-8"), _DUMMY_HASH)
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def criar_usuarios_iniciais(session: Session) -> None:
    """Cria os usuários do `SEED_USERS` que ainda não existirem."""
    criados = []
    for username, password in SEED_USERS.items():
        if get_user(session, username) is None:
            session.add(User(username=username, hashed_password=hash_password(password)))
            criados.append(username)
    if criados:
        session.commit()
        print(f"[seed] usuários criados: {', '.join(criados)}")
