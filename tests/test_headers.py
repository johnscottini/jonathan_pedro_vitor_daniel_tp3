"""Headers de segurança HTTP e CORS — TAREFA 3.

Comprova que os headers exigidos estão presentes nas respostas da API, inclusive
nas de erro, e que o CORS só aceita as origens da allowlist.
"""

import re

import pytest

from core.config import CORS_ORIGINS

OBRIGATORIOS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    # Acrescentado após o primeiro scan do ZAP (regra 90004).
    "Cross-Origin-Resource-Policy": "same-origin",
}


@pytest.mark.parametrize("header,valor", OBRIGATORIOS.items())
def test_headers_de_seguranca_presentes(client, header, valor):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers[header] == valor


def test_headers_presentes_tambem_em_resposta_de_erro(client):
    """Um 401 também precisa proibir iframe e sniffing de conteúdo."""
    response = client.post("/predict", json={"text": "oi"})
    assert response.status_code == 401
    for header, valor in OBRIGATORIOS.items():
        assert response.headers[header] == valor


def test_csp_restritiva_nas_rotas_da_api(client):
    csp = client.get("/health").headers["Content-Security-Policy"]
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp


def test_swagger_carrega_com_script_inline_autorizado_por_hash(client):
    """O /docs tem um <script> inline; sem o hash na CSP, a página abre em branco.

    O hash é calculado a partir do HTML gerado (ver routes/docs.py), então este
    teste também protege contra uma atualização do FastAPI mudar o script e
    quebrar a documentação silenciosamente.
    """
    resposta = client.get("/docs")
    assert resposta.status_code == 200

    csp = resposta.headers["Content-Security-Policy"]
    assert "'sha256-" in csp, "a CSP do /docs precisa autorizar o script inline por hash"
    assert "https://cdn.jsdelivr.net" in csp
    assert "frame-ancestors 'none'" in csp

    # O atalho fácil seria liberar 'unsafe-inline' — justamente o que a CSP
    # existe para impedir.
    script_src = [d for d in csp.split(";") if d.strip().startswith("script-src")][0]
    assert "unsafe-inline" not in script_src


def test_docs_corrige_os_findings_medium_do_zap_tp3(client):
    """Evidência das correções do scan passivo do TP3 (zap/scan_passivo_zap_TP3.md)."""
    resposta = client.get("/docs")
    csp = resposta.headers["Content-Security-Policy"]
    diretivas = {d.strip().split(" ")[0]: d.strip() for d in csp.split(";") if d.strip()}

    # 10055 — form-action não herda de default-src e precisa estar definida.
    assert diretivas["form-action"] == "form-action 'none'"
    # 10055 — style-src sem 'unsafe-inline'.
    assert "unsafe-inline" not in diretivas["style-src"]
    # 90003 — todo arquivo do CDN carrega com Subresource Integrity.
    for tag in re.findall(r"<(?:script|link)[^>]*cdn\.jsdelivr\.net[^>]*>", resposta.text):
        assert 'integrity="sha384-' in tag, tag
        assert 'crossorigin="anonymous"' in tag, tag
    # Versão fixa: "@5" mudaria o arquivo (e invalidaria o hash) a cada release.
    assert "swagger-ui-dist@5/" not in resposta.text
    # 90004 (Low) — página isolada de outras origens.
    assert resposta.headers["Cross-Origin-Embedder-Policy"] == "require-corp"


def test_redoc_foi_removido(client):
    """O ReDoc exigia style-src 'unsafe-inline'; no TP3 só o /docs é servido."""
    assert client.get("/redoc").status_code == 404


def test_banner_do_servidor_nao_expoe_a_stack(client):
    assert client.get("/health").headers.get("server") == "api"


def test_cors_aceita_origem_da_allowlist(client):
    origem = CORS_ORIGINS[0]
    response = client.options(
        "/auth/token",
        headers={
            "Origin": origem,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.headers["access-control-allow-origin"] == origem


def test_cors_recusa_origem_desconhecida(client):
    response = client.options(
        "/auth/token",
        headers={
            "Origin": "https://site-malicioso.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in response.headers
