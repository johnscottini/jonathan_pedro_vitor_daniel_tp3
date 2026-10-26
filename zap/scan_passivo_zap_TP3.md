# Auditoria final com OWASP ZAP — scan passivo (TP3)

Análise dos findings da auditoria final da API, com a aplicação FastAPI em
execução. Os relatórios exportados pelo ZAP estão nesta pasta:

| Arquivo | Conteúdo |
|---|---|
| [`zap_report_tp3.html`](zap_report_tp3.html) / [`.json`](zap_report_tp3.json) / [`.md`](zap_report_tp3.md) | Scan da API (todas as rotas do `openapi.json`) — **relatório final** |
| [`zap_baseline_docs_tp3.html`](zap_baseline_docs_tp3.html) / [`.json`](zap_baseline_docs_tp3.json) | Scan da documentação interativa `/docs` — **relatório final**, após as correções |
| [`zap_baseline_docs_tp3_inicial.html`](zap_baseline_docs_tp3_inicial.html) / [`.json`](zap_baseline_docs_tp3_inicial.json) | Primeira execução sobre o `/docs`, **antes** das correções |
| [`tp2/`](tp2/) | Relatórios e análise da auditoria do TP2 (histórico) |

## Como o scan foi executado

| Item | Valor |
|---|---|
| Ferramenta | OWASP ZAP 2.17.0 (imagem oficial `zaproxy/zap-stable`) |
| Modo | **Passivo**: o ZAP só observa as requisições e respostas, sem enviar ataques |
| Alvo 1 — API | `zap-api-scan.py -S` (modo seguro) a partir de `http://host.docker.internal:8000/openapi.json` |
| Alvo 2 — documentação | `zap-baseline.py` (spider + scan passivo) a partir de `http://host.docker.internal:8000/docs` |
| Escopo | `/health`, `/auth/token`, `/predict`, `/tickets`, `/tickets/{id}`, `/docs`, `/openapi.json` |
| Execuções | 25/10/2026: 1º scan do `/docs` às 22:49, correções, 2º scan às 22:53 e scan final da API às 22:54 (horário de Brasília) |

Por que dois alvos: o `zap-api-scan` só visita as rotas descritas no
`openapi.json`, e a página `/docs` não faz parte da especificação. No TP2 apenas
o primeiro alvo foi auditado, por isso os findings da página de documentação só
apareceram agora.

Comandos reproduzíveis (com a API rodando em `localhost:8000`, a partir da raiz do repositório):

```bash
docker run --rm -v "$(pwd)/zap:/zap/wrk:rw" zaproxy/zap-stable zap-api-scan.py \
  -t http://host.docker.internal:8000/openapi.json -f openapi -S \
  -r zap_report_tp3.html -J zap_report_tp3.json -w zap_report_tp3.md -I

docker run --rm -v "$(pwd)/zap:/zap/wrk:rw" zaproxy/zap-stable zap-baseline.py \
  -t http://host.docker.internal:8000/docs \
  -r zap_baseline_docs_tp3.html -J zap_baseline_docs_tp3.json -I
```

## Resumo por severidade

| Severidade | API — scan final | `/docs` — 1º scan | `/docs` — após correções |
|---|---|---|---|
| **High** | 0 | 0 | **0** |
| **Medium** | 0 | **3** | **0** |
| **Low** | 0 | 2 | **0** |
| Informational | 3 | 2 | 2 |
| Regras aprovadas (PASS) | 119 | 62 | 66 |

**Nenhum finding High foi encontrado.** Os **3 findings Medium**, todos na página
`/docs`, foram corrigidos. Os 2 Low da mesma página também foram eliminados. O
scan da API ficou sem nenhum alerta Medium, High ou Low
(`FAIL-NEW: 0 / WARN-NEW: 0`).

## Findings Medium e High

As três correções estão em [`fastapi/routes/docs.py`](../fastapi/routes/docs.py),
marcadas no código com comentários `ZAP TP3: <finding> — corrigido aqui`.

### 1. CSP: Failure to Define Directive with No Fallback (regra 10055)

| Campo | Detalhe |
|---|---|
| **Finding** | A `Content-Security-Policy` do `/docs` não definia a diretiva `form-action` |
| **Severidade** | **Medium** (confiança High) |
| **Risco** | `form-action` é uma das diretivas que **não herdam** de `default-src 'none'`. Sem ela, um formulário injetado na página (por XSS ou por uma dependência do CDN comprometida) poderia enviar dados digitados pelo usuário, como as credenciais do diálogo *Authorize*, para qualquer domínio |
| **Correção** | Acrescentada a diretiva `form-action 'none'` na CSP montada por `_csp_para()`. O Swagger UI não submete formulários (faz o login via `fetch`), então nenhum destino precisa ser liberado |
| **Evidência** | 2º scan do `/docs` sem a regra 10055. O teste `tests/test_headers.py::test_docs_corrige_os_findings_medium_do_zap_tp3` exige `form-action 'none'`. O login pelo botão *Authorize* do Swagger continuou funcionando (verificado no navegador) |

