"""Glossary management for project-specific terminology.

Loads and applies project-specific glossaries to maintain consistent
terminology across translations, independent of translation engine.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Glossary:
    """A project-specific glossary mapping source terms to translated terms.

    Supports multiple languages via separate glossaries per target locale.
    Format: {source_term: translated_term}
    """

    def __init__(self) -> None:
        """Initialize an empty glossary."""
        self._terms: dict[str, dict[str, str]] = {}

    def load_json(self, path: str | Path, locale: str) -> None:
        """Load a glossary from a JSON file.

        JSON format: {"term1": "translation1", "term2": "translation2", ...}

        Args:
            path: Path to JSON glossary file.
            locale: Target locale code (e.g., "pt_BR").

        Raises:
            FileNotFoundError: If file does not exist.
            ValueError: If JSON is invalid or not a flat dict.

        """
        file_path = Path(path)
        if not file_path.exists():
            msg = f"Glossary file not found: {file_path}"
            raise FileNotFoundError(msg)

        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON in glossary {file_path}: {e}"
            raise ValueError(msg) from e

        if not isinstance(data, dict):
            msg = f"Glossary {file_path} must be a JSON object, not {type(data).__name__}"
            raise ValueError(msg)

        # Validate all keys and values are strings
        for key, value in data.items():
            if not isinstance(key, str):
                msg = f"Glossary keys must be strings, got {type(key).__name__} for {key}"
                raise ValueError(msg)
            if not isinstance(value, str):
                msg = f"Glossary values must be strings, got {type(value).__name__} for key '{key}'"
                raise ValueError(msg)

        self._terms[locale] = data

    def load_csv(self, path: str | Path, locale: str) -> None:
        """Load a glossary from a CSV file (source_term,translated_term per line).

        Args:
            path: Path to CSV glossary file.
            locale: Target locale code (e.g., "pt_BR").

        Raises:
            FileNotFoundError: If file does not exist.
            ValueError: If CSV format is invalid.

        """
        file_path = Path(path)
        if not file_path.exists():
            msg = f"Glossary file not found: {file_path}"
            raise FileNotFoundError(msg)

        terms: dict[str, str] = {}
        try:
            with file_path.open("r", encoding="utf-8") as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(",", 1)
                    if len(parts) != 2:
                        msg = (
                            f"CSV glossary {file_path} line {raw_line!r}: expected 2 "
                            "comma-separated values"
                        )
                        raise ValueError(msg)
                    source, target = parts
                    terms[source.strip()] = target.strip()
        except OSError as e:
            msg = f"Error reading glossary {file_path}: {e}"
            raise ValueError(msg) from e

        self._terms[locale] = terms

    def get_for_locale(self, locale: str) -> dict[str, str]:
        """Return the glossary for a specific locale, or empty dict if not loaded."""
        return self._terms.get(locale, {})

    def apply_to_text(self, text: str, locale: str, case_sensitive: bool = True) -> str:
        """Apply glossary terms to a text string.

        Replaces source terms with their translations. Does NOT replace
        terms inside word boundaries to avoid corrupting larger words.

        Args:
            text: Text to apply glossary to.
            locale: Target locale code.
            case_sensitive: If False, matches terms case-insensitively but
                           preserves original case in replacement.

        Returns:
            Text with glossary terms replaced.

        """
        glossary = self.get_for_locale(locale)
        if not glossary:
            return text

        result = text
        for source, target in glossary.items():
            if case_sensitive:
                result = self._replace_term(result, source, target, case_sensitive=True)
            else:
                result = self._replace_term(result, source, target, case_sensitive=False)

        return result

    @staticmethod
    def _replace_term(text: str, source: str, target: str, case_sensitive: bool = True) -> str:
        """Replace a term in text without breaking word boundaries.

        Only replaces when source term is a standalone word or phrase.
        """
        import re

        # Escape special regex characters
        escaped_source = re.escape(source)

        # Match term surrounded by word boundaries
        if case_sensitive:
            pattern = r"\b" + escaped_source + r"\b"
            return re.sub(pattern, target, text)
        pattern = r"\b" + escaped_source + r"\b"
        return re.sub(pattern, target, text, flags=re.IGNORECASE)

    def apply_to_entries(
        self, entries: dict[str, Any], locale: str, case_sensitive: bool = True
    ) -> dict[str, Any]:
        """Apply glossary to all string values in an entries dict.

        Only processes string values; leaves other types unchanged.

        Args:
            entries: Dict mapping entry keys to values.
            locale: Target locale code.
            case_sensitive: Whether to match terms case-sensitively.

        Returns:
            Dict with glossary applied to string values.

        """
        glossary = self.get_for_locale(locale)
        if not glossary:
            return entries

        result: dict[str, Any] = {}
        for key, value in entries.items():
            if isinstance(value, str):
                result[key] = self.apply_to_text(value, locale, case_sensitive)
            else:
                result[key] = value

        return result
