"""ARB (Flutter / ICU MessageFormat) localization adapter.

This module owns everything ARB-specific: file discovery, the
``app_<module>_<locale>.arb`` path convention, placeholder validation and key
synchronization. It is a format adapter: the core does not depend on it.

Besides the low-level helpers used by the CLI it exposes
:class:`ARBFormatAdapter`, the implementation of
:class:`poliglota.core.format.FormatAdapter` for ARB files.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from poliglota.config import DEFAULT_ARB_GLOB
from poliglota.core.format import LocalizedDocument, LocalizedResource
from poliglota.core.locale import Locale

_PLACEHOLDER_RE = re.compile(r"\{\s*([A-Za-z0-9_]+)\s*\}")

# Minimum number of underscore-separated parts after ``app_`` in an ARB file
# name: at least one module segment plus a two-part locale.
_MIN_TAIL_PARTS = 3


@dataclass(frozen=True, slots=True)
class ArbFile:
    """An ARB file discovered under a project root."""

    path: Path
    locale: str
    module: str

    @property
    def file_stem(self) -> str:
        """Return the file stem (file name without the ``.arb`` extension)."""
        return self.path.stem


def discover_arb_files(root: str | Path) -> list[ArbFile]:
    """Find every ARB file under ``root`` that follows the path convention."""
    root_path = Path(root)
    files: list[ArbFile] = []

    for arb_path in sorted(root_path.glob(DEFAULT_ARB_GLOB)):
        if arb_path.is_file():
            locale = locale_from_arb_path(arb_path)
            module = module_from_arb_path(arb_path)
            if locale and module:
                files.append(ArbFile(path=arb_path, locale=locale, module=module))
    return files


def load_arb(path: str | Path) -> dict[str, Any]:
    """Load an ARB file and ensure it contains a JSON object."""
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        msg = f"ARB file {file_path} must contain a JSON object"
        raise ValueError(msg)  # noqa: TRY004 - parsed-content check, not an argument type
    return data


def locale_from_arb_path(path: str | Path) -> str | None:
    """Extract the locale from an ``app_<module>_<locale>.arb`` file name."""
    file_name = Path(path).name
    stem = Path(file_name).stem
    if not stem.startswith("app_"):
        return None
    tail = stem[len("app_") :].split("_")
    if len(tail) < _MIN_TAIL_PARTS:
        return None
    locale = "_".join(tail[-2:])
    if locale:
        return locale
    return None


def module_from_arb_path(path: str | Path) -> str | None:
    """Extract the module from an ``app_<module>_<locale>.arb`` file name."""
    file_name = Path(path).name
    stem = file_name.removesuffix(".arb")
    if not stem.startswith("app_"):
        return None
    tail = stem[len("app_") :].split("_")
    if len(tail) < _MIN_TAIL_PARTS:
        return None
    module = "_".join(tail[:-2])
    if module:
        return module
    return None


def arb_content_keys(data: dict[str, Any]) -> set[str]:
    """Return the translatable keys (those not starting with ``@``)."""
    return {key for key in data if not key.startswith("@")}


def arb_file_key(path: str | Path, locale: str | None = None) -> str:
    """Return the module stem of an ARB file, optionally stripping a locale."""
    file_name = Path(path).name
    stem = file_name.removesuffix(".arb")
    if locale:
        suffix = f"_{locale}"
        stem = stem.removesuffix(suffix)
    return stem


def validate_root(root: str | Path, source_locale: str) -> list[str]:
    """Validate target ARB files against a source locale.

    Returns a list of human-readable issues (missing keys and placeholder
    mismatches). An empty list means the source locale was found and every
    comparable target file matched.
    """
    root_path = Path(root)
    files = discover_arb_files(root_path)
    file_map: dict[str, list[Path]] = {}
    for arb_file in files:
        file_map.setdefault(arb_file.locale, []).append(arb_file.path)

    if source_locale not in file_map:
        return [f"Missing source locale '{source_locale}' in {root_path}"]

    issues: list[str] = []
    source_files = file_map[source_locale]
    for locale, locale_files in file_map.items():
        if locale == source_locale:
            continue
        for source_file in source_files:
            source_data = load_arb(source_file)
            source_keys = arb_content_keys(source_data)
            source_module = module_from_arb_path(source_file)
            for locale_file in locale_files:
                if source_module != module_from_arb_path(locale_file):
                    continue
                target_data = load_arb(locale_file)
                target_keys = arb_content_keys(target_data)
                missing = sorted(source_keys - target_keys)
                if missing:
                    issues.append(
                        f"{locale}:{locale_file.name} missing keys -> {', '.join(missing)}"
                    )
                placeholder_issues = validate_placeholders(source_data, target_data)
                issues.extend(
                    f"{locale}:{locale_file.name} {issue}" for issue in placeholder_issues
                )
    return issues


def validate_placeholders(source_data: dict, target_data: dict) -> list[str]:
    """Report placeholder differences between matching source/target keys."""
    issues: list[str] = []
    for key, source_value in source_data.items():
        if key.startswith("@"):
            continue
        if key not in target_data:
            continue
        source_placeholders = set(_PLACEHOLDER_RE.findall(str(source_value)))
        target_placeholders = set(_PLACEHOLDER_RE.findall(str(target_data[key])))
        if source_placeholders != target_placeholders:
            issues.append(
                f"placeholder mismatch for '{key}' -> "
                f"source={sorted(source_placeholders)} target={sorted(target_placeholders)}"
            )
    return issues


def sync_locale_files(root: str | Path, source_locale: str, dry_run: bool = False) -> int:
    """Copy missing non-metadata keys from the source locale into target files.

    Returns the number of target files that were (or, with ``dry_run``, would
    be) changed. Raises ``ValueError`` when the source locale is absent.
    """
    root_path = Path(root)
    files = discover_arb_files(root_path)
    by_locale: dict[str, list[ArbFile]] = {}
    for arb_file in files:
        by_locale.setdefault(arb_file.locale, []).append(arb_file)

    source_files = by_locale.get(source_locale, [])
    if not source_files:
        msg = f"Source locale '{source_locale}' not found in {root_path}"
        raise ValueError(msg)

    changed = 0
    for arb_file in files:
        if arb_file.locale == source_locale:
            continue
        for source in source_files:
            if arb_file.module == source.module and arb_file.path.stem.removesuffix(
                f"_{arb_file.locale}"
            ) == source.path.stem.removesuffix(f"_{source.locale}"):
                source_data = load_arb(source.path)
                target_data = load_arb(arb_file.path)
                missing = {
                    key: value
                    for key, value in source_data.items()
                    if key not in target_data and not key.startswith("@")
                }
                if not missing:
                    continue
                if not dry_run:
                    target_data.update(missing)
                    arb_file.path.write_text(
                        json.dumps(target_data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                changed += 1
    return changed


class ARBFormatAdapter:
    """ARB implementation of :class:`poliglota.core.format.FormatAdapter`."""

    name = "arb"

    def discover(self, root: Path) -> list[LocalizedResource]:
        """Discover ARB files under ``root`` as generic localized resources."""
        return [
            LocalizedResource(
                path=arb_file.path,
                locale=Locale(arb_file.locale),
                format=self.name,
                attributes={"module": arb_file.module},
            )
            for arb_file in discover_arb_files(root)
        ]

    def read(self, path: Path) -> LocalizedDocument:
        """Parse an ARB file into translatable entries and preserved metadata."""
        data = load_arb(path)
        locale_code = self._document_locale(data, path)
        entries = {key: value for key, value in data.items() if not key.startswith("@")}
        metadata = {key: value for key, value in data.items() if key.startswith("@")}
        return LocalizedDocument(
            locale=Locale(locale_code) if locale_code else None,
            entries=entries,
            metadata=metadata,
        )

    def write(self, document: LocalizedDocument, path: Path) -> None:
        """Write ``document`` back as ARB, preserving its metadata verbatim."""
        payload: dict[str, Any] = {}
        if "@@locale" not in document.metadata and document.locale is not None:
            payload["@@locale"] = document.locale.code
        payload.update(document.metadata)
        payload.update(document.entries)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _document_locale(data: dict[str, Any], path: Path) -> str | None:
        header = data.get("@@locale")
        if isinstance(header, str) and header:
            return header
        return locale_from_arb_path(path)
