# Contrato do TP2 — decisões da fase 0

Documento de referência do time. Tudo o que está aqui **já foi decidido e já está
no código** (`main`): ninguém precisa reinventar nada, e mudar qualquer item
abaixo exige avisar as outras duas pessoas, porque quebra o trabalho delas.

- **Repositório:** branch `main` já contém o esqueleto.
- **Python:** 3.11+ (o código roda em 3.9, mas padronizem a versão para evitar surpresa).

---

## 1. Divisão de responsabilidades

| Pessoa | Tarefas do enunciado | Arquivos que essa pessoa edita |
|---|---|---|
| **Pessoa 1 — EDA** | 1 e 7 | `eda/eda.ipynb`, `docs/relatorio_eda.md`, `eda/requirements.txt` |
| **Pessoa 2 — Dados e autorização** | 2 e 6 | `fastapi/db.py` (seed), `fastapi/models/*`, `fastapi/routes/tickets.py`, `fastapi/security/*`, `tests/*` |
| **Pessoa 3 — Hardening e auditoria** | 3, 4 e 5 | `fastapi/middleware/security_headers.py`, `fastapi/core/limiter.py`, `docs/zap_findings.md`, `docs/zap_report.html` |

**Arquivos congelados** (definidos na fase 0, ninguém altera sem combinar):
`fastapi/main.py`, `fastapi/core/config.py`, `fastapi/models/tables.py`,
`fastapi/models/ticket.py`, `fastapi/requirements*.txt`, `pytest.ini`,
`tests/conftest.py`.

> O `main.py` já chama `add_security_middlewares(app)` e `install_rate_limiting(app)`,
> e o `routes/auth.py` já está decorado com `@login_rate_limit` e recebe
> `request: Request`. Ou seja: **a Pessoa 3 implementa só os dois módulos dela** e
> não encosta em `main.py` nem em `routes/auth.py`. Era o principal ponto de
> conflito de merge.

---

## 2. Modelo de dados (já implementado em `fastapi/models/tables.py`)

```python
class User(SQLModel, table=True):
    id: int | None            # PK
    username: str             # único, indexado, máx. 50
    hashed_password: str      # bcrypt

class Ticket(SQLModel, table=True):
    id: int | None            # PK
    owner_id: int             # FK -> user.id, indexado  <-- base do controle de BOLA
    subject: str              # máx. 200
    description: str          # máx. 4000
    ticket_type: str          # máx. 50   (ex.: "Billing inquiry")
    priority: str = "Low"
    channel: str = "Email"
    status: str = "Open"
    created_at: datetime      # UTC
```

Os nomes dos campos espelham as colunas do dataset do Kaggle, para o TP do
modelo de classificação reaproveitar sem tradução.

- **Banco:** SQLite em `fastapi/app.db` (já está no `.gitignore`).
- **Usuários iniciais (seed):** `alice` e `bob`, senha em hash bcrypt, criados no
  `init_db()`. Manter também o `admin` do TP1, se quiserem, mas sem senha fraca.
- **SQL cru é proibido.** Só `select()`/`session.get()` do SQLModel, que já são
  queries parametrizadas (OWASP A03 — Injection).

---

## 3. Contrato de autenticação

- O `sub` do JWT guarda o **`username`**.
- `security/jwt.py::get_current_user` passa a devolver o objeto **`User`**
  (hoje devolve `str`) — precisa de `Depends(get_session)`.
