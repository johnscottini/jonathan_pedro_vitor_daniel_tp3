"""Rotas de documentação (/docs e /redoc) com CSP por hash.

As páginas geradas pelo FastAPI trazem um `<script>` **inline** que inicializa o
Swagger UI. Uma CSP com `script-src 'self' https://cdn.jsdelivr.net` bloqueia
esse script, e a página abre em branco.

Há três saídas possíveis:

1. acrescentar `'unsafe-inline'` ao `script-src` — resolve, mas desliga
   justamente a proteção contra XSS que a CSP existe para dar, e é o primeiro
   item que um pentest aponta;
2. usar `nonce`, que exigiria reescrever o HTML da documentação a cada
   requisição;
3. **autorizar o script pelo hash do seu conteúdo** — foi o escolhido.

O hash é calculado em tempo de execução, a partir do HTML que o próprio FastAPI
gera. Assim ele continua correto quando a versão do FastAPI mudar o script
inline, sem ninguém precisar atualizar uma constante na mão.

Como as rotas montam a CSP por conta própria, o middleware de segurança
(`middleware/security_headers.py`) respeita o header já definido e não o
sobrescreve.

**Sobre o ReDoc:** a página funciona e é navegável, mas a CSP bloqueia dois
recursos de terceiros meramente cosméticos — a fonte Montserrat/Roboto hospedada
no Google Fonts e o logotipo do ReDoc no CDN `cdn.redoc.ly`. O bloqueio aparece
como aviso no console do navegador e é **deliberado**: liberar esses domínios
entregaria o IP de quem abre a documentação a dois terceiros, em troca de fonte
e logotipo. O ReDoc cai para as fontes do sistema e segue utilizável.
"""

import base64
import hashlib
import re

from fastapi import APIRouter
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse

from core.config import API_VERSION

router = APIRouter(include_in_schema=False)

TITULO = "Customer Support Intent API"
OPENAPI_URL = "/openapi.json"

# <script> sem atributo src, ou seja, com código embutido na página.
_SCRIPT_INLINE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL)


def _hash_csp(conteudo: str) -> str:
    digest = hashlib.sha256(conteudo.encode("utf-8")).digest()
    return "'sha256-" + base64.b64encode(digest).decode("ascii") + "'"


def _csp_para(html: str) -> str:
    """Monta a CSP da página autorizando cada script inline pelo hash."""
    hashes = " ".join(_hash_csp(trecho) for trecho in _SCRIPT_INLINE.findall(html))
    return (
        "default-src 'none'; "
        f"script-src 'self' https://cdn.jsdelivr.net {hashes}; "
        "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
        "img-src 'self' https://fastapi.tiangolo.com data:; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "connect-src 'self'; "
        "worker-src blob:; "
        "frame-ancestors 'none'; base-uri 'none'"
    )


def _com_csp(resposta: HTMLResponse) -> HTMLResponse:
    html = resposta.body.decode("utf-8")
    resposta.headers["Content-Security-Policy"] = _csp_para(html)
    return resposta


@router.get("/docs")
def swagger_ui() -> HTMLResponse:
    return _com_csp(
        get_swagger_ui_html(openapi_url=OPENAPI_URL, title=f"{TITULO} {API_VERSION} — Swagger UI")
    )


@router.get("/redoc")
def redoc() -> HTMLResponse:
    return _com_csp(
        get_redoc_html(openapi_url=OPENAPI_URL, title=f"{TITULO} {API_VERSION} — ReDoc")
    )
