"""Rate limiting do login — TAREFA 4.

Este arquivo existe porque `conftest.py` DESLIGA o rate limit nos demais testes
(senão os logins em série derrubariam a suíte com 429). Aqui ele é religado,
teste a teste, para comprovar o 429.

O limite vem de `core.config.RATE_LIMIT_LOGIN`: o teste lê o número de lá em vez
de repetir "5", para não quebrar se o limite for ajustado.
"""

import pytest

from core.config import RATE_LIMIT_LOGIN
from core.limiter import reset_rate_limiting, set_rate_limiting_enabled
from tests.conftest import SENHA_PADRAO

LIMITE = int(RATE_LIMIT_LOGIN.split("/")[0])


@pytest.fixture
def limiter_ligado():
    """Religa o rate limit só para este teste e zera o contador nas duas pontas.

    O contador do slowapi vive na memória do processo: sem o reset, a ordem dos
    testes mudaria o resultado.
    """
    reset_rate_limiting()
    set_rate_limiting_enabled(True)
    yield
    set_rate_limiting_enabled(False)
    reset_rate_limiting()


def test_login_devolve_429_apos_exceder_o_limite(client, limiter_ligado, alice):
    """Força bruta: a tentativa seguinte ao limite recebe 429, não 401."""
    credenciais = {"username": alice.username, "password": "senha-errada"}

    for tentativa in range(LIMITE):
        resposta = client.post("/auth/token", data=credenciais)
        assert resposta.status_code == 401, (
            f"tentativa {tentativa + 1} deveria ser 401 (dentro do limite), "
            f"veio {resposta.status_code}"
        )

    bloqueada = client.post("/auth/token", data=credenciais)
    assert bloqueada.status_code == 429
    assert bloqueada.json()["code"] == "rate_limited"
    # Header padrão para o cliente saber quando pode tentar de novo.
    assert bloqueada.headers["Retry-After"] == "60"


def test_credencial_correta_tambem_e_bloqueada_apos_o_limite(client, limiter_ligado, alice):
    """O limite é por IP e vale mesmo para quem acerta a senha.

    É o comportamento desejado: o atacante não pode usar uma credencial válida,
    descoberta no meio da varredura, para escapar do bloqueio.
    """
    for _ in range(LIMITE):
        client.post("/auth/token", data={"username": alice.username, "password": "errada"})

    resposta = client.post(
        "/auth/token", data={"username": alice.username, "password": SENHA_PADRAO}
    )
    assert resposta.status_code == 429


def test_rate_limit_nao_afeta_as_demais_rotas(client, limiter_ligado):
    """Só o /auth/token é limitado: /health é alvo de monitoramento."""
    for _ in range(LIMITE + 3):
        assert client.get("/health").status_code == 200
