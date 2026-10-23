"""Command-line interface for the Poliglota localization commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING

from .config import DEFAULT_ROOT, DEFAULT_SOURCE_LOCALE
from .formats.arb import ARBFormatAdapter
from .formats.registry import FormatRegistry
from .formats.operations import discover_resources, validate_with_adapter, sync_with_adapter

if TYPE_CHECKING:
    from collections.abc import Sequence


# Global registry: initialized with available adapters
_registry: FormatRegistry | None = None


def _load_glossary(glossary_path: Path, locale: str) -> dict[str, str]:
    """Load glossary from JSON or CSV file.
    
    Args:
        glossary_path: Path to glossary file.
        locale: Target locale code (used in error messages).
    
    Returns:
        Dictionary mapping source terms to target terms.
    
    Raises:
        FileNotFoundError: If glossary file doesn't exist.
        ValueError: If glossary format is invalid.
    """
    if not glossary_path.exists():
        raise FileNotFoundError(f"Glossary file not found: {glossary_path}")
    
    if glossary_path.suffix.lower() == ".json":
        with open(glossary_path, encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Glossary JSON must be a dict mapping source to target terms")
            return data
    elif glossary_path.suffix.lower() == ".csv":
        terms = {}
        with open(glossary_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(",", 1)
                if len(parts) != 2:
                    raise ValueError(f"Glossary CSV line {line_num}: expected 'source,target', got '{line}'")
                source, target = parts
                terms[source.strip()] = target.strip()
        return terms
    else:
        raise ValueError(f"Unsupported glossary format: {glossary_path.suffix}. Use .json or .csv")



def _get_registry() -> FormatRegistry:
    """Get or initialize the global format registry."""
    global _registry
    if _registry is None:
        _registry = FormatRegistry()
        _registry.register(ARBFormatAdapter())
    return _registry



def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Poliglota: validate and sync localization files.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate locale files")
    validate_parser.add_argument(
        "--root", type=Path, default=DEFAULT_ROOT, help="project root to scan"
    )
    validate_parser.add_argument(
        "--source", default=DEFAULT_SOURCE_LOCALE, help="source locale to use as reference"
    )
    validate_parser.add_argument(
        "--format", default="arb", help="localization format (default: arb)"
    )
    validate_parser.add_argument(
        "--glossary", type=Path, default=None, help="glossary file for terminology validation (JSON or CSV)"
    )
    validate_parser.add_argument(
        "--locale", type=str, default=None, help="target locale to validate glossary against (default: all)"
    )
    validate_parser.add_argument(
        "--check-keys", action="store_true", default=True,
        help="validate key presence (enabled by default)"
    )
    validate_parser.add_argument(
        "--check-placeholders", action="store_true", default=True,
        help="validate placeholder consistency (enabled by default)"
    )
    validate_parser.add_argument(
        "--check-glossary", action="store_true", default=False,
        help="validate glossary term coverage (disabled by default; requires --glossary)"
    )

    sync_parser = subparsers.add_parser(
        "sync", help="copy missing keys from the source locale into targets"
    )
    sync_parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="project root to scan")
    sync_parser.add_argument(
        "--source", default=DEFAULT_SOURCE_LOCALE, help="source locale to use as reference"
    )
    sync_parser.add_argument(
        "--dry-run", action="store_true", help="show what would change without writing files"
    )
    sync_parser.add_argument(
        "--format", default="arb", help="localization format (default: arb)"
    )

    list_parser = subparsers.add_parser("list-locales", help="list locale files discovered")
    list_parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="project root to scan")
    list_parser.add_argument(
        "--format", default="arb", help="localization format (default: arb)"
    )

    return parser


def _run_validate(
    root: Path,
    source_locale: str,
    format_name: str,
    glossary_path: Path | None = None,
    glossary_locale: str | None = None,
    check_keys: bool = True,
    check_placeholders: bool = True,
    check_glossary: bool = False,
) -> int:
    registry = _get_registry()
    try:
        adapter = registry.get(format_name)
    except KeyError as exc:
        print(f"Error: {exc}")
        return 2

    try:
        issues = validate_with_adapter(
            adapter, root, source_locale,
            check_keys=check_keys,
            check_placeholders=check_placeholders
        )
    except ValueError as exc:
        print(str(exc))
        return 1

    # Load and validate glossary if requested
    glossary_issues = []
    if glossary_path and check_glossary:
        try:
            glossary_terms = _load_glossary(glossary_path, glossary_locale or source_locale)
        except (FileNotFoundError, ValueError) as exc:
            print(f"Error loading glossary: {exc}")
            return 1

        # Get all discovered locales
        by_locale = discover_resources(adapter, root)
        target_locales = [glossary_locale] if glossary_locale else [l for l in by_locale.keys() if l != source_locale]

        from .quality.validation import GlossaryValidator
        glossary_validator = GlossaryValidator()

        for locale in target_locales:
            if locale == source_locale or locale not in by_locale:
                continue

            # Read target entries for this locale
            for resource in by_locale[locale]:
                target_doc = adapter.read(resource.path)
                issues_for_locale = glossary_validator.validate_glossary_coverage(
                    target_doc.entries,
                    glossary_terms,
                    locale,
                )
                # Convert ValidationIssue objects to strings for consistent output
                glossary_issues.extend(
                    f"{locale}:{resource.path.name} {issue.message}"
                    for issue in issues_for_locale
                )

    # Combine all issues
    all_issues = issues + glossary_issues

    if all_issues:
        print("Validation issues found:")
        for issue in all_issues:
            print(f"- {issue}")
        return 1
    else:
        print(f"No validation issues found for source locale '{source_locale}'.")
    return 0


def _run_sync(root: Path, source_locale: str, dry_run: bool, format_name: str) -> int:
    registry = _get_registry()
    try:
        adapter = registry.get(format_name)
    except KeyError as exc:
        print(f"Error: {exc}")
        return 2

    by_locale = discover_resources(adapter, root)
    if not by_locale:
        print(f"No {format_name.upper()} files found under {root}.")
        return 0

    try:
        changed = sync_with_adapter(adapter, root, source_locale, dry_run=dry_run)
    except ValueError as exc:
        print(str(exc))
        return 1
    if dry_run:
        print(f"Dry run: {changed} locale file(s) would be updated.")
    else:
        print(f"Updated {changed} locale file(s) from '{source_locale}'.")
    return 0


def _run_list_locales(root: Path, format_name: str) -> int:
    registry = _get_registry()
    try:
        adapter = registry.get(format_name)
    except KeyError as exc:
        print(f"Error: {exc}")
        return 2

    by_locale = discover_resources(adapter, root)
    locales = sorted(by_locale.keys())
    if not locales:
        print(f"No locale files found under {root}.")
        return 0

    print("Discovered locales:")
    for locale in locales:
        print(f"- {locale}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected command and return the process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        return _run_validate(
            args.root,
            args.source,
            args.format,
            glossary_path=args.glossary,
            glossary_locale=args.locale,
            check_keys=args.check_keys,
            check_placeholders=args.check_placeholders,
            check_glossary=args.check_glossary,
        )
    if args.command == "sync":
        return _run_sync(args.root, args.source, args.dry_run, args.format)
    if args.command == "list-locales":
        return _run_list_locales(args.root, args.format)

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
