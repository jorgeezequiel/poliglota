"""Tests for translation quality validators."""

from __future__ import annotations

import pytest

from poliglota.core.quality import ValidationIssue
from poliglota.quality.validation import (
    PlaceholderValidator,
    KeyValidator,
    GlossaryValidator,
    StructuralValidator,
)


class TestPlaceholderValidator:
    """Tests for placeholder validation between source and target."""

    def test_validate_entry_pair_matching_placeholders(self) -> None:
        """Validator accepts entries with identical placeholders."""
        validator = PlaceholderValidator("arb")

        issues = validator.validate_entry_pair("greeting", "Hello {name}", "Hola {name}")

        assert issues == []

    def test_validate_entry_pair_missing_placeholder_in_target(self) -> None:
        """Validator detects missing placeholder in target."""
        validator = PlaceholderValidator("arb")

        issues = validator.validate_entry_pair("greeting", "Hello {name}", "Hola")

        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert "placeholder mismatch" in issues[0].message.lower()
        assert issues[0].key == "greeting"

    def test_validate_entry_pair_extra_placeholder_in_target(self) -> None:
        """Validator detects extra placeholder in target."""
        validator = PlaceholderValidator("arb")

        issues = validator.validate_entry_pair("greeting", "Hello", "Hola {name}")

        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert "placeholder mismatch" in issues[0].message.lower()

    def test_validate_entry_pair_multiple_placeholders(self) -> None:
        """Validator checks all placeholders in multi-placeholder entries."""
        validator = PlaceholderValidator("arb")

        issues = validator.validate_entry_pair(
            "message",
            "Hello {first} {last}",
            "Hola {first}",  # Missing {last}
        )

        assert len(issues) == 1
        assert "placeholder mismatch" in issues[0].message.lower()

    def test_validate_entries_across_dict(self) -> None:
        """Validator checks placeholder consistency across entries dict."""
        validator = PlaceholderValidator("arb")

        source_entries = {
            "greeting": "Hello {name}",
            "farewell": "Goodbye {name}",
            "message": "You have {count} items",
        }
        target_entries = {
            "greeting": "Hola {name}",
            "farewell": "Adiós {name}",
            "message": "Tienes {count} artículos",
        }

        issues = validator.validate_entries(source_entries, target_entries)

        assert issues == []

    def test_validate_entries_skips_missing_keys(self) -> None:
        """Validator skips entries missing in target."""
        validator = PlaceholderValidator("arb")

        source_entries = {"greeting": "Hello {name}", "farewell": "Goodbye {name}"}
        target_entries = {"greeting": "Hola {name}"}  # Missing "farewell"

        issues = validator.validate_entries(source_entries, target_entries)

        # Should not complain about missing "farewell"; that's KeyValidator's job
        assert issues == []

    def test_validate_entries_detects_multiple_errors(self) -> None:
        """Validator reports all placeholder mismatches."""
        validator = PlaceholderValidator("arb")

        source_entries = {
            "greeting": "Hello {name}",
            "farewell": "Goodbye {user}",
        }
        target_entries = {
            "greeting": "Hola",  # Missing {name}
            "farewell": "Adiós {user}",  # OK
        }

        issues = validator.validate_entries(source_entries, target_entries)

        assert len(issues) == 1
        assert issues[0].key == "greeting"


class TestKeyValidator:
    """Tests for key consistency validation."""

    def test_validate_keys_matching_keys(self) -> None:
        """Validator accepts entries with matching keys."""
        validator = KeyValidator()

        source_entries = {"greeting": "Hello", "farewell": "Goodbye"}
        target_entries = {"greeting": "Hola", "farewell": "Adiós"}

        issues = validator.validate_keys(source_entries, target_entries)

        assert issues == []

    def test_validate_keys_missing_in_target(self) -> None:
        """Validator detects keys missing in target."""
        validator = KeyValidator()

        source_entries = {"greeting": "Hello", "farewell": "Goodbye", "neutral": "Hi"}
        target_entries = {"greeting": "Hola", "farewell": "Adiós"}

        issues = validator.validate_keys(source_entries, target_entries)

        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert "missing keys" in issues[0].message.lower()
        assert "neutral" in issues[0].message

    def test_validate_keys_extra_in_target(self) -> None:
        """Validator warns about extra keys in target."""
        validator = KeyValidator()

        source_entries = {"greeting": "Hello"}
        target_entries = {"greeting": "Hola", "extra": "Extra translation"}

        issues = validator.validate_keys(source_entries, target_entries)

        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert "extra keys" in issues[0].message.lower()

    def test_validate_keys_empty_source(self) -> None:
        """Validator handles empty source entries."""
        validator = KeyValidator()

        source_entries = {}
        target_entries = {"greeting": "Hola"}

        issues = validator.validate_keys(source_entries, target_entries)

        assert len(issues) == 1
        assert issues[0].severity == "warning"


