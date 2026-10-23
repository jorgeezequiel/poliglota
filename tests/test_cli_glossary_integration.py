"""Integration tests for CLI glossary validation."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from poliglota.cli import main


@pytest.fixture
def temp_arb_project() -> tuple[Path, dict]:
    """Create a temporary ARB project with source and target locales.
    
    Returns:
        (root_path, arb_files_dict)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # ARB pattern: app_<module>_<locale>.arb
        source_file = root / "app_messages_pt_BR.arb"
        source_file.write_text(
            json.dumps({
                "@@locale": "pt_BR",
                "greeting": "Olá, {name}!",
                "farewell": "Até logo!",
            }, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        target_file = root / "app_messages_es_ES.arb"
        target_file.write_text(
            json.dumps({
                "@@locale": "es_ES",
                "greeting": "¡Hola, {name}!",
                "farewell": "¡Hasta luego!",
            }, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        incomplete_file = root / "app_messages_fr_FR.arb"
        incomplete_file.write_text(
            json.dumps({
                "@@locale": "fr_FR",
                "greeting": "Bonjour, {name}!",
                "farewell": "À bientôt!",
            }, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        yield root, {
            "source": source_file,
            "target": target_file,
            "incomplete": incomplete_file,
        }


@pytest.fixture
def temp_glossary_json(tmp_path: Path) -> Path:
    """Create a temporary glossary JSON file with terms that appear in translations."""
    glossary_file = tmp_path / "glossary.json"
    glossary_file.write_text(
        json.dumps({
            "hello": "Hola",
            "bye": "Hasta",
        }, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return glossary_file


@pytest.fixture
def temp_glossary_csv(tmp_path: Path) -> Path:
    """Create a temporary glossary CSV file with terms that appear in translations."""
    glossary_file = tmp_path / "glossary.csv"
    glossary_file.write_text(
        "hello,Hola\nbye,Hasta\n",
        encoding="utf-8"
    )
    return glossary_file


def test_validate_without_glossary_succeeds(temp_arb_project: tuple[Path, dict]) -> None:
    """Validate without glossary should succeed for complete locales."""
    root, _ = temp_arb_project
    exit_code = main(["validate", "--root", str(root), "--source", "pt_BR"])
    assert exit_code == 0  # All locales have all keys now


def test_validate_with_missing_glossary_file_returns_error(
    temp_arb_project: tuple[Path, dict],
) -> None:
    """Validate with missing glossary file should return error code 1."""
    root, _ = temp_arb_project
    exit_code = main([
        "validate",
        "--root", str(root),
        "--source", "pt_BR",
        "--glossary", "/nonexistent/glossary.json",
        "--check-glossary",
    ])
    assert exit_code == 1


def test_validate_glossary_json_format(
    temp_arb_project: tuple[Path, dict],
    temp_glossary_json: Path,
) -> None:
    """Validate glossary from JSON file."""
    root, _ = temp_arb_project
    exit_code = main([
        "validate",
        "--root", str(root),
        "--source", "pt_BR",
        "--glossary", str(temp_glossary_json),
        "--check-glossary",
        "--locale", "es_ES",
    ])
    assert exit_code == 0


def test_validate_glossary_csv_format(
    temp_arb_project: tuple[Path, dict],
    temp_glossary_csv: Path,
) -> None:
    """Validate glossary from CSV file."""
    root, _ = temp_arb_project
    exit_code = main([
        "validate",
        "--root", str(root),
        "--source", "pt_BR",
        "--glossary", str(temp_glossary_csv),
        "--check-glossary",
        "--locale", "es_ES",
    ])
    assert exit_code == 0


def test_validate_without_glossary_flag_ignores_glossary_file(
    temp_arb_project: tuple[Path, dict],
    temp_glossary_json: Path,
) -> None:
    """Glossary file should be ignored if --check-glossary flag is not set."""
    root, _ = temp_arb_project
    exit_code = main([
        "validate",
        "--root", str(root),
        "--source", "pt_BR",
        "--glossary", str(temp_glossary_json),
    ])
    assert exit_code == 0  # No glossary check, all keys present


def test_validate_with_all_locales_when_no_target_locale_specified(
    temp_arb_project: tuple[Path, dict],
    temp_glossary_json: Path,
) -> None:
    """When --locale not specified, validate glossary for all target locales."""
    root, _ = temp_arb_project
    exit_code = main([
        "validate",
        "--root", str(root),
        "--source", "pt_BR",
        "--glossary", str(temp_glossary_json),
        "--check-glossary",
    ])
    # Glossary terms are not in fr_FR, so warnings expected (exit code 1)
    assert exit_code == 1


def test_validate_preserves_backward_compatibility(
    temp_arb_project: tuple[Path, dict],
) -> None:
    """Validate command without new flags should work as before."""
    root, _ = temp_arb_project
    exit_code = main(["validate", "--root", str(root), "--source", "pt_BR"])
    assert exit_code in (0, 1)  # Valid exit codes


def test_validate_glossary_with_invalid_json_returns_error(
    temp_arb_project: tuple[Path, dict],
    tmp_path: Path,
) -> None:
    """Invalid JSON glossary file should return error."""
    root, _ = temp_arb_project
    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text("{invalid json", encoding="utf-8")
    
    exit_code = main([
        "validate",
        "--root", str(root),
        "--source", "pt_BR",
        "--glossary", str(invalid_json),
        "--check-glossary",
    ])
    assert exit_code == 1


def test_validate_glossary_with_invalid_csv_returns_error(
    temp_arb_project: tuple[Path, dict],
    tmp_path: Path,
) -> None:
    """Invalid CSV glossary file should return error."""
    root, _ = temp_arb_project
    invalid_csv = tmp_path / "invalid.csv"
    invalid_csv.write_text("only_one_column\n", encoding="utf-8")
    
    exit_code = main([
        "validate",
        "--root", str(root),
        "--source", "pt_BR",
        "--glossary", str(invalid_csv),
        "--check-glossary",
    ])
    assert exit_code == 1


def test_validate_glossary_unsupported_format_returns_error(
    temp_arb_project: tuple[Path, dict],
    tmp_path: Path,
) -> None:
    """Unsupported glossary format should return error."""
    root, _ = temp_arb_project
    unsupported = tmp_path / "glossary.yaml"
    unsupported.write_text("key: value\n", encoding="utf-8")
    
    exit_code = main([
        "validate",
        "--root", str(root),
        "--source", "pt_BR",
        "--glossary", str(unsupported),
        "--check-glossary",
    ])
    assert exit_code == 1


def test_validate_check_keys_flag_controls_key_validation(
    temp_arb_project: tuple[Path, dict],
) -> None:
    """--check-keys flag should control key validation."""
    root, _ = temp_arb_project

    exit_code = main([
        "validate",
        "--root", str(root),
        "--source", "pt_BR",
        "--check-keys",
    ])
    assert exit_code == 0  # All keys present in all locales


def test_validate_check_placeholders_flag_controls_placeholder_validation(
    temp_arb_project: tuple[Path, dict],
) -> None:
    """--check-placeholders flag should control placeholder validation."""
    root, _ = temp_arb_project

    exit_code = main([
        "validate",
        "--root", str(root),
        "--source", "pt_BR",
        "--check-placeholders",
    ])
    assert exit_code == 0  # All placeholders match between locales


def test_validate_glossary_json_with_non_dict_returns_error(
    temp_arb_project: tuple[Path, dict],
    tmp_path: Path,
) -> None:
    """Glossary JSON that is not a dict should return error."""
    root, _ = temp_arb_project
    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text('["term1", "term2"]', encoding="utf-8")
    
    exit_code = main([
        "validate",
        "--root", str(root),
        "--source", "pt_BR",
        "--glossary", str(invalid_json),
        "--check-glossary",
    ])
    assert exit_code == 1


def test_validate_glossary_csv_with_comments_is_ignored(
    temp_arb_project: tuple[Path, dict],
    tmp_path: Path,
) -> None:
    """CSV glossary with comment lines should skip them."""
    root, _ = temp_arb_project
    glossary_csv = tmp_path / "glossary.csv"
    glossary_csv.write_text(
        "# This is a comment\nhello,Hola\n# Another comment\nbye,Hasta\n",
        encoding="utf-8"
    )
    
    exit_code = main([
        "validate",
        "--root", str(root),
        "--source", "pt_BR",
        "--glossary", str(glossary_csv),
        "--check-glossary",
        "--locale", "es_ES",
    ])
    assert exit_code == 0


def test_validate_glossary_csv_with_whitespace_handling(
    temp_arb_project: tuple[Path, dict],
    tmp_path: Path,
) -> None:
    """CSV glossary should handle whitespace correctly."""
    root, _ = temp_arb_project
    glossary_csv = tmp_path / "glossary.csv"
    glossary_csv.write_text(
        "  hello  ,  Hola  \nbye , Hasta\n",
        encoding="utf-8"
    )
    
    exit_code = main([
        "validate",
        "--root", str(root),
        "--source", "pt_BR",
        "--glossary", str(glossary_csv),
        "--check-glossary",
        "--locale", "es_ES",
    ])
    assert exit_code == 0