### 2. CSP: style-src unsafe-inline (regra 10055)

| Campo | Detalhe |
|---|---|
| **Finding** | A CSP do `/docs` tinha `style-src ... 'unsafe-inline'` |
| **Severidade** | **Medium** (confiança High) |
| **Risco** | `'unsafe-inline'` permite que qualquer `<style>` ou atributo `style` injetado seja aplicado. Isso abre espaço para ataques de injeção de CSS: exfiltração de dados por seletores de atributo, sobreposição de elementos (UI redressing) e páginas falsas de login desenhadas sobre a documentação |
| **Correção** | `'unsafe-inline'` foi removido: `style-src 'self' https://cdn.jsdelivr.net`. O Swagger UI não precisa dele, porque o CSS vem do CDN (agora com SRI) e os estilos dinâmicos são aplicados via CSSOM, que a CSP não bloqueia. A rota `/redoc` foi removida, porque o ReDoc injeta `<style>` em tempo de execução e só funcionaria com `'unsafe-inline'` |
| **Evidência** | 2º scan sem o alerta. O mesmo teste exige `style-src` sem `unsafe-inline`, e `test_redoc_foi_removido` exige 404 em `/redoc`. No navegador, o `/docs` renderiza sem nenhuma violação de CSP no console |

### 3. Sub Resource Integrity Attribute Missing (regra 90003)

| Campo | Detalhe |
|---|---|
| **Finding** | `<script src=".../swagger-ui-bundle.js">` e `<link href=".../swagger-ui.css">` carregados do `cdn.jsdelivr.net` sem o atributo `integrity` |
| **Severidade** | **Medium** (confiança High) |
| **Risco** | A página executa um JavaScript de terceiro sem conferir o conteúdo. Se o CDN fosse comprometido, ou a versão flutuante `@5` passasse a apontar para um pacote malicioso (ataque de cadeia de suprimentos), o código rodaria na origem da API, com acesso ao token JWT digitado no Swagger (OWASP A08 — Software and Data Integrity Failures) |
| **Correção** | (a) A versão foi fixada em `swagger-ui-dist@5.34.0`, em vez de `@5`. (b) Cada tag ganhou `integrity="sha384-..."` e `crossorigin="anonymous"` (função `_com_sri()`), com o hash SHA-384 do arquivo esperado: se o conteúdo mudar, o navegador não executa. (c) O favicon, que vinha de `fastapi.tiangolo.com`, passou a ser um `data:` embutido |
| **Evidência** | 2º scan sem a regra 90003. O teste exige `integrity="sha384-` e `crossorigin="anonymous"` em toda tag do CDN e proíbe a versão flutuante `@5/` |

## Findings Low (não obrigatórios, corrigidos)

| Finding | Correção |
|---|---|
| Cross-Origin-Embedder-Policy Header Missing (90004) | O `/docs` passou a enviar `Cross-Origin-Embedder-Policy: require-corp`. Funciona porque os arquivos do CDN agora são pedidos em modo CORS (`crossorigin`) |
| Cross-Domain JavaScript Source File Inclusion (10017) | Deixou de ser reportado com o script do CDN protegido por SRI e versão fixa |

## Findings informativos (aceitos)

| Finding | Onde | Por que não é um problema |
|---|---|---|
| Non-Storable Content (10049) | API e `/docs` | Comportamento desejado: todas as respostas saem com `Cache-Control: no-store`, para que tokens e dados de tickets não fiquem em cache de navegador ou proxy |
| Modern Web Application (10109) | `/docs` | Apenas informa que a página é montada por JavaScript (Swagger UI). Não é uma vulnerabilidade |
| A Client Error response code was returned (100000) | API | São os 401/404/422 esperados: o ZAP chamou rotas protegidas sem token e com dados de exemplo |
| Authentication Request Identified (10111) | `/auth/token` | O ZAP identificou o endpoint de login. Ele é protegido por rate limit (429 após 5 tentativas/min por IP) |

## Controles que o scan confirma (já existentes)

As 119 regras aprovadas no scan da API incluem a ausência de vazamento de erro
ou stack trace (90022), os headers anti-clickjacking e `nosniff`, a CSP
restritiva da API (`default-src 'none'`), o isolamento contra Spectre (90004) e a
ausência de banner de servidor. Os comentários sobre esses controles estão em
`fastapi/middleware/security_headers.py` e `fastapi/core/exception_handlers.py`.
