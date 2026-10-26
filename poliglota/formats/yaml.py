"""YAML format adapter implementation for Poliglota."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from pathlib import Path

    from poliglota.core import LocalizedDocument, LocalizedResource


class YAMLFormatAdapter:
    """YAML implementation of :class:`poliglota.core.format.FormatAdapter`."""

    name = "yaml"

    def discover(self, root: Path) -> list[LocalizedResource]:
        """Discover YAML files under ``root`` as generic localized resources.

        Searches for files matching patterns:
        - *.yaml / *.yml
        - {locale_code}.yaml / {locale_code}.yml
        - {name}_{locale_code}.yaml / {name}_{locale_code}.yml

        Locale is inferred from filename or directory structure.
        """
        from poliglota.core.format import LocalizedResource
        from poliglota.core.locale import Locale

        resources: list[LocalizedResource] = []

        if not root.exists():
            return resources

        # Recurse all directories for *.yaml and *.yml files
        for yaml_file in root.rglob("*.yaml"):
            locale = self._infer_locale_from_path(yaml_file)
            if locale:
                resources.append(
                    LocalizedResource(
                        path=yaml_file,
                        locale=Locale(locale),
                        format=self.name,
                        attributes={"directory": str(yaml_file.parent.relative_to(root))},
                    )
                )

        for yml_file in root.rglob("*.yml"):
            locale = self._infer_locale_from_path(yml_file)
            if locale:
                resources.append(
                    LocalizedResource(
                        path=yml_file,
                        locale=Locale(locale),
                        format=self.name,
                        attributes={"directory": str(yml_file.parent.relative_to(root))},
                    )
                )

        return resources

    def read(self, path: Path) -> LocalizedDocument:
        """Parse a YAML file into translatable entries and preserved metadata.

        Entries are top-level keys with string values (or recursively flattened).
        Metadata includes YAML comments and structure info (currently minimal).
        """
        from poliglota.core.format import LocalizedDocument
        from poliglota.core.locale import Locale

        yaml_content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(yaml_content)

        if not isinstance(data, dict):
            data = {}

        locale_code = self._infer_locale_from_path(path)

        # Flatten nested YAML into dot-notation keys for translation
        entries = self._flatten_dict(data)

        # Preserve original YAML structure info in metadata
        metadata = {
            "@@yaml_original": yaml_content,
            "@@yaml_structure": self._document_structure(data),
        }

        return LocalizedDocument(
            locale=Locale(locale_code) if locale_code else None,
            entries=entries,
            metadata=metadata,
        )

    def write(self, document: LocalizedDocument, path: Path) -> None:
        """Write ``document`` back as YAML, preserving original structure if available.

        Attempts to reconstruct nested structure from dot-notation keys.
        Falls back to flat structure if original not preserved.
        """
        # Attempt to reconstruct nested structure
        data = self._unflatten_dict(dict(document.entries))

        path.parent.mkdir(parents=True, exist_ok=True)

        # Use safe_dump with preserve formatting options
        yaml_output = yaml.dump(
            data,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=80,
        )

        path.write_text(yaml_output, encoding="utf-8")

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
                result.update(YAMLFormatAdapter._flatten_dict(value, full_key))
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
        """Capture structural information about the YAML document.

        Used to preserve layout, comments, and organization hints.
        """
        return {
            "top_level_keys": list(data.keys()),
            "depth": YAMLFormatAdapter._max_depth(data),
        }

    @staticmethod
    def _max_depth(data: Any, current_depth: int = 0) -> int:
        """Calculate maximum nesting depth of the data structure."""
        if not isinstance(data, dict):
            return current_depth

        if not data:
            return current_depth

        return max(YAMLFormatAdapter._max_depth(v, current_depth + 1) for v in data.values())

    @staticmethod
    def _infer_locale_from_path(path: Path) -> str | None:
        """Infer locale code from file path.

        Patterns supported:
        - {locale_code}.yaml (e.g., en.yaml, pt_BR.yaml)
        - {name}_{locale_code}.yaml (e.g., app_en.yaml, app_pt_BR.yaml)
        - Filename only if matches locale pattern (e.g., en, pt-BR, pt_BR)

        Returns None if no valid locale pattern found.
        """
        stem = path.stem

        # Pattern: {name}_{locale_code}.yaml
        # Match: word_word, word_word_word (e.g., app_en, common_pt_BR)
        match = re.match(r"^(.+?)_([a-z]{2}(?:[_\-][a-zA-Z]{2})?)$", stem)
        if match:
            locale = match.group(2)
            # Normalize: replace - with _ for consistency
            return locale.replace("-", "_").lower()

        # Pattern: {locale_code}.yaml (e.g., en.yaml, pt_BR.yaml, pt-BR.yaml)
        if re.match(r"^[a-z]{2}(?:[_\-][a-zA-Z]{2})?$", stem):
            return stem.replace("-", "_").lower()

        return None
