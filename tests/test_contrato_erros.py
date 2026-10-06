"""Formato padronizado das respostas de erro (correção do retorno do TP1, Q5).

Todo erro da API — 401, 404, 422, 500 — sai no mesmo formato `ErrorResponse`:
`code`, `message`, `path` e, só em 422, a lista `fields`.
"""

from security.jwt import create_access_token
from security.users import ADMIN_USERNAME


def _auth_header():
    """Token do admin. A fixture `admin` precisa acompanhar o teste: desde o TP2
    o `sub` é conferido contra a tabela `User`."""
    return {"Authorization": "Bearer " + create_access_token(subject=ADMIN_USERNAME)}


def test_erro_401_tem_formato_padronizado(client):
    response = client.post("/predict", json={"text": "preciso de reembolso"})

    assert response.status_code == 401
    corpo = response.json()
    assert corpo["code"] == "unauthorized"
    assert corpo["path"] == "/predict"
    assert isinstance(corpo["message"], str) and corpo["message"]
    # O fluxo OAuth2 exige este header na resposta 401; o handler de erro
    # padronizado não pode engoli-lo.
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_erro_422_lista_os_campos_invalidos(client, admin):
    response = client.post("/predict", headers=_auth_header(), json={})

    assert response.status_code == 422
    corpo = response.json()
    assert corpo["code"] == "validation_error"
    assert corpo["path"] == "/predict"
    assert any(campo["field"].endswith("text") for campo in corpo["fields"])


def test_erro_404_tambem_segue_o_padrao(client):
    response = client.get("/rota-que-nao-existe")

    assert response.status_code == 404
    corpo = response.json()
    assert corpo["code"] == "not_found"
    assert corpo["path"] == "/rota-que-nao-existe"
