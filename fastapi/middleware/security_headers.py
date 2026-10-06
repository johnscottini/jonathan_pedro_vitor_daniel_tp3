"""Headers de segurança HTTP e CORS (OWASP A05 — Security Misconfiguration).

`main.py` chama `add_security_middlewares(app)`. Os headers são aplicados a
**todas** as respostas, inclusive às de erro — um 401 ou um 404 também precisa
dizer ao navegador que não pode ser exibido em um iframe.

Headers aplicados e por quê:

* `Strict-Transport-Security` — obriga o navegador a só falar HTTPS com este
  domínio, fechando a janela de downgrade para HTTP em que um atacante na rede
  leria a senha enviada ao `/auth/token`.
* `X-Frame-Options: DENY` — a API não pode ser embutida em iframe (clickjacking).
* `X-Content-Type-Options: nosniff` — impede o navegador de "adivinhar" o tipo do
  conteúdo e executar como script algo que devolvemos como JSON.
* `Content-Security-Policy` — a API só devolve JSON, então a política padrão
  bloqueia qualquer carregamento de recurso. Ver a ressalva sobre o `/docs`.
* `Referrer-Policy: no-referrer` — evita vazar a URL da API (e qualquer dado no
  caminho) para sites de terceiros.
* `Permissions-Policy` — desliga APIs de dispositivo que a API nunca usa.
* `Cache-Control: no-store` — respostas podem conter token e dados do ticket;
  não devem ficar em cache de navegador ou proxy.
* `Cross-Origin-Resource-Policy: same-origin` — impede que outra origem embuta a
  resposta da API como recurso. Acrescentado após o primeiro scan do ZAP, que
  apontou a ausência deste header (regra 90004).
* `server` genérico — o valor padrão (`uvicorn`) entrega a stack para quem está
  sondando a API.

**Ressalva sobre o `/docs`:** a CSP restritiva quebraria o Swagger UI, que além
de carregar JS do `cdn.jsdelivr.net` executa um `<script>` inline. Em vez de
afrouxar a política do site inteiro, as rotas de documentação montam a própria
CSP, autorizando o script inline **pelo hash** — ver `routes/docs.py`. Este
middleware preserva a CSP que a rota já tiver definido.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from core.config import CORS_ORIGINS

# CSP da API: ela só devolve JSON, então nada pode ser carregado.
CSP_API = (
    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)

SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Cache-Control": "no-store",
    "X-Permitted-Cross-Domain-Policies": "none",
    # Impede que outros sites embutam/leiam as respostas da API como se fossem
    # um recurso qualquer (apontado pelo ZAP, regra 90004).
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    "server": "api",
}


def add_security_middlewares(app: FastAPI) -> None:
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)

        for header, valor in SECURITY_HEADERS.items():
            response.headers[header] = valor

        # As rotas de documentação montam a própria CSP (com o hash do script
        # inline do Swagger, ver routes/docs.py). Se a resposta já trouxe uma,
        # ela é preservada.
        if "Content-Security-Policy" not in response.headers:
            response.headers["Content-Security-Policy"] = CSP_API

        return response

    # CORS com allowlist explícita. Nunca "*" junto de allow_credentials: essa
    # combinação permitiria que qualquer site fizesse requisições autenticadas
    # em nome do usuário.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )
