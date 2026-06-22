"""Guardrails de seguridad para el API del agente.

La idea es validar el input antes de invocar el modelo o cualquier herramienta MCP/RAG.
Si una solicitud es riesgosa, se bloquea de forma temprana y se devuelve una
respuesta controlada.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class GuardrailResult:
    blocked: bool
    reason: str | None = None
    category: str | None = None


MAX_QUESTION_LENGTH = 1200
MAX_USER_LENGTH = 80

PROMPT_INJECTION_PATTERNS = [
    r"ignora\s+(todas\s+)?(las\s+)?instrucciones",
    r"olvida\s+(todas\s+)?(las\s+)?instrucciones",
    r"revela\s+(tu\s+)?(prompt|system prompt|instrucciones)",
    r"muestra\s+(tu\s+)?(prompt|system prompt|instrucciones)",
    r"dime\s+(tu\s+)?(prompt|system prompt|instrucciones)",
    r"act[uú]a\s+como\s+(admin|administrador|developer|desarrollador|sistema)",
    r"modo\s+(developer|desarrollador|admin|administrador)",
    r"bypass",
    r"jailbreak",
    r"dan\s+mode",
]

SENSITIVE_DATA_PATTERNS = [
    r"sk-[A-Za-z0-9_-]{20,}",                              # OpenAI API key aproximada
    r"(?i)(api[_\s-]?key|token|secret|password|contrase[nñ]a)\s*[:=]",
    r"\b(?:\d[ -]*?){13,19}\b",                           # posible tarjeta
    r"\b\d{4}\s?\d{5}\s?\d{4}\b",                        # DPI GT aproximado 13 dígitos
]

SQL_OR_TOOL_ABUSE_PATTERNS = [
    r"(?i)drop\s+table",
    r"(?i)delete\s+from",
    r"(?i)truncate\s+table",
    r"(?i)update\s+.+\s+set\s+",
]


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def validate_input(question: str | None, user: str | None) -> GuardrailResult:
    """Valida el request antes de usar el agente."""
    if question is None or not question.strip():
        return GuardrailResult(True, "La pregunta no puede estar vacía.", "validation")

    if len(question) > MAX_QUESTION_LENGTH:
        return GuardrailResult(True, f"La pregunta supera el límite de {MAX_QUESTION_LENGTH} caracteres.", "validation")

    if user is None or not user.strip():
        return GuardrailResult(True, "El usuario no puede estar vacío.", "validation")

    if len(user) > MAX_USER_LENGTH:
        return GuardrailResult(True, f"El usuario supera el límite de {MAX_USER_LENGTH} caracteres.", "validation")

    if _matches_any(question, PROMPT_INJECTION_PATTERNS):
        return GuardrailResult(True, "Intento de prompt injection detectado.", "prompt_injection")

    if _matches_any(question, SENSITIVE_DATA_PATTERNS):
        return GuardrailResult(True, "Se detectaron datos sensibles o credenciales en la solicitud.", "sensitive_data")

    if _matches_any(question, SQL_OR_TOOL_ABUSE_PATTERNS):
        return GuardrailResult(True, "Solicitud potencialmente peligrosa para herramientas o base de datos.", "tool_abuse")

    return GuardrailResult(False)


def validate_output(answer: str | None) -> GuardrailResult:
    """Valida la respuesta generada antes de devolverla al usuario."""
    if not answer:
        return GuardrailResult(False)

    if _matches_any(answer, SENSITIVE_DATA_PATTERNS):
        return GuardrailResult(True, "La respuesta generada contiene posible información sensible.", "sensitive_data_output")

    return GuardrailResult(False)


def blocked_answer(result: GuardrailResult) -> str:
    """Respuesta uniforme para solicitudes bloqueadas."""
    return (
        "Solicitud bloqueada por política de seguridad. "
        f"Motivo: {result.reason}"
    )
