from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from poliglota.gui_validators import (
    MAX_LOCALE_LENGTH,
    MAX_MODEL_NAME_LENGTH,
    ValidationResult,
    validate_locale,
    validate_model_name,
    validate_project_path,
    validate_translation_text,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.unit
def test_validation_result_helpers() -> None:
    assert ValidationResult.ok().is_valid is True
    assert ValidationResult.error("falhou").message == "falhou"
    assert ValidationResult.error("falhou").is_valid is False


@pytest.mark.unit
def test_validate_project_path_accepts_existing_directory(tmp_path: Path) -> None:
    result = validate_project_path(str(tmp_path))

    assert result.is_valid is True


@pytest.mark.unit
def test_validate_project_path_rejects_empty_value() -> None:
    result = validate_project_path("   ")

    assert result.is_valid is False
    assert "Informe a pasta" in result.message


@pytest.mark.unit
def test_validate_project_path_rejects_missing_directory(tmp_path: Path) -> None:
    result = validate_project_path(str(tmp_path / "missing"))

    assert result.is_valid is False
    assert "não encontrada" in result.message


@pytest.mark.unit
def test_validate_project_path_rejects_regular_file(tmp_path: Path) -> None:
    file_path = tmp_path / "file.txt"
    file_path.write_text("conteúdo", encoding="utf-8")

    result = validate_project_path(str(file_path))

    assert result.is_valid is False
    assert "não é uma pasta" in result.message


@pytest.mark.unit
@pytest.mark.parametrize("code", ["pt", "pt_BR", "en-US", "zh_Hant_TW", "es"])
def test_validate_locale_accepts_supported_codes(code: str) -> None:
    assert validate_locale(code).is_valid is True


@pytest.mark.unit
@pytest.mark.parametrize("code", ["", "   ", "p", "pt_BR!", "idioma com espaço", "x" * 40])
def test_validate_locale_rejects_invalid_codes(code: str) -> None:
    assert validate_locale(code).is_valid is False


@pytest.mark.unit
def test_validate_locale_uses_custom_label() -> None:
    result = validate_locale("", label="Idioma de origem")

    assert "Idioma de origem" in result.message


@pytest.mark.unit
def test_validate_locale_rejects_overlong_code() -> None:
    result = validate_locale("a" * (MAX_LOCALE_LENGTH + 1))

    assert result.is_valid is False
    assert "longo demais" in result.message


@pytest.mark.unit
def test_validate_model_name_accepts_empty_and_huggingface_ids() -> None:
    assert validate_model_name("").is_valid is True
    assert validate_model_name("facebook/nllb-200-distilled-600M").is_valid is True


@pytest.mark.unit
def test_validate_model_name_rejects_spaces() -> None:
    result = validate_model_name("modelo com espaço")

    assert result.is_valid is False


@pytest.mark.unit
def test_validate_model_name_rejects_overlong_value() -> None:
    result = validate_model_name("a" * (MAX_MODEL_NAME_LENGTH + 1))

    assert result.is_valid is False
    assert "longo demais" in result.message


@pytest.mark.unit
def test_validate_translation_text_requires_content() -> None:
    assert validate_translation_text("Olá").is_valid is True
    assert validate_translation_text("   ").is_valid is False
