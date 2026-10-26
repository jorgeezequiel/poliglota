"""Quality assurance abstractions for translation consistency and integrity.

This module provides reusable protocols and base classes for validating,
protecting, and improving translations across any format adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """A single validation problem detected in a translation."""

    severity: str  # "error" or "warning"
    message: str
    key: str | None = None  # Which entry key has the issue, if applicable
    locale: str | None = None  # Which locale has the issue, if applicable


class PlaceholderProtector(Protocol):
    """Protects and restores placeholders in text before and after translation."""

    def mask(self, text: str) -> tuple[str, dict[str, str]]:
        """Replace placeholders with unique tokens.

        Returns (masked_text, placeholders_map) where placeholders_map
        is {token: original_placeholder}.
        """
        ...

    def restore(self, text: str, placeholders_map: dict[str, str]) -> str:
        """Restore placeholders from tokens.

        Returns text with placeholders replaced back.
        """
        ...

    def detect(self, text: str) -> set[str]:
        """Return all placeholders found in text."""
        ...


class TermConsistencyValidator(Protocol):
    """Validates that glossary terms are applied consistently."""

    def check_consistency(
        self, entries: Mapping[str, Any], glossary: Mapping[str, str], locale: str
    ) -> list[ValidationIssue]:
        """Check if glossary terms appear in translated entries.

        Glossary is {source_term: translated_term}.
        """
        ...


class StructuralValidator(Protocol):
    """Validates technical integrity of translated documents."""

    def check_structure(
        self, source_entries: Mapping[str, Any], target_entries: Mapping[str, Any]
    ) -> list[ValidationIssue]:
        """Check structural consistency between source and target.

        May verify: keys, placeholders, nesting, format-specific syntax.
        """
        ...
