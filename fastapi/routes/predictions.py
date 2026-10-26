"""Rotas de consulta às predições — ownership / BOLA (OWASP A01).

Toda predição feita em `POST /predict` é gravada na tabela `prediction` com o
`owner_id` do usuário do token. Aqui valem as mesmas regras dos tickets:

1. A listagem filtra por `Prediction.owner_id == current_user.id`.
2. Buscar uma predição de outro usuário devolve **404**, não 403: o 403
   confirmaria que aquele ID existe (enumeração de identificadores).

As consultas usam `select()`/`session.get()` do SQLModel (SQL parametrizado).
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlmodel import Session, select

from core.database import get_session
from models.errors import ErrorResponse
from models.predict import PredictionRead
from models.tables import Prediction, User
from security.jwt import get_current_user

router = APIRouter(prefix="/predictions", tags=["predict"])

_AUTH = (
    "**Autenticação:** exige `Authorization: Bearer <token>`, obtido em "
    "`POST /auth/token` (no Swagger, use o botão **Authorize**)."
)


@router.get(
    "",
    response_model=List[PredictionRead],
    summary="Lista as predições do usuário autenticado",
    description=(
        "Devolve somente as predições cujo dono é o usuário do token, em ordem de ID. "
        "Predições de outros usuários nunca aparecem.\n\n" + _AUTH
    ),
    responses={401: {"model": ErrorResponse, "description": "Token ausente, inválido ou expirado"}},
)
def listar_predictions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> List[Prediction]:
    consulta = (
        select(Prediction).where(Prediction.owner_id == current_user.id).order_by(Prediction.id)
    )
    return list(session.exec(consulta))


@router.get(
    "/{prediction_id}",
    response_model=PredictionRead,
    summary="Busca uma predição por ID (somente do próprio usuário)",
    description=(
        "Devolve a predição pelo ID, desde que ela pertença ao usuário do token. "
        "Predição inexistente e predição de outro usuário recebem a **mesma** resposta "
        "404, para não revelar quais IDs existem (proteção contra BOLA).\n\n" + _AUTH
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Token ausente, inválido ou expirado"},
        404: {"model": ErrorResponse, "description": "Predição inexistente ou de outro usuário"},
        422: {"model": ErrorResponse, "description": "ID inválido"},
    },
)
def obter_prediction(
    prediction_id: int = Path(..., ge=1, description="ID da predição", examples=[1]),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Prediction:
    prediction = session.get(Prediction, prediction_id)

    # Verificação de ownership: inexistente e alheia respondem exatamente igual.
    if prediction is None or prediction.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Predição não encontrada",
        )

    return prediction
