from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from core.database import get_session
from core.intencao import prever_intencao
from models.errors import ErrorResponse
from models.predict import PredictRequest, PredictResponse
from models.tables import Prediction, User
from security.jwt import get_current_user

router = APIRouter(tags=["predict"])

@router.post(
    "/predict",
    response_model=PredictResponse,
    status_code=status.HTTP_200_OK,
    summary="Prevê a intenção de um ticket (saída simulada)",
    description=(
        "Recebe o texto de uma mensagem de atendimento e devolve a intenção prevista "
        "com uma confiança. **Nesta versão a saída é simulada** por palavras-chave; o "
        "classificador treinado substitui a lógica no próximo TP, mantendo o mesmo "
        "contrato.\n\n"
        "Cada predição fica registrada com o usuário do token como dono e pode ser "
        "consultada depois em `GET /predictions/{id}`.\n\n"
        "**Corpo:** `{\"text\": \"...\"}`, com texto não vazio e de até 4000 caracteres. Qualquer outro campo devolve 422.\n\n"
        + "**Autenticação:** exige `Authorization: Bearer <token>`, obtido em `POST /auth/token` (no Swagger, use o botão **Authorize**)."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Token ausente, inválido, expirado ou de usuário não autorizado"},
        422: {"model": ErrorResponse, "description": "Corpo da requisição inválido"},
    },
)
def predict(
    payload: PredictRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Prediction:
    """Endpoint protegido, ainda não roda um modelo de ML (ver `core/intencao.py`)."""
    intent, confidence = prever_intencao(payload.text)
    # O dono vem sempre do token, nunca do corpo (que nem aceita `owner_id`).
    prediction = Prediction(
        owner_id=current_user.id, text=payload.text, intent=intent, confidence=confidence
    )
    session.add(prediction)
    session.commit()
    session.refresh(prediction)
    return prediction
