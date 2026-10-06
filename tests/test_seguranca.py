"""Testes de segurança obrigatórios do TP2 — TAREFA 6 (Pessoa 2).

Casos exigidos pelo enunciado:
  (a) acesso sem token            -> 401
  (b) acesso a recurso de outro usuário -> 404 (não 403: não vazar existência)
  (c) campo extra no body         -> 422 (Pydantic com extra="forbid")
"""

from tests.conftest import auth_header


def test_a_acesso_sem_token_e_negado(client, ticket_de_bob):
    response = client.get("/tickets/" + str(ticket_de_bob.id))
    assert response.status_code == 401


def test_b_nao_acessa_ticket_de_outro_usuario(client, token_alice, ticket_de_bob):
    """BOLA (OWASP A01): alice tenta ler um ticket que é do bob."""
    response = client.get(
        "/tickets/" + str(ticket_de_bob.id), headers=auth_header(token_alice)
    )
    assert response.status_code == 404


def test_c_campo_extra_no_body_e_rejeitado(client, token_alice):
    """Mass assignment: o cliente tenta injetar `owner_id` no corpo."""
    response = client.post(
        "/tickets",
        headers=auth_header(token_alice),
        json={
            "subject": "Não consigo acessar minha conta",
            "description": "Recebo erro de senha inválida.",
            "ticket_type": "Technical issue",
            "owner_id": 999,
        },
    )
    assert response.status_code == 422
