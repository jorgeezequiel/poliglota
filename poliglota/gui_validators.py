"""Input validation helpers for the Poliglota desktop GUI.

The validators are pure functions so they can be unit-tested without a display
and reused by any future front end. They only check what the GUI can know
locally: a bad locale or a missing project folder is reported before a
subprocess is spawned, so the user gets feedback while typing instead of
waiting for a generic CLI failure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Poliglota locale codes are free-form language identifiers such as "en",
# "pt_BR", "zh_Hant_TW" or "en-US"; the core never forces a country part.
LOCALE_PATTERN = re.compile(r"[A-Za-z]{2,3}(?:[_-][A-Za-z0-9]{2,8})*")
# Model identifiers look like Hugging Face repo ids or local folder names.
MODEL_NAME_PATTERN = re.compile(r"[A-Za-z0-9._/-]+")

MAX_LOCALE_LENGTH = 35
MAX_MODEL_NAME_LENGTH = 200


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Outcome of validating a single form field."""

    is_valid: bool
    message: str = ""

    @classmethod
    def ok(cls, message: str = "") -> ValidationResult:
        """Build a successful result, optionally with a hint message."""
        return cls(is_valid=True, message=message)

    @classmethod
    def error(cls, message: str) -> ValidationResult:
        """Build a failing result with an actionable message."""
        return cls(is_valid=False, message=message)


def validate_project_path(value: str) -> ValidationResult:
    """Check that the project root is an existing directory."""
    candidate = value.strip()
    if not candidate:
        return ValidationResult.error("Informe a pasta do projeto.")

    path = Path(candidate).expanduser()
    try:
        if not path.exists():
            return ValidationResult.error("Pasta não encontrada.")
        if not path.is_dir():
            return ValidationResult.error("O caminho não é uma pasta.")
    except OSError:
        return ValidationResult.error("Caminho inválido ou inacessível.")

    return ValidationResult.ok("Pasta válida.")


def validate_locale(value: str, *, label: str = "Idioma") -> ValidationResult:
    """Check one locale or a comma-separated list of locales."""
    candidate = value.strip()
    if not candidate:
        return ValidationResult.error(f"{label} é obrigatório.")

    items = [item.strip() for item in candidate.split(",") if item.strip()]
    if not items:
        return ValidationResult.error(f"{label} inválido. Use o formato: pt_BR, en_US, es…")

    for item in items:
        if len(item) > MAX_LOCALE_LENGTH:
            return ValidationResult.error(f"{label} é longo demais.")
        if LOCALE_PATTERN.fullmatch(item) is None:
            return ValidationResult.error(
                f"{label} inválido. Use o formato: pt_BR, en_US, es…",
            )

    return ValidationResult.ok()


def validate_model_name(value: str) -> ValidationResult:
    """Check the optional model identifier (empty means "use the default")."""
    candidate = value.strip()
    if not candidate:
        return ValidationResult.ok("O modelo padrão do motor será usado.")
    if len(candidate) > MAX_MODEL_NAME_LENGTH:
        return ValidationResult.error("Nome do modelo é longo demais.")
    if MODEL_NAME_PATTERN.fullmatch(candidate) is None:
        return ValidationResult.error("Use apenas letras, números, '.', '_', '-' e '/'.")

    return ValidationResult.ok()


def validate_translation_text(value: str) -> ValidationResult:
    """Check the text submitted to the single-text translation command."""
    if not value.strip():
        return ValidationResult.error("Informe o texto para tradução.")

    return ValidationResult.ok()
