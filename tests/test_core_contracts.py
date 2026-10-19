"""Tests for the format-agnostic core contracts."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from poliglota.core import Locale, TranslationRequest, TranslationResult
from poliglota.core.translation import IssueSeverity, TranslationIssue

CORE_DIR = Path(__file__).resolve().parent.parent / "poliglota" / "core"


def _imported_module_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _is_format_adapter_import(name: str) -> bool:
    lowered = name.lower()
    return (
        "arb" in lowered
        or lowered == "formats"
        or lowered.startswith("formats.")
        or "poliglota.formats" in lowered
    )


@pytest.mark.parametrize("module_path", sorted(CORE_DIR.glob("*.py")), ids=lambda p: p.name)
def test_core_does_not_import_format_adapters(module_path: Path) -> None:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    offenders = {name for name in _imported_module_names(tree) if _is_format_adapter_import(name)}
    assert offenders == set(), f"{module_path.name} imports format adapters: {sorted(offenders)}"


def test_locale_rejects_empty_code() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        Locale(code="   ")


def test_locale_str_returns_code_and_keeps_display_name() -> None:
    assert str(Locale("pt_BR")) == "pt_BR"
    assert Locale("en", display_name="English").display_name == "English"


def test_translation_request_and_result_are_format_independent() -> None:
    source = Locale("en")
    target = Locale("pt_BR")
    request = TranslationRequest(source=source, targets=(target,), texts=("Hello",))

    assert request.source.code == "en"
    assert [t.code for t in request.targets] == ["pt_BR"]

    result = TranslationResult(source=source, translations={target.code: ("Olá",)})
    assert result.translation_for(target) == ("Olá",)
    assert result.translation_for(Locale("ja")) is None
    assert result.issues == ()


def test_translation_issue_renders_severity_and_locale() -> None:
    issue = TranslationIssue(
        severity=IssueSeverity.WARNING,
        message="resource not installed",
        locale=Locale("ja"),
    )
    assert str(issue) == "warning: [ja] resource not installed"


class _StubEngine:
    """Minimal test double used to show the engine contract is satisfiable."""

    name = "stub"

    def engine_language(self, locale: Locale) -> str:
        return locale.code.lower()

    def supports(self, source: Locale, target: Locale) -> bool:
        return True

    def translate(self, request: TranslationRequest) -> TranslationResult:
        return TranslationResult(
            source=request.source,
            translations={target.code: request.texts for target in request.targets},
        )


def test_engine_contract_is_usable_without_a_real_engine() -> None:
    engine = _StubEngine()
    request = TranslationRequest(source=Locale("en"), targets=(Locale("es"),), texts=("Hi",))

    assert engine.name == "stub"
    assert engine.supports(request.source, Locale("es"))
    assert engine.engine_language(Locale("pt_BR")) == "pt_br"
    assert engine.translate(request).translation_for(Locale("es")) == ("Hi",)
