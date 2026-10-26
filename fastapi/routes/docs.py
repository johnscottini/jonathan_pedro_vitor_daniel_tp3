"""Rota de documentação interativa (/docs) com CSP por hash e SRI.

A página gerada pelo FastAPI traz um `<script>` **inline** que inicializa o
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

Como a rota monta a CSP por conta própria, o middleware de segurança
(`middleware/security_headers.py`) respeita o header já definido e não o
sobrescreve.

**Auditoria ZAP do TP3** (`zap/scan_passivo_zap_TP3.md`): o scan passivo da
página `/docs` apontou três findings Medium, todos corrigidos neste arquivo —
procure pelos comentários `ZAP TP3`.

**Sobre o ReDoc:** a rota `/redoc` foi removida no TP3. O ReDoc injeta estilos
inline em tempo de execução e só funciona com `style-src 'unsafe-inline'`, o
mesmo problema corrigido aqui no Swagger. A documentação interativa exigida é a
do `/docs`, então manter uma segunda página só ampliaria a superfície de ataque.
"""

import base64
import hashlib
import re

from fastapi import APIRouter
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

from core.config import API_VERSION

router = APIRouter(include_in_schema=False)

TITULO = "Customer Support Intent API"
OPENAPI_URL = "/openapi.json"

# ZAP TP3: Sub Resource Integrity Attribute Missing (90003, Medium) — corrigido aqui.
# A versão do Swagger UI é fixada (antes era `@5`, que muda sozinha a cada
# release) e cada arquivo carrega o hash SHA-384 do conteúdo esperado. Se o CDN
# for comprometido e servir outro arquivo, o navegador se recusa a executá-lo.
# Para atualizar a versão, recalcule o hash:
#   curl -s <url> | openssl dgst -sha384 -binary | openssl base64 -A
SWAGGER_VERSAO = "5.34.0"
_CDN = f"https://cdn.jsdelivr.net/npm/swagger-ui-dist@{SWAGGER_VERSAO}"
SWAGGER_JS = f"{_CDN}/swagger-ui-bundle.js"
SWAGGER_CSS = f"{_CDN}/swagger-ui.css"
SRI = {
    SWAGGER_JS: "sha384-9Td7MKiIr2S83E1kZyyVi8KdJw/S8CpAvu0llLyMeg0xq/hDGiZJfVn0fV4llCmK",
    SWAGGER_CSS: "sha384-4c3vsE5f+trhFyHrFrLM1fFGUn531NIaC7dcqEWIJdoRQJ5CkJbSuSCwXLpaS1KF",
}

# Favicon embutido: evita carregar uma imagem de um terceiro (fastapi.tiangolo.com)
# a cada abertura da documentação, o que também conflitaria com o COEP abaixo.
FAVICON = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E"

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
        # ZAP TP3: CSP: style-src unsafe-inline (10055, Medium) — corrigido aqui.
        # O Swagger UI não precisa de <style> inline: o CSS vem do CDN (com SRI)
        # e os estilos dinâmicos são aplicados via CSSOM, que a CSP não bloqueia.
        "style-src 'self' https://cdn.jsdelivr.net; "
        "img-src 'self' data:; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "connect-src 'self'; "
        "worker-src blob:; "
        # ZAP TP3: CSP: Failure to Define Directive with No Fallback (10055, Medium)
        # — corrigido aqui. `form-action` não herda de `default-src`; sem ela,
        # um formulário injetado poderia enviar dados para qualquer domínio. O
        # Swagger não submete formulários (usa fetch), então a política é 'none'.
        "form-action 'none'; "
        "frame-ancestors 'none'; base-uri 'none'"
    )


def _com_sri(html: str) -> str:
    """Acrescenta `integrity` e `crossorigin` às tags que carregam do CDN."""
    for url, integridade in SRI.items():
        atributos = f'integrity="{integridade}" crossorigin="anonymous"'
        html = html.replace(f'src="{url}"', f'src="{url}" {atributos}')
        html = html.replace(f'href="{url}"', f'href="{url}" {atributos}')
    return html


@router.get("/docs")
def swagger_ui() -> HTMLResponse:
    original = get_swagger_ui_html(
        openapi_url=OPENAPI_URL,
        title=f"{TITULO} {API_VERSION} — Swagger UI",
        swagger_js_url=SWAGGER_JS,
        swagger_css_url=SWAGGER_CSS,
        swagger_favicon_url=FAVICON,
    )
    html = _com_sri(original.body.decode("utf-8"))
    resposta = HTMLResponse(html)
    resposta.headers["Content-Security-Policy"] = _csp_para(html)
    # Isola a página de documentos de outras origens (finding Low 90004 do ZAP).
    # Funciona porque os arquivos do CDN são pedidos em modo CORS (crossorigin).
    resposta.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
    return resposta
