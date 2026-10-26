"""Classificador de intenção simulado (fake model).

O `POST /predict` ainda não roda um modelo de Machine Learning: devolve uma
intenção predeterminada por correspondência de palavras-chave, apenas para
simular o formato da resposta. O classificador planejado em
`others/planejamento.md` (CountVectorizer + Regressão Logística) substitui esta
função no próximo TP, sem mudar quem a chama.
"""

from typing import Tuple

_KEYWORD_INTENTS = [
    ("refund", "refund_request"),
    ("reembolso", "refund_request"),
    ("cancel", "cancellation_request"),
    ("cancela", "cancellation_request"),
    ("bill", "billing_inquiry"),
    ("fatura", "billing_inquiry"),
    ("cobra", "billing_inquiry"),
    ("bug", "technical_issue"),
    ("error", "technical_issue"),
    ("erro", "technical_issue"),
    ("problem", "technical_issue"),
    ("problema", "technical_issue"),
]

_DEFAULT_INTENT = "product_inquiry"
_STUB_CONFIDENCE = 0.5


def prever_intencao(texto: str) -> Tuple[str, float]:
    """Devolve `(intenção, confiança)` para o texto de uma mensagem."""
    texto_lower = texto.lower()
    for keyword, intent in _KEYWORD_INTENTS:
        if keyword in texto_lower:
            return intent, _STUB_CONFIDENCE
    return _DEFAULT_INTENT, _STUB_CONFIDENCE
