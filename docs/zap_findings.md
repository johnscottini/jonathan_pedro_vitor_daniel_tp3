# Findings do OWASP ZAP — scan passivo

Análise dos relatórios exportados em [`zap_report.html`](zap_report.html) (versão
final) e [`zap_report_inicial.html`](zap_report_inicial.html) (primeira execução,
antes da correção). Os dados brutos estão em [`zap_report.json`](zap_report.json).

## Como o scan foi executado

| Item | Valor |
|---|---|
| Ferramenta | OWASP ZAP 2.17.0 (imagem oficial `zaproxy/zap-stable`) |
| Script | `zap-api-scan.py` em **modo seguro** (`-S`): spider da especificação + scan **passivo**, sem ataques ativos |
| Alvo | `http://host.docker.internal:8000/openapi.json` (a API rodando localmente, com a especificação OpenAPI como ponto de partida) |
| Escopo | `/health`, `/auth/token`, `/predict`, `/tickets`, `/tickets/{id}` |
| Base de código | commit `d133ab0` + as implementações do TP2 |
| Execuções | 1ª em 05/10/2026 21:58 · 2ª (após correção) em 05/10/2026 22:05 |

Comando reproduzível:

```bash
docker run --rm -v "$(pwd)/docs:/zap/wrk:rw" zaproxy/zap-stable zap-api-scan.py \
  -t http://host.docker.internal:8000/openapi.json -f openapi -S \
  -r zap_report.html -J zap_report.json -I
```

## Resumo

| Severidade | 1º scan | Após correções | Corrigidos | Aceitos |
|---|---|---|---|---|
| **High** | 0 | 0 | — | — |
| **Medium** | 0 | 0 | — | — |
| **Low** | 1 | **0** | 1 | 0 |
| Informational | 3 | 3 | 0 | 3 |
| Regras aprovadas (PASS) | 117 | **118** | | |

## Findings Medium e High

**Nenhum finding de severidade Medium ou High foi reportado em nenhuma das duas
execuções** — os contadores acima vêm direto do relatório do ZAP
(`FAIL-NEW: 0 / WARN-NEW: 0` na execução final).

Isso não é acaso. Os alertas Medium que um scan passivo costuma levantar contra
uma API FastAPI recém-exposta vêm das regras de header ausente, CSP não
definida, falta de proteção contra clickjacking, `X-Content-Type-Options`
ausente, HSTS ausente e banner do servidor expondo a versão. Nenhuma delas
disparou aqui porque todos esses headers são enviados pelo middleware em
[`fastapi/middleware/security_headers.py`](../fastapi/middleware/security_headers.py),
o que pode ser conferido de duas formas independentes do relatório:

```bash
curl -si http://127.0.0.1:8000/health | grep -iE "strict-transport|x-frame|x-content-type|content-security|^server"
```

e pelos testes automatizados em [`tests/test_headers.py`](../tests/test_headers.py),
que falham se qualquer um dos headers obrigatórios deixar de ser enviado —
inclusive nas respostas de erro.

Como não há findings dessas severidades, foram documentados os findings Low e Informational abaixo.

## F01 — Cross-Origin-Resource-Policy Header Missing or Invalid

- **Severidade:** Low (confiança Medium) · regra ZAP 90004
- **Onde:** `GET /health` e `GET /openapi.json` (2 instâncias)
- **Status: CORRIGIDO** — ausente na segunda execução
- **O que foi detectado:** as respostas não traziam o header
  `Cross-Origin-Resource-Policy`.
- **Por que é um problema:** sem esse header, outro site pode embutir a resposta
  da API como se fosse um recurso qualquer (uma imagem, um script). É o vetor
  explorado em ataques de canal lateral do tipo Spectre e em técnicas de
  *cross-site leaks*, em que o atacante não lê a resposta diretamente, mas
  infere o conteúdo a partir de efeitos colaterais do carregamento. O CORS
  controla quem pode **ler** a resposta; o CORP controla quem pode **carregá-la**.
- **Como foi corrigido:** acrescentados
  `Cross-Origin-Resource-Policy: same-origin` e
  `Cross-Origin-Opener-Policy: same-origin` ao middleware de headers, em
  `fastapi/middleware/security_headers.py`.
- **Evidência pós-correção:** a segunda execução do ZAP não reporta mais o
  alerta (de 117 para 118 regras aprovadas, 0 WARN), e o header é verificado
  automaticamente em [`tests/test_headers.py`](../tests/test_headers.py).

