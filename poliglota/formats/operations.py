"""Format-agnostic operations for validation, sync and discovery.

These functions work with any FormatAdapter, not just ARB.
They provide the core business logic that the CLI and other consumers need.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from poliglota.core.locale import Locale
from poliglota.language_detection import detect_source_locale, normalize_locale_code

if TYPE_CHECKING:
    from poliglota.core import FormatAdapter


def _fallback_files(root_path: Path, format_name: str) -> list[Path]:
    """List files for a format when the adapter cannot infer locales from names."""
    suffixes: tuple[str, ...]
    if format_name.lower() in {"yaml", "yml"}:
        suffixes = (".yaml", ".yml")
    elif format_name.lower() == "json":
        suffixes = (".json",)
    elif format_name.lower() == "xml":
        suffixes = (".xml",)
    elif format_name.lower() == "arb":
        suffixes = (".arb",)
    else:
        suffixes = (f".{format_name.lower()}",)

    files: list[Path] = []
    for suffix in suffixes:
        files.extend(root_path.rglob(f"*{suffix}"))

    if format_name.lower() == "json":
        files = [
            path
            for path in files
            if path.name not in {"package.json", "tsconfig.json", "package-lock.json"}
        ]

    seen: set[Path] = set()
    unique: list[Path] = []
    for path in files:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def _resource_group_key(resource: Any) -> str:
    """Return a stable grouping key for matching source/target files.

    ARB files identify a logical bundle by ``module``. Other formats do not carry
    an explicit module, so they should be matched by the enclosing directory name
    or a normalized filename stem when no better identifier exists.
    """
    attributes = getattr(resource, "attributes", {}) or {}
    module = attributes.get("module")
    if module:
        return str(module)

    path = getattr(resource, "path", None)
    if path is not None:
        candidate = path.parent.name or path.stem
        if candidate and candidate not in {".", ""}:
            return candidate
    return "default"


def discover_resources(adapter: FormatAdapter, root: str | Path) -> dict[str, list]:
    """Discover localized resources for a format under root.

    Returns a dict mapping locale codes to lists of LocalizedResource objects.
    """
    from poliglota.core.format import LocalizedResource

    root_path = Path(root)
    resources = adapter.discover(root_path)

    if not resources:
        resources = [
            LocalizedResource(
                path=path,
                locale=Locale("und"),
                format=adapter.name,
                attributes={"directory": str(path.parent.relative_to(root_path))},
            )
            for path in _fallback_files(root_path, adapter.name)
        ]

    unresolved = [
        resource
        for resource in resources
        if not getattr(resource.locale, "code", "").strip()
        or resource.locale.code.lower() in {"und", "unknown"}
    ]
    if unresolved:
        detection = detect_source_locale(root_path, adapter.name, adapter=adapter)
        detected_code = None
        if not detection.inconclusive and detection.candidates:
            detected_code = normalize_locale_code(detection.candidates[0].locale_code)

        if detected_code is not None:
            resolved_locale = Locale(detected_code)
            resources = [
                replace(resource, locale=resolved_locale)
                if resource.locale.code.lower() in {"und", "unknown"}
                else resource
                for resource in resources
            ]

    by_locale: dict[str, list] = {}
    for resource in resources:
        locale_code = normalize_locale_code(resource.locale.code) or resource.locale.code
        if locale_code.lower() in {"und", "unknown"}:
            continue
        by_locale.setdefault(locale_code, []).append(resource)
    return by_locale


def validate_with_adapter(
    adapter: FormatAdapter,
    root: str | Path,
    source_locale: str,
    check_keys: bool = True,
    check_placeholders: bool = True,
) -> list[str]:
    """Validate target locale files against a source locale using the given adapter.

    Returns a list of human-readable issues (missing keys and placeholder mismatches).
    An empty list means validation passed.

    Args:
        adapter: FormatAdapter instance.
        root: Project root directory.
        source_locale: Source locale code.
        check_keys: Enable key consistency validation (default: True).
        check_placeholders: Enable placeholder consistency validation (default: True).

    """
    root_path = Path(root)
    by_locale = discover_resources(adapter, root_path)

    source_key = normalize_locale_code(source_locale) or source_locale
    if source_key not in by_locale:
        if source_locale in by_locale:
            source_key = source_locale
        else:
            return [f"Missing source locale '{source_locale}' in {root_path}"]

    issues: list[str] = []
    source_resources = by_locale[source_key]

    for locale, locale_resources in by_locale.items():
        if locale == source_key:
            continue

        for source_resource in source_resources:
            source_doc = adapter.read(source_resource.path)
            source_group = _resource_group_key(source_resource)

            for target_resource in locale_resources:
                target_group = _resource_group_key(target_resource)

                if source_group != target_group:
                    continue

                target_doc = adapter.read(target_resource.path)

                # Check for missing keys
                if check_keys:
                    source_keys = set(source_doc.entries.keys())
                    target_keys = set(target_doc.entries.keys())
                    missing = sorted(source_keys - target_keys)

                    if missing:
                        joined_missing = ", ".join(missing)
                        issues.append(
                            f"{locale}:{target_resource.path.name} missing keys -> {joined_missing}"
                        )

                # Check for placeholder mismatches using format-specific validation
                if check_placeholders:
                    _validate_placeholders_for_adapter(
                        adapter, source_doc, target_doc, locale, target_resource, issues
                    )

    return issues


def _validate_placeholders_for_adapter(
    adapter: FormatAdapter,
    source_doc: Any,
    target_doc: Any,
    locale: str,
    target_resource: Any,
    issues: list[str],
) -> None:
    """Validate placeholders between source and target documents.

    For ARB, this checks {placeholder} syntax. Format-specific implementations
    can override or extend this logic.
    """
    if adapter.name == "arb":
        from .arb import validate_placeholders

        placeholder_issues = validate_placeholders(source_doc.entries, target_doc.entries)
        issues.extend(
            f"{locale}:{target_resource.path.name} {issue}" for issue in placeholder_issues
        )


def sync_with_adapter(
    adapter: FormatAdapter, root: str | Path, source_locale: str, dry_run: bool = False
) -> int:
    """Copy missing keys from source locale to target locales using the given adapter.

    Returns the number of target files that were (or, with dry_run, would be) changed.
    Raises ValueError when the source locale is absent.
    """
    root_path = Path(root)
    by_locale = discover_resources(adapter, root_path)

    source_key = normalize_locale_code(source_locale) or source_locale
    source_resources = by_locale.get(source_key, [])
    if not source_resources:
        msg = f"Source locale '{source_locale}' not found in {root_path}"
        raise ValueError(msg)

    changed = 0
    all_resources = [r for resources in by_locale.values() for r in resources]

    for target_resource in all_resources:
        target_key = (
            normalize_locale_code(target_resource.locale.code) or target_resource.locale.code
        )
        if target_key == source_key:
            continue

        target_group = _resource_group_key(target_resource)

        for source_resource in source_resources:
            source_group = _resource_group_key(source_resource)

            if source_group != target_group:
                continue

            source_doc = adapter.read(source_resource.path)
            target_doc = adapter.read(target_resource.path)

            missing = {
                key: value
                for key, value in source_doc.entries.items()
                if key not in target_doc.entries
            }

            if not missing:
                continue

            if not dry_run:
                updated_entries = dict(target_doc.entries)
                updated_entries.update(missing)

                updated_doc = replace(target_doc, entries=updated_entries)
                adapter.write(updated_doc, target_resource.path)

            changed += 1
            break

    return changed
