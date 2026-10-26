"""Suíte de testes de segurança do TP3.

Um bloco por aspecto exigido pelo enunciado. Todos os testes conferem o status
code **e** o corpo da resposta: um 401 com o corpo errado (traceback, `detail`
solto, mensagem que entrega qual campo falhou) também é uma falha de segurança.

  1. Autenticação ............ credenciais válidas e inválidas no /auth/token
  2. Autorização / BOLA ...... um usuário não acessa recurso de outro
  3. Validação de entrada .... campos extras e valores inválidos -> 422
  4. Rate limiting ........... login acima do limite -> 429
  5. Rota protegida .......... sem token válido -> 401

Os testes do TP2 (`test_seguranca.py`, `test_rate_limit.py`, `test_auth_jwt.py`,
`test_headers.py`) continuam valendo; este arquivo os complementa.
"""

from jose import jwt

from core.config import ALGORITHM, SECRET_KEY
from tests.conftest import LIMITE_LOGIN, SENHA_PADRAO, auth_header, obter_token

MENSAGEM_LOGIN_INVALIDO = "Usuário ou senha incorretos"


def _login(client, username, password):
    return client.post("/auth/token", data={"username": username, "password": password})


def _assert_erro_padronizado(resposta, status, code, path):
    """Todo erro sai no formato `ErrorResponse`, nunca com traceback."""
    assert resposta.status_code == status
    corpo = resposta.json()
    assert corpo["code"] == code
    assert corpo["path"] == path
    assert isinstance(corpo["message"], str) and corpo["message"]
    assert "Traceback" not in resposta.text
    return corpo


# --- 1. Autenticação --------------------------------------------------------


