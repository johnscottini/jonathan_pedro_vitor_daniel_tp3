from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from core.limiter import login_rate_limit
from db import get_session
from models.auth import Token
from models.errors import ErrorResponse
from security.jwt import create_access_token
from security.users import authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/token",
    response_model=Token,
    summary="Autentica o usuário e emite um token JWT",
    responses={
        401: {"model": ErrorResponse, "description": "Usuário ou senha incorretos"},
        422: {"model": ErrorResponse, "description": "Formulário inválido"},
        429: {"model": ErrorResponse, "description": "Tentativas de login em excesso"},
    },
)
@login_rate_limit
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    """Autentica o usuário contra a tabela `User` e emite um JWT.

    O parâmetro `request` existe porque o rate limiter (slowapi) precisa dele
    para identificar o IP de origem — não remover.

    A mensagem de erro é a mesma para usuário inexistente e senha errada: dizer
    qual dos dois falhou entregaria ao atacante a lista de usuários válidos.
    """
    user = authenticate_user(session, form_data.username, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(subject=user.username)
    return Token(access_token=access_token)
