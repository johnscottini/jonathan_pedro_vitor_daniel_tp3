"""Ponto de entrada da API (FastAPI).

Responsabilidade deste módulo: montar a aplicação. Ele conhece todos os outros
módulos, e nenhum outro módulo o importa — assim não existe import circular.

Ordem de montagem:
  1. middlewares de segurança (headers + CORS)
  2. rate limiting
  3. handlers de erro padronizados
  4. routers (as rotas em si)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.config import API_VERSION
from core.exception_handlers import register_exception_handlers
from core.limiter import install_rate_limiting
from sqlite_database import init_db
from middleware.security_headers import add_security_middlewares
from routes import auth, docs, health, predict, tickets


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cria tabelas e usuários iniciais quando a aplicação sobe."""
    init_db()
    yield


app = FastAPI(
    title="Customer Support Intent API",
    description=(
        "API do sistema de atendimento ao cliente. Expõe autenticação JWT, "
        "gestão de tickets por usuário e um endpoint de predição de intenção "
        "com saída simulada (o modelo de ML real será integrado em um TP futuro).\n\n"
        "**Como autenticar:** faça `POST /auth/token` com `username` e `password` "
        "(ou clique em **Authorize** e informe as credenciais). As rotas marcadas com "
        "cadeado exigem o header `Authorization: Bearer <token>`.\n\n"
        "**Erros:** toda resposta de erro segue o formato `ErrorResponse` "
        "(`code`, `message`, `path` e, em 422, `fields`)."
    ),
    version=API_VERSION,
    openapi_tags=[
        {"name": "health", "description": "Monitoramento — rota pública."},
        {"name": "auth", "description": "Login e emissão do token JWT (limitado a 5 tentativas/min por IP)."},
        {"name": "predict", "description": "Predição de intenção do texto do ticket — requer token."},
        {"name": "tickets", "description": "Tickets do usuário autenticado, com verificação de dono — requer token."},
    ],
    lifespan=lifespan,
    # /docs é servido por `routes/docs.py`, que monta a CSP com o hash do script
    # inline do Swagger em vez de liberar 'unsafe-inline'. O /redoc foi
    # desativado no TP3 (ver zap/scan_passivo_zap_TP3.md).
    docs_url=None,
    redoc_url=None,
)

# Tarefa 3 (Pessoa 3) — headers de segurança + CORS: ver middleware/security_headers.py
add_security_middlewares(app)

# Tarefa 4 (Pessoa 3) — rate limiting do login: ver core/limiter.py
install_rate_limiting(app)

# Toda resposta de erro sai no formato `models.errors.ErrorResponse`.
register_exception_handlers(app)

app.include_router(docs.router)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(predict.router)
app.include_router(tickets.router)
