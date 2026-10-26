"""Configuração central da API.

Todos os valores sensíveis ou dependentes de ambiente ficam aqui e são lidos de
variáveis de ambiente (ver `.env.example`). Nenhum segredo deve voltar a ser
escrito direto no código — no TP1 a `SECRET_KEY` estava fixa em `security/jwt.py`,
o que é exatamente o tipo de problema que o ZAP e o pentest do próximo bloco
procuram (OWASP A02 — Cryptographic Failures / A05 — Security Misconfiguration).

ATENÇÃO: este arquivo faz parte do contrato do TP2 (fase 0). Se precisar de uma
nova configuração, avise o time antes de alterar.
"""

import os
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent

# Versão da API: usada no título do OpenAPI e devolvida pelo GET /health.
API_VERSION = "0.3.0"


def _csv_env(name: str, default: str) -> List[str]:
    """Lê uma variável de ambiente no formato `a,b,c` e devolve uma lista."""
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# --- JWT -------------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-trocar-em-producao")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# --- Banco de dados --------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///" + str(BASE_DIR / "database.db"))

# Caminho do arquivo SQLite, usado pelos scripts `sqlite_database.py` e
# `sqlite_populate.py` (módulo `sqlite3`, que recebe um caminho e não uma URL).
SQLITE_PATH = DATABASE_URL.removeprefix("sqlite:///")

# --- CORS (Pessoa 3) -------------------------------------------------------
# Allowlist explícita. Nunca usar "*" junto com credenciais (OWASP A05).
CORS_ORIGINS = _csv_env("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")

# --- Rate limiting (Pessoa 3) ---------------------------------------------
# Formato aceito pelo slowapi. O enunciado do TP2 fixa no máximo 10 requisições
# por minuto por cliente no endpoint de autenticação.
RATE_LIMIT_LOGIN = os.getenv("RATE_LIMIT_LOGIN", "10/minute")