## F02 — A Client Error response code was returned by the server

- **Severidade:** Informational · regra ZAP 100000
- **Onde:** `/auth/token`, `/predict`, `/tickets`, `/tickets/10` (5 instâncias)
- **Status: ACEITO** — é o comportamento desejado
- **O que foi detectado:** o ZAP registrou respostas 4xx (401 e 422) ao acessar
  as rotas sem token válido e com corpo incompleto.
- **Por que o ZAP reporta:** a regra apenas sinaliza que houve erro de cliente,
  para o analista verificar se não é um endpoint quebrado.
- **Justificativa do aceite:** esses 4xx **são os controles de segurança
  funcionando**. O ZAP não possui credenciais da API, então toda requisição a
  rota protegida devolve 401 (`Not authenticated`), e a chamada a
  `/tickets/10` devolve 404 porque o recurso não pertence a quem pediu. Transformar esses casos em 2xx seria a vulnerabilidade. Os
  mesmos códigos estão cobertos por testes em
  [`tests/test_seguranca.py`](../tests/test_seguranca.py).

## F03 — Non-Storable Content

- **Severidade:** Informational · regra ZAP 10049
- **Onde:** todas as rotas (5 instâncias)
- **Status: ACEITO** — é consequência de um controle intencional
- **O que foi detectado:** as respostas não podem ser armazenadas em cache.
- **Por que o ZAP reporta:** a regra é informativa e existe para avisar sobre
  possível perda de desempenho por falta de cache.
- **Justificativa do aceite:** o middleware envia `Cache-Control: no-store` de
  propósito. As respostas carregam token JWT e conteúdo de tickets, que podem
  conter dados pessoais do cliente; mantê-las em cache de navegador ou de proxy
  intermediário criaria uma cópia desses dados fora do controle da aplicação. A
  perda de desempenho é irrelevante para o volume desta API.

## F04 — Authentication Request Identified

- **Severidade:** Informational · regra ZAP 10111
- **Onde:** `POST /auth/token`
- **Status: ACEITO** — identificação correta, sem risco
- **O que foi detectado:** o ZAP identificou o endpoint como fluxo de
  autenticação, por causa dos campos `username` e `password`.
- **Por que o ZAP reporta:** é um apontamento informativo que ajuda a configurar
  scans autenticados; não indica falha.
- **Justificativa do aceite:** a identificação está certa e é justamente o que se
  espera de um endpoint OAuth2 Password Flow. O endpoint está protegido por rate
  limiting (429 após 5 tentativas por minuto por IP) e devolve mensagem genérica
  para usuário inexistente e senha errada.

## Riscos conhecidos e aceitos (fora do alcance do scan passivo)

O scan passivo observa tráfego e headers; ele não enxerga decisões de
arquitetura. Estes pontos ficam registrados porque serão relevantes no pentest
do próximo bloco:

1. **Contador de rate limit em memória.** Com mais de uma instância da API, cada
   processo teria seu próprio contador, e o limite efetivo seria multiplicado
   pelo número de instâncias. Aceito nesta entrega (execução single-process); em
   produção, o storage do slowapi apontaria para um Redis compartilhado.
2. **`SECRET_KEY` com valor padrão em desenvolvimento.** A chave é lida de
   variável de ambiente, mas há um valor padrão para a aplicação subir sem
   configuração. Em produção, subir sem `SECRET_KEY` definida deveria ser um
   erro fatal, não um aviso.
3. **CSP própria nas rotas de documentação.** `/docs` e `/redoc` precisam
   carregar o bundle do Swagger/ReDoc do `cdn.jsdelivr.net`, e a página do
   Swagger ainda executa um `<script>` inline. Em vez de liberar
   `'unsafe-inline'` — o atalho que anularia a proteção contra XSS —, essas
   rotas autorizam o script inline **pelo hash**, calculado em tempo de execução
   a partir do HTML gerado (`fastapi/routes/docs.py`). O restante da API mantém
   `default-src 'none'`. Endurecer mais exigiria servir os assets localmente ou
   desabilitar o `/docs` em produção.
4. **HSTS sem HTTPS no ambiente de teste.** O header é enviado, mas o scan rodou
   sobre HTTP local, onde ele não tem efeito prático. O controle só passa a valer
   quando a API estiver atrás de TLS.
5. **Credenciais de desenvolvimento documentadas no README.** Será removida antes de liberar em prod.
