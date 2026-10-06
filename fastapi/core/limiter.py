"""Rate limiting do endpoint de autenticação (OWASP A07 — Identification and
Authentication Failures).

**Limite configurado:** 5 tentativas por minuto por IP no `POST /auth/token`
(`RATE_LIMIT_LOGIN`, ajustável por variável de ambiente).

**Justificativa técnica.** Sem limite, o `/auth/token` aceita tentativas na
velocidade que o atacante conseguir enviar, e uma senha fraca cai em minutos.
Com 5 tentativas por minuto, varrer uma lista de mil senhas comuns levaria mais
de três horas por usuário, e um dicionário de um milhão passaria de três meses —
tempo suficiente para que o abuso apareça em qualquer monitoramento. O custo
para quem é legítimo é nulo: um usuário que lembra a senha erra duas ou três
vezes, no máximo.

**Por que por IP e não por usuário:** limitar por nome de usuário permitiria que
um atacante bloqueasse a conta de terceiros só errando a senha de propósito,
transformando a proteção em negação de serviço. O IP pune a origem do abuso.

**Limitação conhecida:** o contador vive na memória do processo. Com mais de uma
instância da API, cada uma teria seu próprio contador — em produção, o storage
do slowapi apontaria para um Redis compartilhado. Registrado como limitação
aceita em `docs/zap_findings.md`.
"""

from typing import Callable, TypeVar

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from core.config import RATE_LIMIT_LOGIN
from models.errors import ErrorResponse

F = TypeVar("F", bound=Callable)

limiter = Limiter(key_func=get_remote_address)


def login_rate_limit(endpoint: F) -> F:
    """Decorator aplicado ao `POST /auth/token`.

    O endpoint decorado precisa receber `request: Request` — é de onde o slowapi
    tira o IP de origem.
    """
    return limiter.limit(RATE_LIMIT_LOGIN)(endpoint)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """429 no mesmo formato `ErrorResponse` dos demais erros da API."""
    corpo = ErrorResponse(
        code="rate_limited",
        message=(
            "Muitas tentativas de autenticação. "
            f"Limite: {RATE_LIMIT_LOGIN}. Tente novamente mais tarde."
        ),
        path=request.url.path,
    )
    return JSONResponse(
        status_code=429,
        content=corpo.model_dump(exclude_none=True),
        # Retry-After é o header padrão para dizer ao cliente quando voltar.
        headers={"Retry-After": "60"},
    )


def install_rate_limiting(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


def set_rate_limiting_enabled(enabled: bool) -> None:
    """Liga/desliga o limite. Usado por `tests/conftest.py`."""
    limiter.enabled = enabled


def reset_rate_limiting() -> None:
    """Zera os contadores. Evita que um teste influencie o seguinte."""
    limiter.reset()
