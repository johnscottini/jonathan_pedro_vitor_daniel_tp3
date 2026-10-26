"""Documentação interativa (/docs) — exigência do TP3.

O Swagger é gerado a partir do `/openapi.json`. Estes testes garantem que as
rotas principais continuam documentadas: descrição, corpo esperado, respostas
possíveis e o mecanismo de autenticação nas rotas protegidas.
"""

ROTAS_PROTEGIDAS = [
    ("post", "/predict"),
    ("get", "/tickets"),
    ("post", "/tickets"),
    ("get", "/tickets/{ticket_id}"),
]
ROTAS_PUBLICAS = [("get", "/health"), ("post", "/auth/token")]


def _spec(client):
    resposta = client.get("/openapi.json")
    assert resposta.status_code == 200
    return resposta.json()


def test_swagger_ui_esta_disponivel_em_docs(client):
    resposta = client.get("/docs")
    assert resposta.status_code == 200
    assert "swagger-ui" in resposta.text
    assert "/openapi.json" in resposta.text


def test_rotas_principais_tem_descricao_e_respostas_documentadas(client):
    paths = _spec(client)["paths"]
    for metodo, rota in ROTAS_PROTEGIDAS + ROTAS_PUBLICAS:
        operacao = paths[rota][metodo]
        assert operacao.get("summary"), f"{metodo.upper()} {rota} sem summary"
        assert operacao.get("description"), f"{metodo.upper()} {rota} sem description"
        assert any(status.startswith("2") for status in operacao["responses"])


def test_rotas_protegidas_declaram_autenticacao_e_o_401(client):
    spec = _spec(client)
    esquema = spec["components"]["securitySchemes"]["OAuth2PasswordBearer"]
    assert esquema["type"] == "oauth2"
    assert esquema["flows"]["password"]["tokenUrl"] == "auth/token"

    for metodo, rota in ROTAS_PROTEGIDAS:
        operacao = spec["paths"][rota][metodo]
        assert operacao.get("security") == [{"OAuth2PasswordBearer": []}], rota
        assert "401" in operacao["responses"], rota


def test_rotas_publicas_nao_exigem_token(client):
    paths = _spec(client)["paths"]
    for metodo, rota in ROTAS_PUBLICAS:
        assert "security" not in paths[rota][metodo], rota


def test_corpo_e_parametros_estao_documentados(client):
    spec = _spec(client)
    paths = spec["paths"]

    assert "requestBody" in paths["/predict"]["post"]
    assert "requestBody" in paths["/tickets"]["post"]
    assert "application/x-www-form-urlencoded" in paths["/auth/token"]["post"]["requestBody"]["content"]

    parametros = paths["/tickets/{ticket_id}"]["get"]["parameters"]
    assert parametros[0]["name"] == "ticket_id" and parametros[0]["in"] == "path"

    # 429 do rate limit também aparece na documentação do login.
    assert "429" in paths["/auth/token"]["post"]["responses"]
