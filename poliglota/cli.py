"""Command-line interface for the Poliglota localization commands."""

from __future__ import annotations

import argparse
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


def _run_validate(root: Path, source_locale: str, format_name: str) -> int:
    registry = _get_registry()
    try:
        adapter = registry.get(format_name)
    except KeyError as exc:
        print(f"Error: {exc}")
        return 2

    try:
        issues = validate_with_adapter(adapter, root, source_locale)
    except ValueError as exc:
        print(str(exc))
        return 1
    if issues:
        print("Validation issues found:")
        for issue in issues:
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
        return _run_validate(args.root, args.source, args.format)
    if args.command == "sync":
        return _run_sync(args.root, args.source, args.dry_run, args.format)
    if args.command == "list-locales":
        return _run_list_locales(args.root, args.format)

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