- A `SECRET_KEY` sai do código e vem de `core.config` / variável de ambiente.
- Expiração do token: 30 minutos (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- **Não remover a validação do `sub`** (correção do TP1, Q6): hoje
  `get_current_user` verifica assinatura, expiração **e** se o `sub` é o usuário
  autorizado. Com a tabela `User`, essa terceira checagem vira
  `select(User).where(User.username == sub)` e um 401 quando não encontra — o
  controle continua existindo, só muda a fonte da verdade. Os testes em
  `tests/test_auth_jwt.py` cobrem isso e precisam continuar passando.

---

## 4. Rotas e códigos de resposta

| Método | Rota | Body | Sucesso |
|---|---|---|---|
| POST | `/auth/token` | form OAuth2 | 200 `Token` |
| GET | `/health` | — | 200 |
| POST | `/predict` | `PredictRequest` | 200 `PredictResponse` |
| POST | `/tickets` | `TicketCreate` | 201 `TicketRead` |
| GET | `/tickets` | — | 200 `List[TicketRead]` (só do usuário logado) |
| GET | `/tickets/{id}` | — | 200 `TicketRead` |

**Tabela única de erros** — testes, ZAP e documentação usam estes números:

| Situação | Status |
|---|---|
| Sem token / token inválido ou expirado | **401** |
| Recurso existe mas é de outro usuário | **404** (não 403: 403 confirma que o ID existe) |
| Campo extra ou inválido no body | **422** |
| Estourou o rate limit do login | **429** |

Toda resposta de erro sai no formato `models/errors.py::ErrorResponse`
(`code`, `message`, `path` e, em 422, `fields`), gerado pelos handlers em
`core/exception_handlers.py` — não devolver `{"detail": ...}` solto nem montar
JSON de erro na mão dentro das rotas. Cada rota declara esses retornos em
`responses=` para que apareçam no Swagger.

Regras invioláveis:
- `owner_id` nunca vem do body; sempre de `current_user.id`.
- Todo schema de **entrada** herda de `models/base.py::StrictModel`
  (`extra="forbid"`). Falta aplicar em `PredictRequest` — tarefa da Pessoa 2.

---

## 5. Configuração (`fastapi/core/config.py` + `.env.example`)

| Variável | Default | Dono |
|---|---|---|
| `SECRET_KEY` | valor de dev | Pessoa 2 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Pessoa 2 |
| `DATABASE_URL` | `sqlite:///fastapi/app.db` | Pessoa 2 |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Pessoa 3 |
| `RATE_LIMIT_LOGIN` | `5/minute` | Pessoa 3 |

**Rate limit — decisão e justificativa (documentar no README):** 5 tentativas por
minuto por IP no `POST /auth/token`. Um usuário legítimo erra a senha 2 ou 3
vezes, no máximo; um ataque de força bruta com 5 tentativas/minuto levaria anos
para varrer um dicionário pequeno. O limite é por IP porque limitar por usuário
permitiria que o atacante travasse a conta de um terceiro (negação de serviço).

---

## 6. Testes

- Rodar **da raiz do repositório**: `pytest tests/`.
- `pytest.ini` coloca `fastapi/` no `pythonpath` — a pasta tem o mesmo nome da
  biblioteca, e sem isso o `import fastapi` pega a pasta errada. Já validado.
- Cada teste usa SQLite **em memória**; o `app.db` real nunca é tocado.
- Fixtures já prontas em `tests/conftest.py` (nomes fazem parte do contrato):
  `session`, `client`, `alice`, `bob`, `token_alice`, `token_bob`, `ticket_de_bob`,
  além dos helpers `criar_usuario`, `obter_token` e `auth_header`.
- O rate limit é desligado automaticamente durante os testes
  (`core/limiter.py::set_rate_limiting_enabled`), senão o login em série
  derrubaria a suíte com 429.
- Os 3 testes obrigatórios já estão escritos em `tests/test_seguranca.py`, com
  `skip`. A Pessoa 2 remove o `pytestmark` conforme implementa as rotas.
- **Teste do 429 (obrigatório para a rubrica).** Como a suíte desliga o rate
  limit, nada provaria o 429 sem um teste que o ligue de volta. O esqueleto está
  em `tests/test_rate_limit.py`, também com `skip`: a Pessoa 3 liga o limiter na
  própria fixture do teste, dispara mais tentativas do que o limite e exige 429
  na última. É a evidência que vale mais do que um print de `curl`, porque roda
  junto com `pytest tests/`.
- Testes que já existem e **não podem quebrar**: `tests/test_smoke.py`,
  `tests/test_contrato_erros.py` (formato padronizado de erro) e
  `tests/test_auth_jwt.py` (assinatura, expiração e validação do `sub`) — estes
  dois últimos são as correções do retorno do TP1.

---

## 7. EDA — o que precisa ser decidido pela Pessoa 1

> Atualizado após o retorno do professor no TP1: as hipóteses da seção 6 do
> notebook foram reescritas e cada uma já traz o teste que a verifica.

**Decisão:** o teste de hipótese formal exigido pelo TP2 é o da **H2**, com
**Mann-Whitney**:

> Entre os tickets `Closed`, a satisfação do cliente (`Customer Satisfaction
> Rating`) difere entre tickets de intenção **técnica** e de intenção
> **comercial**?

Mann-Whitney em vez de t-test porque a nota de satisfação é ordinal de 1 a 5 e
não tem distribuição normal. Interpretar o p-valor em linguagem acessível e —
importante — comentar que, sendo um dataset sintético, um resultado não
significativo é um achado esperado e igualmente válido de reportar.

As demais hipóteses pedem **qui-quadrado** e podem entrar como análise
complementar (a H3, em especial, já tem p ≈ 0,98 e é o achado de maior impacto
para a modelagem: os dois campos de rótulo são independentes entre si).

### Antes do heatmap: preparar as variáveis numéricas

**Atenção, senão o heatmap sai vazio.** O dataset tem apenas **duas** colunas
numéricas de origem — `Customer Age` e `Customer Satisfaction Rating` — e uma
matriz de correlação 2×2 não demonstra a rubrica. Monte o conjunto numérico
antes de chamar o `sns.heatmap`, usando as derivadas que o notebook já cria na
seção 4 e mais algumas:

| Variável | Origem |
|---|---|
| `Customer Age` | original |
| `Customer Satisfaction Rating` | original (só tickets `Closed`) |
| `description_length` | já criada na seção 4 |
| `purchase_year`, `purchase_month` | já criadas na seção 4 |
| `priority_ordinal` | codificar `Ticket Priority`: Low=1, Medium=2, High=3, Critical=4 |
| `is_closed`, `has_satisfaction_rating` | já criadas na seção 4 (booleanas → int) |
| `horas_ate_primeira_resposta` | opcional: `First Response Time` − `Date of Purchase`, **sempre com a ressalva** da seção 3 (os timestamps do dataset são causalmente inconsistentes) |

Use `df_num.corr()` com `annot=True` e comente o resultado: correlações próximas
de zero entre quase tudo são o esperado aqui, e isso **é** um achado — basta
interpretá-lo, não maquiá-lo.

### Checklist da Pessoa 1 (cada item é uma rubrica)

- [ ] Heatmap de correlação com `seaborn`, sobre a matriz numérica preparada acima
- [ ] Pelo menos 2 scatter plots relevantes
- [ ] Teste de hipótese com SciPy, com o **p-valor interpretado em texto**
- [ ] Narrativa em linguagem acessível que cite **explicitamente** a hipótese do
      TP1 que está sendo testada (ex.: "a H2 formulada no TP1 dizia que…")
- [ ] `docs/relatorio_eda.md` com as seções problema / dados / análise /
      insights / limitações / próximos passos
- [ ] Na seção de próximos passos, **enunciar a pergunta de classificação do
      TP3** e ligar cada insight a ela — inclusive qual coluna será o alvo do
      classificador, decisão que a H3 torna inevitável

---

## 8. Organização do trabalho

**Branches:** `feat/eda` (Pessoa 1), `feat/bola-sqlmodel` (Pessoa 2),
`feat/hardening` (Pessoa 3). PR para `main` com `pytest tests/` passando e
revisão de pelo menos uma outra pessoa.

**Ordem obrigatória:** o scan do ZAP (tarefa 5) só pode rodar depois que as
partes das Pessoas 2 e 3 estiverem juntas na `main`. Combinem uma data-limite
para esse merge — é o gargalo da entrega.

**Revisão cruzada no final:** Pessoa 1 revisa o hardening, Pessoa 2 revisa a EDA,
Pessoa 3 revisa as rotas e os testes.

**Entregáveis (checklist do enunciado):**

- [x] `eda/eda.ipynb` com heatmap, scatter plots e teste de hipótese interpretado (seção 7)
- [x] API com `extra="forbid"`, SQLModel, ownership, headers, CORS e rate limit
- [x] `docs/zap_report.html` + `docs/zap_findings.md`
- [x] `pytest tests/` passando — 25 testes, incluindo os 3 obrigatórios e o do 429
- [x] `docs/relatorio_eda.md` com as 6 seções e a ligação explícita com o TP3
- [x] README atualizado para o TP2 (estrutura, como rodar, limite de rate e justificativa)

**Dono do README final:** Pessoa 3 — já vai escrever a justificativa do rate
limit, então centraliza a atualização e as Pessoas 1 e 2 só revisam.

---

## 9. Mapa das rubricas

Cada rubrica da avaliação, quem a demonstra e qual artefato serve de evidência.
Antes de entregar, confira esta tabela de cima a baixo.

| Rubrica | Dono | Evidência no repositório |
|---|---|---|
| Heatmap de correlação com seaborn | Pessoa 1 | `eda/eda.ipynb`, com a matriz numérica preparada (seção 7 deste contrato) |
| Teste de hipótese formal com SciPy e p-valor interpretado | Pessoa 1 | `eda/eda.ipynb` — Mann-Whitney da H2 |
| Narrativa acessível conectada às hipóteses do TP1 | Pessoa 1 | `eda/eda.ipynb` + `docs/relatorio_eda.md`, citando a hipótese pelo número |
| API rejeita campo extra com 422 | Pessoa 2 | `models/base.py::StrictModel` em **todos** os schemas de entrada (falta `PredictRequest`) + `tests/test_seguranca.py` caso (c) |
| Recurso por ID com verificação de ownership | Pessoa 2 | `routes/tickets.py` + `tests/test_seguranca.py` caso (b) |
| HSTS, X-Frame-Options e X-Content-Type-Options nas respostas | Pessoa 3 | `middleware/security_headers.py` + teste que confira os headers |
| `POST /auth/token` devolve 429 | Pessoa 3 | `core/limiter.py` + `tests/test_rate_limit.py` |
| Limite e justificativa documentados | Pessoa 3 | README (texto já redigido na seção 5 deste contrato) |
| Relatório ZAP exportado no repositório | Pessoa 3 | `docs/zap_report.html` |
| Cada finding Medium/High com o que é, por que é problema e o que foi feito | Pessoa 3 | `docs/zap_findings.md` — se o scan não achar nenhum Medium/High, **registrar isso explicitamente**, com a contagem por severidade, em vez de deixar a seção vazia |
| Relatório de EDA com problema, dados, análise, insights e próximos passos | Pessoa 1 | `docs/relatorio_eda.md` |
| Relatório conecta os insights à pergunta de classificação do TP3 | Pessoa 1 | `docs/relatorio_eda.md`, seção 6 |

---

## 9. Como rodar (para todos)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r fastapi/requirements-dev.txt   # API + pytest
pip install -r eda/requirements.txt           # só quem for mexer no notebook
pytest tests/                                 # da raiz do repositório
cd fastapi && uvicorn main:app --reload       # API em http://127.0.0.1:8000
```
