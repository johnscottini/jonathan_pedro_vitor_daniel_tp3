# Auditoria final com OWASP ZAP — scan passivo (TP3)

## Execução

| Item | Valor |
|---|---|
| Ferramenta | OWASP ZAP 2.17.0 (`zaproxy/zap-stable`), scan passivo |
| Alvo 1 — API | `zap-api-scan.py -S` a partir de `/openapi.json` (todas as rotas da API) |
| Alvo 2 — documentação | `zap-baseline.py` a partir de `/docs` (página que não faz parte do `openapi.json`) |
| Datas | 25/10/2026: scan inicial, correções e novo scan. 26/10/2026: auditoria repetida após as alterações da API (tabela `prediction`, rotas `/predictions` e rate limit de 10/min) |

Relatórios finais: [`zap_report_tp3.html`](zap_report_tp3.html) (API) e
[`zap_baseline_docs_tp3.html`](zap_baseline_docs_tp3.html) (`/docs`). O relatório
anterior às correções é o [`zap_baseline_docs_tp3_inicial.html`](zap_baseline_docs_tp3_inicial.html).

```bash
docker run --rm -v "$(pwd)/zap:/zap/wrk:rw" zaproxy/zap-stable zap-api-scan.py \
  -t http://host.docker.internal:8000/openapi.json -f openapi -S \
  -r zap_report_tp3.html -J zap_report_tp3.json -w zap_report_tp3.md -I

docker run --rm -v "$(pwd)/zap:/zap/wrk:rw" zaproxy/zap-stable zap-baseline.py \
  -t http://host.docker.internal:8000/docs \
  -r zap_baseline_docs_tp3.html -J zap_baseline_docs_tp3.json -I
```

## Resumo por severidade

| Severidade | API (final) | `/docs` (inicial) | `/docs` (final) |
|---|---|---|---|
| High | 0 | 0 | 0 |
| Medium | 0 | 3 | 0 |
| Low | 0 | 2 | 0 |
| Informational | 3 | 2 | 2 |

Não houve findings High. Os 3 Medium estavam na página `/docs` e foram
corrigidos em [`fastapi/routes/docs.py`](../fastapi/routes/docs.py), onde estão
marcados com o comentário `ZAP TP3`.

## Findings Medium

### 1. CSP: Failure to Define Directive with No Fallback (10055)

| Campo | Detalhe |
|---|---|
| Severidade | Medium |
| Problema | A CSP do `/docs` não definia `form-action`, diretiva que não herda o valor de `default-src` |
| Risco | Um formulário injetado na página poderia enviar dados do usuário, como as credenciais digitadas no Swagger, para outro domínio |
| Correção | Adicionado `form-action 'none'` à CSP |
| Evidência | Regra ausente no scan final; teste `test_docs_corrige_os_findings_medium_do_zap_tp3`; login pelo *Authorize* do Swagger continua funcionando |

### 2. CSP: style-src unsafe-inline (10055)

| Campo | Detalhe |
|---|---|
| Severidade | Medium |
| Problema | A CSP do `/docs` permitia `style-src 'unsafe-inline'` |
| Risco | Estilos injetados seriam aplicados, permitindo sobrepor elementos da página ou extrair dados por CSS |
| Correção | Removido `'unsafe-inline'`; o CSS do Swagger vem do CDN. O `/redoc` foi desativado, pois só funciona com essa permissão |
| Evidência | Regra ausente no scan final; o mesmo teste e `test_redoc_foi_removido`; página sem erros de CSP no navegador |

### 3. Sub Resource Integrity Attribute Missing (90003)

| Campo | Detalhe |
|---|---|
| Severidade | Medium |
| Problema | O JS e o CSS do Swagger eram carregados do CDN sem o atributo `integrity` |
| Risco | Se o arquivo no CDN fosse alterado, o código malicioso rodaria na página da API, com acesso ao token do usuário |
| Correção | Versão fixada (`swagger-ui-dist@5.34.0`) e `integrity="sha384-..."` com `crossorigin="anonymous"` em cada arquivo |
| Evidência | Regra ausente no scan final; o teste verifica `integrity` em todas as tags do CDN |

## Findings Low e informativos

- Low, corrigidos: Cross-Origin-Embedder-Policy ausente (90004), resolvido com
  o header `require-corp` no `/docs`; Cross-Domain JavaScript Inclusion (10017),
  que deixou de aparecer com a versão fixa e o SRI.
- Informativos, aceitos:
  - Non-Storable Content (10049): é o `Cache-Control: no-store` configurado de propósito.
  - Modern Web Application (10109): indica apenas que o Swagger é uma página JavaScript.
  - Client Error response (100000): são os 401/404/422 esperados nas rotas protegidas.
  - Authentication Request (10111): identifica o login, protegido por rate limit.
