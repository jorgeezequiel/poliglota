"""JSON format adapter implementation for Poliglota."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from poliglota.core import FormatAdapter, LocalizedDocument, LocalizedResource
    from poliglota.core.locale import Locale


class JSONFormatAdapter:
    """JSON implementation of :class:`poliglota.core.format.FormatAdapter`."""

    name = "json"

    def discover(self, root: Path) -> list[LocalizedResource]:
        """Discover JSON files under ``root`` as generic localized resources.
        
        Searches for files matching patterns:
        - *.json
        - {locale_code}.json
        - {name}_{locale_code}.json
        
        Locale is inferred from filename or directory structure.
        """
        from poliglota.core.format import LocalizedResource
        from poliglota.core.locale import Locale

        resources: list[LocalizedResource] = []
        
        if not root.exists():
            return resources
        
        # Recurse all directories for *.json files
        for json_file in root.rglob("*.json"):
            # Skip certain patterns (e.g., package.json, tsconfig.json)
            if json_file.name in ("package.json", "tsconfig.json", "package-lock.json"):
                continue
            
            locale = self._infer_locale_from_path(json_file)
            if locale:
                resources.append(
                    LocalizedResource(
                        path=json_file,
                        locale=Locale(locale),
                        format=self.name,
                        attributes={"directory": str(json_file.parent.relative_to(root))},
                    )
                )
        
        return resources

    def read(self, path: Path) -> LocalizedDocument:
        """Parse a JSON file into translatable entries and preserved metadata.
        
        Entries are top-level keys with string values (or recursively flattened).
        Metadata includes JSON structure info and non-string values.
        """
        from poliglota.core.format import LocalizedDocument
        from poliglota.core.locale import Locale

        json_content = path.read_text(encoding="utf-8")
        data = json.loads(json_content)
        
        if not isinstance(data, dict):
            data = {}
        
        locale_code = self._infer_locale_from_path(path)
        
        # Flatten nested JSON into dot-notation keys for translation
        entries = self._flatten_dict(data)
        
        # Preserve original JSON structure and non-translatable metadata
        metadata = {
            "@@json_original": json_content,
            "@@json_structure": self._document_structure(data),
        }
        
        return LocalizedDocument(
            locale=Locale(locale_code) if locale_code else None,
            entries=entries,
            metadata=metadata,
        )

    def write(self, document: LocalizedDocument, path: Path) -> None:
        """Write ``document`` back as JSON, preserving original structure if available.
        
        Attempts to reconstruct nested structure from dot-notation keys.
        Falls back to flat structure if original not preserved.
        """
        # Convert entries to dict if needed (LocalizedDocument.entries is Mapping)
        entries_dict = dict(document.entries)
        
        # Attempt to reconstruct nested structure
        data = self._unflatten_dict(entries_dict)
        
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use json.dumps with pretty printing
        json_output = json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        )
        
        path.write_text(json_output + "\n", encoding="utf-8")

    @staticmethod
    def _flatten_dict(data: dict, prefix: str = "") -> dict[str, Any]:
        """Flatten nested dict into dot-notation keys.
        
        Example:
            {"user": {"name": "Alice"}} -> {"user.name": "Alice"}
        """
        result = {}
        for key, value in data.items():
            full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
            
            if isinstance(value, dict):
                result.update(JSONFormatAdapter._flatten_dict(value, full_key))
            elif isinstance(value, (str, int, float, bool)):
                result[full_key] = str(value)
        
        return result

    @staticmethod
    def _unflatten_dict(data: dict[str, Any]) -> dict:
        """Reconstruct nested dict from dot-notation keys.
        
        Example:
            {"user.name": "Alice"} -> {"user": {"name": "Alice"}}
        """
        result = {}
        for key, value in data.items():
            parts = key.split(".")
            current = result
            
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            current[parts[-1]] = value
        
        return result

    @staticmethod
    def _document_structure(data: dict) -> dict[str, Any]:
        """Capture structural information about the JSON document.
        
        Used to preserve layout and organization hints.
        """
        return {
            "top_level_keys": list(data.keys()),
            "depth": JSONFormatAdapter._max_depth(data),
        }

    @staticmethod
    def _max_depth(data: Any, current_depth: int = 0) -> int:
        """Calculate maximum nesting depth of the data structure."""
        if not isinstance(data, dict):
            return current_depth
        
        if not data:
            return current_depth
        
        return max(
            JSONFormatAdapter._max_depth(v, current_depth + 1)
            for v in data.values()
        )

    @staticmethod
    def _infer_locale_from_path(path: Path) -> str | None:
        """Infer locale code from file path.
        
        Patterns supported:
        - {locale_code}.json (e.g., en.json, pt_BR.json)
        - {name}_{locale_code}.json (e.g., app_en.json, app_pt_BR.json)
        - Filename only if matches locale pattern (e.g., en, pt-BR, pt_BR)
        
        Returns None if no valid locale pattern found.
        """
        stem = path.stem
        
        # Pattern: {name}_{locale_code}.json
        # Match: word_word, word_word_word (e.g., app_en, common_pt_BR)
        match = re.match(r"^(.+?)_([a-z]{2}(?:[_\-][a-zA-Z]{2})?)$", stem)
        if match:
            locale = match.group(2)
            # Normalize: replace - with _ for consistency
            return locale.replace("-", "_").lower()
        
        # Pattern: {locale_code}.json (e.g., en.json, pt_BR.json, pt-BR.json)
        if re.match(r"^[a-z]{2}(?:[_\-][a-zA-Z]{2})?$", stem):
            return stem.replace("-", "_").lower()
        
        return None
