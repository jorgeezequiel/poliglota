"""Format-agnostic operations for validation, sync and discovery.

These functions work with any FormatAdapter, not just ARB.
They provide the core business logic that the CLI and other consumers need.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from poliglota.core import FormatAdapter


def discover_resources(adapter: FormatAdapter, root: str | Path) -> dict[str, list]:
    """Discover localized resources for a format under root.

    Returns a dict mapping locale codes to lists of LocalizedResource objects.
    """
    root_path = Path(root)
    resources = adapter.discover(root_path)
    by_locale: dict[str, list] = {}
    for resource in resources:
        locale_code = resource.locale.code
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

    if source_locale not in by_locale:
        return [f"Missing source locale '{source_locale}' in {root_path}"]

    issues: list[str] = []
    source_resources = by_locale[source_locale]

    for locale, locale_resources in by_locale.items():
        if locale == source_locale:
            continue

        for source_resource in source_resources:
            source_doc = adapter.read(source_resource.path)
            source_module = source_resource.attributes.get("module")

            for target_resource in locale_resources:
                target_module = target_resource.attributes.get("module")

                if source_module != target_module:
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

    source_resources = by_locale.get(source_locale, [])
    if not source_resources:
        msg = f"Source locale '{source_locale}' not found in {root_path}"
        raise ValueError(msg)

    changed = 0
    all_resources = [r for resources in by_locale.values() for r in resources]

    for target_resource in all_resources:
        if target_resource.locale.code == source_locale:
            continue

        target_module = target_resource.attributes.get("module")

        for source_resource in source_resources:
            source_module = source_resource.attributes.get("module")

            if source_module != target_module:
                continue

            # Read both documents
            source_doc = adapter.read(source_resource.path)
            target_doc = adapter.read(target_resource.path)

            # Find missing keys in target
            missing = {
                key: value
                for key, value in source_doc.entries.items()
                if key not in target_doc.entries
            }

            if not missing:
                continue

            if not dry_run:
                # Update target entries with missing keys
                updated_entries = dict(target_doc.entries)
                updated_entries.update(missing)

                # Write back with preserved metadata
                from dataclasses import replace

                updated_doc = replace(target_doc, entries=updated_entries)
                adapter.write(updated_doc, target_resource.path)

            changed += 1

    return changed
