"""Emissão e validação de JWT + dependência `OAuth2PasswordBearer`.

Validação do token em `get_current_user`, nesta ordem:

1. **Assinatura** (HS256 com a `SECRET_KEY`): detecta token forjado ou adulterado.
2. **Expiração**: `exp` é obrigatório (`require_exp`) e verificado; token vencido
   é recusado mesmo com assinatura válida.
3. **Autorização do `sub`**: assinatura válida não basta. O `sub` precisa
   corresponder a um usuário existente na base — é o que impede que um token
   bem assinado para qualquer outro `sub` (emitido por outro serviço que
   compartilhe a chave, ou para um usuário já removido) continue valendo.

A checagem (3) foi introduzida na correção do TP1, quando só se verificava se o
`sub` existia no payload. Ao migrar para a tabela `User`, ela deixou de comparar
com uma constante e passou a consultar o banco — o controle é o mesmo.
"""

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlmodel import Session

from core.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY
from db import get_session
from models.tables import User
from security.users import get_user

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# Claims que o token DEVE trazer para ser aceito.
_DECODE_OPTIONS = {
    "verify_signature": True,
    "verify_exp": True,
    "require_exp": True,
    "require_sub": True,
}


def create_access_token(subject: str, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    issued_at = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # (1) assinatura e (2) expiração
    try:
        payload = jwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM], options=_DECODE_OPTIONS
        )
    except JWTError:
        raise credentials_exception

    # (3) o `sub` corresponde a um usuário autorizado existente?
    username = payload.get("sub")
    if not isinstance(username, str):
        raise credentials_exception

    user = get_user(session, username)
    if user is None:
        raise credentials_exception

    return user
