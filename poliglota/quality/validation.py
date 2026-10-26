"""Validation checkers for translation quality and integrity.

Reusable validators that work with any format adapter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from poliglota.core.quality import ValidationIssue
from poliglota.quality.placeholders import ArbPlaceholderProtector

if TYPE_CHECKING:
    from collections.abc import Mapping


class PlaceholderValidator:
    """Validates placeholder consistency between source and target entries."""

    def __init__(self, format_name: str = "arb") -> None:
        """Initialize with protector for a specific format.

        Args:
            format_name: Format name ("arb", etc.).

        """
        if format_name == "arb":
            self._protector = ArbPlaceholderProtector()
        else:
            msg = f"No placeholder protector for format '{format_name}'"
            raise ValueError(msg)

    def validate_entry_pair(
        self, key: str, source_value: str, target_value: str
    ) -> list[ValidationIssue]:
        """Check that source and target have identical placeholders.

        Args:
            key: Entry key (for error reporting).
            source_value: Source entry value.
            target_value: Target entry value.

        Returns:
            List of validation issues.

        """
        issues = []

        source_phs = self._protector.detect(str(source_value))
        target_phs = self._protector.detect(str(target_value))

        if source_phs != target_phs:
            missing_in_target = source_phs - target_phs
            extra_in_target = target_phs - source_phs
            msg = f"Placeholder mismatch for key '{key}'"
            if missing_in_target:
                msg += f"; missing in target: {sorted(missing_in_target)}"
            if extra_in_target:
                msg += f"; extra in target: {sorted(extra_in_target)}"

            issues.append(
                ValidationIssue(
                    severity="error",
                    message=msg,
                    key=key,
                )
            )

        return issues

    def validate_entries(
        self, source_entries: Mapping[str, Any], target_entries: Mapping[str, Any]
    ) -> list[ValidationIssue]:
        """Check placeholder consistency across all matching entries.

        Args:
            source_entries: Source translation entries.
            target_entries: Target translation entries.

        Returns:
            List of validation issues.

        """
        issues = []

        for key, source_value in source_entries.items():
            if key not in target_entries:
                continue

            target_value = target_entries[key]
            issues.extend(self.validate_entry_pair(key, source_value, target_value))

        return issues


class KeyValidator:
    """Validates key consistency between source and target entries."""

    def validate_keys(
        self, source_entries: Mapping[str, Any], target_entries: Mapping[str, Any]
    ) -> list[ValidationIssue]:
        """Check that target has all keys from source.

        Args:
            source_entries: Source translation entries.
            target_entries: Target translation entries.

        Returns:
            List of validation issues.

        """
        issues = []

        source_keys = set(source_entries.keys())
        target_keys = set(target_entries.keys())
        missing = sorted(source_keys - target_keys)

        if missing:
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=f"Missing keys in target: {', '.join(missing)}",
                )
            )

        extra = sorted(target_keys - source_keys)
        if extra:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    message=f"Extra keys in target (not in source): {', '.join(extra)}",
                )
            )

        return issues


class GlossaryValidator:
    """Validates that glossary terms are applied to entries."""

    def validate_glossary_coverage(
        self,
        entries: Mapping[str, Any],
        glossary: Mapping[str, str],
        locale: str,
    ) -> list[ValidationIssue]:
        """Check that glossary terms appear in translated entries.

        Generates warnings (not errors) for missing glossary terms,
        as translation may use equivalent terminology.

        Args:
            entries: Translated entries to check.
            glossary: Source-to-target glossary mapping.
            locale: Target locale (for error reporting).

        Returns:
            List of validation issues.

        """
        issues = []

        for source_term, target_term in glossary.items():
            found = False
            for value in entries.values():
                if isinstance(value, str) and target_term in value:
                    found = True
                    break

            if not found:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        message=(
                            f"Glossary term '{source_term}' -> '{target_term}' not found "
                            f"in any entry for locale {locale}"
                        ),
                    )
                )

        return issues


class StructuralValidator:
    """Validates structural integrity of translated documents."""

    def validate_structure(
        self, source_entries: Mapping[str, Any], target_entries: Mapping[str, Any]
    ) -> list[ValidationIssue]:
        """Run all structural checks.

        Args:
            source_entries: Source translation entries.
            target_entries: Target translation entries.

        Returns:
            List of validation issues.

        """
        issues = []

        # Check keys
        key_validator = KeyValidator()
        issues.extend(key_validator.validate_keys(source_entries, target_entries))

        # Check placeholders
        placeholder_validator = PlaceholderValidator("arb")
        issues.extend(placeholder_validator.validate_entries(source_entries, target_entries))

        return issues
