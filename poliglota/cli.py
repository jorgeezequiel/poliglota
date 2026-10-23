"""Command-line interface for the Poliglota localization commands."""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from .config import DEFAULT_ROOT, DEFAULT_SOURCE_LOCALE
from .formats.arb import ARBFormatAdapter
from .formats.registry import FormatRegistry
from .formats.operations import discover_resources, validate_with_adapter, sync_with_adapter
from .quality.placeholders import ArbPlaceholderProtector

if TYPE_CHECKING:
    from collections.abc import Sequence


logger = logging.getLogger("poliglota.cli")


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

    translate_parser = subparsers.add_parser(
        "translate",
        help="translate text with the offline Marian model (Phase 6a)",
    )
    translate_parser.add_argument("text", help="Text to translate")
    translate_parser.add_argument(
        "--source",
        default="pt_BR",
        help="Source locale (e.g. pt_BR)",
    )
    translate_parser.add_argument(
        "--target",
        default="en_US",
        help="Target locale (e.g. en_US)",
    )
    translate_parser.add_argument(
        "--engine",
        default="marian",
        help="Translation engine (marian only for Phase 6a)",
    )
    translate_parser.add_argument(
        "--model",
        default="opus-mt-tc-big-en-pt",
        help="Marian model name from HuggingFace",
    )
    translate_parser.add_argument(
        "--device",
        default="cpu",
        help="Device to run inference on (cpu, cuda, mps)",
    )
    translate_parser.add_argument(
        "--preserve-placeholders",
        action="store_true",
        default=True,
        help="Preserve ARB placeholders before and after translation",
    )
    translate_parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Batch size for inference",
    )
    translate_parser.add_argument(
        "--json-output",
        action="store_true",
        default=False,
        help="Output JSON instead of plain text",
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


def _locale_to_engine_code(locale: str) -> str:
    """Convert a Poliglota locale like ``pt_BR`` into a Marian language code."""
    if not locale or "_" not in locale:
        return locale.strip()
    return locale.split("_", 1)[0].strip().lower()


def _translate_with_placeholders(
    text: str,
    source_locale: str,
    target_locale: str,
    *,
    preserve_placeholders: bool,
    model_name: str,
    device: str,
    batch_size: int,
) -> tuple[str, dict[str, int], float]:
    """Translate a single string using the local Marian adapter with placeholder protection."""
    if batch_size <= 0:
        raise ValueError("Batch size must be greater than zero.")

    if not preserve_placeholders:
        started = time.perf_counter()
        adapter = _get_marian_adapter(model_name=model_name, device=device)
        translated = adapter.translate(
            text,
            _locale_to_engine_code(source_locale),
            _locale_to_engine_code(target_locale),
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "marian inference completed with no placeholder preservation",
            extra={
                "source_locale": source_locale,
                "target_locale": target_locale,
                "device": device,
                "time_ms": round(elapsed_ms, 2),
                "model": model_name,
            },
        )
        return translated, {"preserved": 0, "substituted": 0, "missing": 0}, elapsed_ms

    protector = ArbPlaceholderProtector()
    masked_text, placeholders_map = protector.mask(text)
    original_count = len(placeholders_map)
    started = time.perf_counter()
    adapter = _get_marian_adapter(model_name=model_name, device=device)
    translated_masked = adapter.translate(
        masked_text,
        _locale_to_engine_code(source_locale),
        _locale_to_engine_code(target_locale),
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    restored = protector.restore(translated_masked, placeholders_map)
    restore_issues = protector.validate_restore(masked_text, restored, text)
    if restore_issues:
        logger.warning(
            "Placeholder restoration warnings: %s",
            "; ".join(restore_issues),
            extra={"issues": restore_issues, "preserved": original_count},
        )
    logger.info(
        "marian inference completed with placeholder restoration",
        extra={
            "source_locale": source_locale,
            "target_locale": target_locale,
            "device": device,
            "time_ms": round(elapsed_ms, 2),
            "model": model_name,
            "placeholders": original_count,
            "preserved": original_count,
        },
    )
    placeholder_stats = {
        "preserved": original_count,
        "substituted": max(0, original_count - len(restore_issues)),
        "missing": len(restore_issues),
    }
    if elapsed_ms > 5000:
        logger.warning(
            "Long Marian inference detected; consider reducing input length or using a faster device",
            extra={"time_ms": round(elapsed_ms, 2), "device": device},
        )
    return restored, placeholder_stats, elapsed_ms


def _get_marian_adapter(model_name: str, device: str):
    """Create and initialize a Marian adapter for the current environment."""
    try:
        marian_module = importlib.import_module("poliglota.engines.marian")
        adapter_cls = marian_module.MariansNMTAdapter
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Marian engine is not available in this build. Install the engine implementation or use a compatible environment."
        ) from exc

    adapter = adapter_cls(model_name=model_name, device=device)
    try:
        logger.info(
            "Loading Marian model",
            extra={"model": model_name, "device": device},
        )
        adapter.load_model()
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Model '{model_name}' is not cached locally. Run `poliglota download-model --engine marian --model {model_name}` first."
        ) from exc
    return adapter


def _run_translate(
    text: str,
    source: str,
    target: str,
    *,
    engine: str,
    model: str,
    device: str,
    preserve_placeholders: bool,
    batch_size: int,
    json_output: bool,
) -> int:
    """Translate a string through the offline Marian engine."""
    if engine != "marian":
        print(f"Error: Unsupported engine '{engine}'. Only 'marian' is available in Phase 6a.")
        return 1

    if device not in {"cpu", "cuda", "mps"}:
        print(f"Error: Unsupported device '{device}'. Use one of: cpu, cuda, mps.")
        return 1

    try:
        translated, placeholder_stats, elapsed_ms = _translate_with_placeholders(
            text,
            source,
            target,
            preserve_placeholders=preserve_placeholders,
            model_name=model,
            device=device,
            batch_size=batch_size,
        )
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1
    except RuntimeError as exc:
        print(f"Error: {exc}")
        print("Hint: try --device cpu to force the CPU path and reduce memory pressure.")
        return 1
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 1

    payload = {
        "text": text,
        "source": source,
        "target": target,
        "translated": translated,
        "time_ms": int(round(elapsed_ms)),
        "preserved_placeholders": placeholder_stats["preserved"],
    }

    if json_output:
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    print(translated)
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
    if args.command == "translate":
        return _run_translate(
            args.text,
            args.source,
            args.target,
            engine=args.engine,
            model=args.model,
            device=args.device,
            preserve_placeholders=args.preserve_placeholders,
            batch_size=args.batch_size,
            json_output=args.json_output,
        )

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
