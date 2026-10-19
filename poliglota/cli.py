"""Command-line interface for the Poliglota ARB commands."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from .config import DEFAULT_ROOT, DEFAULT_SOURCE_LOCALE
from .formats.arb import discover_arb_files, sync_locale_files, validate_root

if TYPE_CHECKING:
    from collections.abc import Sequence


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Poliglota: validate and sync ARB locale files.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate locale files")
    validate_parser.add_argument(
        "--root", type=Path, default=DEFAULT_ROOT, help="project root to scan"
    )
    validate_parser.add_argument(
        "--source", default=DEFAULT_SOURCE_LOCALE, help="source locale to use as reference"
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

    list_parser = subparsers.add_parser("list-locales", help="list locale files discovered")
    list_parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="project root to scan")

    return parser


def _run_validate(root: Path, source_locale: str) -> int:
    issues = validate_root(root, source_locale)
    if issues:
        print("Validation issues found:")
        for issue in issues:
            print(f"- {issue}")
    else:
        print(f"No validation issues found for source locale '{source_locale}'.")
    return 0


def _run_sync(root: Path, source_locale: str, dry_run: bool) -> int:
    files = discover_arb_files(root)
    if not files:
        print(f"No ARB files found under {root}.")
        return 0

    try:
        changed = sync_locale_files(root, source_locale, dry_run=dry_run)
    except ValueError as exc:
        print(str(exc))
        return 1
    if dry_run:
        print(f"Dry run: {changed} locale file(s) would be updated.")
    else:
        print(f"Updated {changed} locale file(s) from '{source_locale}'.")
    return 0


def _run_list_locales(root: Path) -> int:
    files = discover_arb_files(root)
    locales = sorted({arb_file.locale for arb_file in files})
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
        return _run_validate(args.root, args.source)
    if args.command == "sync":
        return _run_sync(args.root, args.source, args.dry_run)
    if args.command == "list-locales":
        return _run_list_locales(args.root)

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