class TestGlossaryValidator:
    """Tests for glossary coverage validation."""

    def test_validate_glossary_coverage_term_found(self) -> None:
        """Validator accepts when glossary term is found in entries."""
        validator = GlossaryValidator()

        # entries contain the TARGET translations, glossary maps source -> target
        entries = {"greeting": "Hola, usuario!"}
        glossary = {"Hello": "Hola"}

        issues = validator.validate_glossary_coverage(entries, glossary, "es_ES")

        assert issues == []

    def test_validate_glossary_coverage_term_not_found(self) -> None:
        """Validator warns when glossary term is not found."""
        validator = GlossaryValidator()

        entries = {"greeting": "Hi there!"}
        glossary = {"Hello": "Hola"}  # "Hello" not in entries

        issues = validator.validate_glossary_coverage(entries, glossary, "es_ES")

        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert "not found" in issues[0].message.lower()

    def test_validate_glossary_coverage_multiple_terms(self) -> None:
        """Validator checks all glossary terms."""
        validator = GlossaryValidator()

        entries = {"greeting": "Hola allí!", "settings": "Configuración"}
        glossary = {"Hello": "Hola", "Goodbye": "Adiós"}  # "Adiós" not found

        issues = validator.validate_glossary_coverage(entries, glossary, "es_ES")

        assert len(issues) == 1
        assert "Adiós" in issues[0].message

    def test_validate_glossary_coverage_empty_glossary(self) -> None:
        """Validator handles empty glossary."""
        validator = GlossaryValidator()

        entries = {"greeting": "Hello"}
        glossary = {}

        issues = validator.validate_glossary_coverage(entries, glossary, "es_ES")

        assert issues == []

    def test_validate_glossary_coverage_non_string_entries(self) -> None:
        """Validator handles non-string entry values."""
        validator = GlossaryValidator()

        entries = {"count": 42, "greeting": "Hola"}
        glossary = {"Hello": "Hola"}

        issues = validator.validate_glossary_coverage(entries, glossary, "es_ES")

        assert issues == []  # Only checks string values


class TestStructuralValidator:
    """Tests for structural integrity validation."""

    def test_validate_structure_all_checks_pass(self) -> None:
        """Validator passes when all structural checks pass."""
        validator = StructuralValidator()

        source_entries = {
            "greeting": "Hello {name}",
            "count": "You have {count} items",
        }
        target_entries = {
            "greeting": "Hola {name}",
            "count": "Tienes {count} artículos",
        }

        issues = validator.validate_structure(source_entries, target_entries)

        assert issues == []

    def test_validate_structure_detects_key_mismatch(self) -> None:
        """Validator detects key mismatches."""
        validator = StructuralValidator()

        source_entries = {"greeting": "Hello", "farewell": "Goodbye"}
        target_entries = {"greeting": "Hola"}  # Missing "farewell"

        issues = validator.validate_structure(source_entries, target_entries)

        assert any("missing keys" in issue.message.lower() for issue in issues)

    def test_validate_structure_detects_placeholder_mismatch(self) -> None:
        """Validator detects placeholder mismatches."""
        validator = StructuralValidator()

        source_entries = {"greeting": "Hello {name}"}
        target_entries = {"greeting": "Hola"}  # Missing {name}

        issues = validator.validate_structure(source_entries, target_entries)

        assert any("placeholder" in issue.message.lower() for issue in issues)

    def test_validate_structure_returns_validation_issues(self) -> None:
        """Validator returns ValidationIssue objects."""
        validator = StructuralValidator()

        source_entries = {"greeting": "Hello {name}"}
        target_entries = {"greeting": "Hola"}

        issues = validator.validate_structure(source_entries, target_entries)

        assert len(issues) > 0
        assert all(isinstance(issue, ValidationIssue) for issue in issues)


class TestValidationIssue:
    """Tests for ValidationIssue dataclass."""

    def test_validation_issue_creation(self) -> None:
        """ValidationIssue can be created with required fields."""
        issue = ValidationIssue(severity="error", message="Test error")

        assert issue.severity == "error"
        assert issue.message == "Test error"
        assert issue.key is None
        assert issue.locale is None

    def test_validation_issue_with_all_fields(self) -> None:
        """ValidationIssue accepts all optional fields."""
        issue = ValidationIssue(
            severity="warning",
            message="Test warning",
            key="test_key",
            locale="pt_BR",
        )

        assert issue.severity == "warning"
        assert issue.message == "Test warning"
        assert issue.key == "test_key"
        assert issue.locale == "pt_BR"

    def test_validation_issue_is_frozen(self) -> None:
        """ValidationIssue is immutable (frozen dataclass)."""
        issue = ValidationIssue(severity="error", message="Test")

        with pytest.raises(AttributeError):
            issue.severity = "warning"