def test_login_com_credenciais_validas_emite_token_jwt(client, alice):
    resposta = _login(client, alice.username, SENHA_PADRAO)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["token_type"] == "bearer"
    # O token é um JWT válido, assinado pela API, do usuário que fez login e com expiração.
    payload = jwt.decode(corpo["access_token"], SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "alice"
    assert "exp" in payload


def test_login_com_senha_errada_e_recusado(client, alice):
    resposta = _login(client, alice.username, "senha-errada")

    corpo = _assert_erro_padronizado(resposta, 401, "unauthorized", "/auth/token")
    assert corpo["message"] == MENSAGEM_LOGIN_INVALIDO
    assert "access_token" not in corpo
    assert resposta.headers["WWW-Authenticate"] == "Bearer"


def test_usuario_inexistente_recebe_a_mesma_resposta_da_senha_errada(client, alice):
    """Mensagens diferentes permitiriam descobrir quais usuários existem."""
    senha_errada = _login(client, alice.username, "senha-errada")
    inexistente = _login(client, "usuario-que-nao-existe", "qualquer-senha")

    assert inexistente.status_code == senha_errada.status_code == 401
    assert inexistente.json() == senha_errada.json()


# --- 2. Autorização / BOLA --------------------------------------------------


def test_usuario_nao_le_ticket_de_outro_usuario(client, token_alice, ticket_de_bob):
    """BOLA (OWASP A01): alice pede pelo ID um ticket que pertence ao bob."""
    path = "/tickets/" + str(ticket_de_bob.id)
    resposta = client.get(path, headers=auth_header(token_alice))

    # 404, não 403: a resposta não confirma que o ID existe.
    corpo = _assert_erro_padronizado(resposta, 404, "not_found", path)
    assert ticket_de_bob.subject not in resposta.text
    assert "owner_id" not in corpo


def test_ticket_de_outro_usuario_responde_igual_a_ticket_inexistente(
    client, token_alice, ticket_de_bob
):
    alheio = client.get("/tickets/" + str(ticket_de_bob.id), headers=auth_header(token_alice))
    inexistente = client.get("/tickets/999999", headers=auth_header(token_alice))

    assert alheio.status_code == inexistente.status_code == 404
    assert alheio.json()["message"] == inexistente.json()["message"]


def test_listagem_mostra_apenas_os_tickets_do_proprio_usuario(
    client, token_alice, token_bob, ticket_de_bob
):
    criado = client.post(
        "/tickets",
        headers=auth_header(token_alice),
        json={"subject": "Reembolso", "description": "Quero meu dinheiro de volta.",
              "ticket_type": "Refund request"},
    )
    assert criado.status_code == 201

    lista_alice = client.get("/tickets", headers=auth_header(token_alice))
    assert lista_alice.status_code == 200
    ids_alice = [t["id"] for t in lista_alice.json()]
    assert ids_alice == [criado.json()["id"]]
    assert ticket_de_bob.id not in ids_alice

    # O dono continua enxergando o próprio ticket.
    lista_bob = client.get("/tickets", headers=auth_header(token_bob))
    assert [t["id"] for t in lista_bob.json()] == [ticket_de_bob.id]


# --- 3. Validação de entrada ------------------------------------------------


def test_campo_extra_owner_id_e_rejeitado_e_apontado(client, token_alice, bob):
    """Mass assignment: tentar criar um ticket em nome do bob via `owner_id`."""
    resposta = client.post(
        "/tickets",
        headers=auth_header(token_alice),
        json={"subject": "Teste", "description": "Teste", "ticket_type": "Billing inquiry",
              "owner_id": bob.id},
    )

    corpo = _assert_erro_padronizado(resposta, 422, "validation_error", "/tickets")
    assert any(campo["field"].endswith("owner_id") for campo in corpo["fields"])
    # Nada foi gravado para o bob.
    assert client.get("/tickets", headers=auth_header(token_alice)).json() == []


def test_predict_rejeita_campo_extra(client, token_alice):
    resposta = client.post(
        "/predict", headers=auth_header(token_alice),
        json={"text": "quero reembolso", "is_admin": True},
    )

    corpo = _assert_erro_padronizado(resposta, 422, "validation_error", "/predict")
    assert any(campo["field"].endswith("is_admin") for campo in corpo["fields"])


def test_predict_rejeita_texto_vazio_e_tipo_invalido(client, token_alice):
    for corpo_invalido in ({"text": ""}, {"text": 123}, {"text": None}, {}):
        resposta = client.post("/predict", headers=auth_header(token_alice), json=corpo_invalido)
        corpo = _assert_erro_padronizado(resposta, 422, "validation_error", "/predict")
        assert any(campo["field"].endswith("text") for campo in corpo["fields"])


def test_ticket_rejeita_campo_acima_do_tamanho_maximo(client, token_alice):
    resposta = client.post(
        "/tickets",
        headers=auth_header(token_alice),
        json={"subject": "x" * 201, "description": "ok", "ticket_type": "Billing inquiry"},
    )

    corpo = _assert_erro_padronizado(resposta, 422, "validation_error", "/tickets")
    assert any(campo["field"].endswith("subject") for campo in corpo["fields"])


# --- 4. Rate limiting -------------------------------------------------------


def test_login_acima_do_limite_e_bloqueado_com_429(client, limiter_ligado, alice):
    for _ in range(LIMITE_LOGIN):
        assert _login(client, alice.username, "senha-errada").status_code == 401

    bloqueada = _login(client, alice.username, "senha-errada")

    corpo = _assert_erro_padronizado(bloqueada, 429, "rate_limited", "/auth/token")
    assert "Limite" in corpo["message"]
    assert bloqueada.headers["Retry-After"] == "60"
    assert "access_token" not in corpo


# --- 5. Rota protegida ------------------------------------------------------


def test_rotas_protegidas_exigem_token(client):
    rotas = [
        ("get", "/tickets", None),
        ("get", "/tickets/1", None),
        ("post", "/tickets", {"subject": "a", "description": "b", "ticket_type": "c"}),
        ("post", "/predict", {"text": "quero reembolso"}),
    ]
    for metodo, path, corpo in rotas:
        resposta = getattr(client, metodo)(path, json=corpo) if corpo else getattr(client, metodo)(path)
        _assert_erro_padronizado(resposta, 401, "unauthorized", path)
        assert resposta.headers["WWW-Authenticate"] == "Bearer"


def test_rota_protegida_recusa_token_invalido(client, alice):
    tokens_invalidos = [
        "nao-e-um-jwt",
        "a.b.c",
        jwt.encode({"sub": "alice", "exp": 9999999999}, "chave-de-outro-sistema", algorithm=ALGORITHM),
    ]
    for token in tokens_invalidos:
        resposta = client.get("/tickets", headers=auth_header(token))
        _assert_erro_padronizado(resposta, 401, "unauthorized", "/tickets")


def test_rota_protegida_aceita_token_valido(client, alice):
    """Contraprova: o 401 acima vem da falta de token, não de a rota estar quebrada."""
    token = obter_token(client, alice.username)
    resposta = client.get("/tickets", headers=auth_header(token))

    assert resposta.status_code == 200
    assert resposta.json() == []
