"""Command-line interface for the Poliglota localization commands."""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from poliglota import gpu

from .config import DEFAULT_ROOT, DEFAULT_SOURCE_LOCALE
from .engines.response_cache import ResponseCache
from .formats.operations import discover_resources, sync_with_adapter, validate_with_adapter
from .formats.registry_init import get_registry as get_global_registry
from .quality.placeholders import ArbPlaceholderProtector

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .formats.registry import FormatRegistry


logger = logging.getLogger("poliglota.cli")


def _configure_console_encoding() -> None:
    """Force UTF-8 text IO when the terminal is configured for a legacy code page."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError, OSError):
                continue


_DEFAULT_MOTOR_PRIORITY = (
    "Helsinki-NLP/opus-mt-en-es",
    "Helsinki-NLP/opus-mt-en-fr",
    "Helsinki-NLP/opus-mt-tc-big-en-pt",
)

_DEFAULT_MOTOR_LANGUAGE_SETS = {
    "Helsinki-NLP/opus-mt-en-es": {"en", "es"},
    "Helsinki-NLP/opus-mt-en-fr": {"en", "fr"},
    "Helsinki-NLP/opus-mt-tc-big-en-pt": {"en", "pt"},
}

_DEFAULT_MOTOR_DIRECTIONS = {
    "Helsinki-NLP/opus-mt-en-es": ("en", "es"),
    "Helsinki-NLP/opus-mt-en-fr": ("en", "fr"),
    "Helsinki-NLP/opus-mt-tc-big-en-pt": ("en", "pt"),
}

PHASE_D_BENCHMARKS: dict[str, dict[str, float]] = {
    "M2M-100-418M": {"disk_mb": 840.0, "ram_gb": 1.2},
    "mBART-50": {"disk_mb": 1500.0, "ram_gb": 2.0},
    "NLLB-200": {"disk_mb": 2400.0, "ram_gb": 2.5},
}

_RESOURCE_FOOTPRINT_ALIASES: dict[str, str] = {
    "facebook/m2m100_418M": "M2M-100-418M",
    "facebook/mbart-large-50-many-to-many-mmt": "mBART-50",
    "facebook/mbart-50-many-to-many-mmt": "mBART-50",
    "nllb-200": "NLLB-200",
    "nllb-200-distilled-600m": "NLLB-200",
    "facebook/nllb-200-distilled-600M": "NLLB-200",
}


# Global registry: initialized with available adapters
_registry: FormatRegistry | None = None
_TRANSLATION_CACHE = ResponseCache(max_entries=256, enabled=False)


def _translation_cache_max_entries() -> int:
    """Return the configured max cache size, falling back safely on invalid values."""
    raw = os.environ.get("POLIGLOTA_TRANSLATION_CACHE_MAX_ENTRIES", "256").strip()
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "Invalid POLIGLOTA_TRANSLATION_CACHE_MAX_ENTRIES=%r; using default of 256 entries.",
            raw,
        )
        return 256

    if value <= 0:
        logger.warning(
            "POLIGLOTA_TRANSLATION_CACHE_MAX_ENTRIES must be greater than "
            "zero; using default of 256 entries."
        )
        return 256

    return value


def _translation_cache_enabled() -> bool:
    """Return True when the CLI cache is explicitly enabled by configuration."""
    raw = os.environ.get("POLIGLOTA_ENABLE_TRANSLATION_CACHE", "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _get_translation_cache() -> ResponseCache:
    """Return the CLI-scoped cache, creating it only when explicitly enabled."""
    global _TRANSLATION_CACHE
    enabled = _translation_cache_enabled()
    if enabled:
        max_entries = _translation_cache_max_entries()
        if not _TRANSLATION_CACHE.enabled or _TRANSLATION_CACHE.max_entries != max_entries:
            _TRANSLATION_CACHE = ResponseCache(max_entries=max_entries, enabled=True)
        else:
            _TRANSLATION_CACHE.enabled = True
    elif _TRANSLATION_CACHE.enabled:
        _TRANSLATION_CACHE.enabled = False
        _TRANSLATION_CACHE.clear()
    return _TRANSLATION_CACHE


def _validate_resource_footprint(model_name: str) -> None:
    """Validate conservative disk/RAM resource usage for a translation model.

    This is a non-blocking pre-flight check based on Phase D benchmark data.
    It never raises an exception; it only emits warnings for models above the
    conservative 2GB threshold or logs an informational message for unknown models.

    Examples:
        >>> _validate_resource_footprint("M2M-100-418M")
        >>> _validate_resource_footprint("mBART-50")
        >>> _validate_resource_footprint("unknown-model")

    """
    if model_name is None:
        logger.info("No model name provided; skipping resource footprint validation")
        return

    normalized = model_name.strip()
    canonical_name = _RESOURCE_FOOTPRINT_ALIASES.get(normalized.lower(), normalized)
    footprint = PHASE_D_BENCHMARKS.get(canonical_name)

    if footprint is None:
        logger.info(
            "No Phase D resource footprint benchmark available for model %s; skipping validation",
            model_name,
        )
        return

    disk = int(footprint["disk_mb"])
    ram = float(footprint["ram_gb"])

    if disk >= 2048:
        logger.warning("Model %s requires %sMB disk (2GB+ may impact install)", model_name, disk)

    if ram >= 2.0:
        logger.warning("Model %s requires %sGB RAM (2GB+ may cause OOM)", model_name, ram)


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
    del locale  # Unused by the load functions; preserved for API compatibility.

    if not glossary_path.exists():
        msg = f"Glossary file not found: {glossary_path}"
        raise FileNotFoundError(msg)

    if glossary_path.suffix.lower() == ".json":
        with glossary_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                msg = "Glossary JSON must be a dict mapping source to target terms"
                raise ValueError(msg)
            return data
    elif glossary_path.suffix.lower() == ".csv":
        terms: dict[str, str] = {}
        with glossary_path.open("r", encoding="utf-8") as f:
            for line_num, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(",", 1)
                if len(parts) != 2:
                    msg = f"Glossary CSV line {line_num}: expected 'source,target', got '{line}'"
                    raise ValueError(msg)
                source, target = parts
                terms[source.strip()] = target.strip()
        return terms
    else:
        msg = f"Unsupported glossary format: {glossary_path.suffix}. Use .json or .csv"
        raise ValueError(msg)


def _get_registry() -> FormatRegistry:
    """Get or initialize the global format registry with all adapters."""
    global _registry
    if _registry is None:
        _registry = get_global_registry()
    return _registry


def _prompt_yes_no(prompt: str, default: bool = False) -> bool:
    """Prompt for an explicit yes/no answer with a negative default."""
    default_label = "S/N" if default else "s/N"
    while True:
        try:
            answer = input(f"{prompt} [{default_label}] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return default

        if answer == "":
            return default
        if answer in {"s", "sim", "y", "yes", "true", "1"}:
            return True
        if answer in {"n", "nao", "no", "false", "0"}:
            return False

        print(f"Entrada inválida. Use s/Sim ou n/Não. [{default_label}]")


def _confirm_model_download(model_name: str, *, default: bool = False) -> bool:
    """Request explicit consent before downloading a model for local preparation."""
    print(f"Modelo ausente ou incompleto: {model_name}")
    print("Este comando pode baixar artefatos do Hugging Face e prepará-los localmente.")
    return _prompt_yes_no(f"Baixar e preparar o modelo {model_name}?", default=default)


def _prepare_model_locally(model_name: str, device: str) -> bool:
    """Prepare a model from the canonical Hugging Face cache path with explicit consent."""
    try:
        gpu.detect_device(device, strict=True)
    except ValueError as exc:
        logger.exception("Invalid device specification for model preparation")
        raise RuntimeError(str(exc)) from exc

    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except ImportError as exc:
        msg = "prepare-model requires the optional [gpu] dependency set"
        raise RuntimeError(msg) from exc

    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        del tokenizer, model
    except (OSError, ValueError, RuntimeError) as exc:
        msg = f"Failed to prepare model {model_name}"
        raise RuntimeError(msg) from exc

    if not gpu.check_model_cached(model_name):
        msg = f"Model {model_name} was not validated as a complete local cache after preparation"
        raise RuntimeError(msg)

    logger.info("Model %s prepared and cached successfully.", model_name)
    return True


def _run_prepare_model(args: argparse.Namespace) -> int:
    """Download and cache a Hugging Face translation model for offline use."""
    model_name = str(args.model).strip()
    if not model_name:
        print("Error: --model is required.")
        return 1

    try:
        if gpu.check_model_cached(model_name):
            print(f"Modelo {model_name} já está preparado localmente.")
            return 0
    except (OSError, ValueError, TypeError):
        pass

    try:
        if not _confirm_model_download(model_name, default=False):
            print("Preparação cancelada. Nenhum modelo foi baixado.")
            return 0
        _prepare_model_locally(model_name, args.device)
    except RuntimeError as exc:
        print(f"Error: {exc}")
        return 1

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Poliglota: validate and sync localization files.")
    subparsers = parser.add_subparsers(dest="command", required=False)
    subparsers.add_parser("interactive", help="launch interactive guided flow")
    subparsers.add_parser("guiado", help="lançar fluxo interativo guiado")

    validate_parser = subparsers.add_parser("validate", help="validate locale files")
    validate_parser.add_argument(
        "--root", type=Path, default=DEFAULT_ROOT, help="project root to scan"
    )
    validate_parser.add_argument(
        "--source", default=DEFAULT_SOURCE_LOCALE, help="source locale to use as reference"
    )
    validate_parser.add_argument(
        "--format",
        default="arb",
        choices=["arb", "yaml", "json", "xml"],
        help="localization format: arb, yaml, json, or xml (default: arb)",
    )
    validate_parser.add_argument(
        "--glossary",
        type=Path,
        default=None,
        help="glossary file for terminology validation (JSON or CSV)",
    )
    validate_parser.add_argument(
        "--locale",
        type=str,
        default=None,
        help="target locale to validate glossary against (default: all)",
    )
    validate_parser.add_argument(
        "--check-keys",
        action="store_true",
        default=True,
        help="validate key presence (enabled by default)",
    )
    validate_parser.add_argument(
        "--check-placeholders",
        action="store_true",
        default=True,
        help="validate placeholder consistency (enabled by default)",
    )
    validate_parser.add_argument(
        "--check-glossary",
        action="store_true",
        default=False,
        help="validate glossary term coverage (disabled by default; requires --glossary)",
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
        "--format",
        default="arb",
        choices=["arb", "yaml", "json", "xml"],
        help="localization format: arb, yaml, json, or xml (default: arb)",
    )

    list_parser = subparsers.add_parser("list-locales", help="list locale files discovered")
    list_parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="project root to scan")
    list_parser.add_argument(
        "--format",
        default="arb",
        choices=["arb", "yaml", "json", "xml"],
        help="localization format: arb, yaml, json, or xml (default: arb)",
    )

    translate_parser = subparsers.add_parser(
        "translate",
        help="translate text with a local model (no automatic model download)",
        description=(
            "If --model is omitted, the default motor is auto-selected for the "
            "requested language pair."
        ),
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
        default=os.environ.get("POLIGLOTA_ENGINE", "marian"),
        help="Translation engine (marian or pytorch; default resolves POLIGLOTA_ENGINE)",
    )
    translate_parser.add_argument(
        "--model",
        default=None,
        help="Marian model name from HuggingFace; if omitted, default motor is auto-selected",
    )
    translate_parser.add_argument(
        "--device",
        default="auto",
        help="Device to run inference on (auto, cpu, cuda, mps, gpu)",
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

    prepare_model_parser = subparsers.add_parser(
        "prepare-model",
        help="Prepare (download) a translation model for offline use",
    )
    prepare_model_parser.add_argument(
        "--model",
        required=True,
        help="Hugging Face model name to download and cache",
    )
    prepare_model_parser.add_argument(
        "--device",
        choices=["auto", "cpu", "cuda", "mps", "gpu"],
        default="auto",
        help="Device to validate for model preparation (default: auto)",
    )
    prepare_model_parser.set_defaults(func=_run_prepare_model)

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
            adapter,
            root,
            source_locale,
            check_keys=check_keys,
            check_placeholders=check_placeholders,
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
        target_locales = (
            [glossary_locale]
            if glossary_locale
            else [locale_name for locale_name in by_locale if locale_name != source_locale]
        )

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
                    f"{locale}:{resource.path.name} {issue.message}" for issue in issues_for_locale
                )

    # Combine all issues
    all_issues = issues + glossary_issues

    if all_issues:
        print("Validation issues found:")
        for issue in all_issues:
            print(f"- {issue}")
        return 1
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


def _normalize_locale_code(locale: str) -> str:
    """Normalize locale aliases like ``pt_BR`` and ``pt-BR`` into a canonical form."""
    if not locale:
        return ""
    normalized = locale.strip().replace("-", "_")
    if "_" not in normalized:
        return normalized.lower()
    language, region = normalized.split("_", 1)
    return f"{language.lower()}_{region.upper()}"


def _locale_to_engine_code(locale: str) -> str:
    """Convert a Poliglota locale like ``pt_BR`` into a Marian language code."""
    normalized = _normalize_locale_code(locale)
    if not normalized:
        return ""
    if "_" not in normalized:
        return normalized.lower()
    return normalized.split("_", 1)[0].strip().lower()


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
        msg = "Batch size must be greater than zero."
        raise ValueError(msg)

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
            "Long Marian inference detected; consider reducing input length or "
            "using a faster device",
            extra={"time_ms": round(elapsed_ms, 2), "device": device},
        )
    return restored, placeholder_stats, elapsed_ms


def _verify_offline_capability(model_name: str) -> bool:
    """Check whether a Hugging Face model is already cached for offline use.

    The real Hugging Face Hub layout stores cached models under ``HF_HOME/hub`` using
    the transformed directory name ``models--org--repo`` (for example,
    ``models--facebook--m2m100_418M``), not the raw repo slug with a single slash.
    This helper normalizes both the legacy flat cache name and the real hub layout
    before deciding whether a model is available offline.
    """
    hf_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
    candidate_names = {model_name.replace("/", "--")}
    if model_name.count("/") == 1:
        org, repo = model_name.split("/", 1)
        candidate_names.add(f"models--{org}--{repo}")
    cache_dirs = [hf_home / "hub" / name for name in sorted(candidate_names)]
    cache_exists = any(path.exists() for path in cache_dirs)
    offline_mode = os.environ.get("HF_HUB_OFFLINE") == "1"

    if offline_mode and not cache_exists:
        logger.warning(
            "Offline mode is enabled but the model cache is missing for '%s' under '%s'.",
            model_name,
            hf_home / "hub",
        )
        msg = "Model cache not available for offline mode"
        raise RuntimeError(msg)

    if cache_exists:
        logger.info(
            "Offline capability verified for model '%s' in cache '%s'.",
            model_name,
            next(path for path in cache_dirs if path.exists()),
        )
    else:
        logger.info(
            "Offline capability check for model '%s': cache not found under '%s'.",
            model_name,
            hf_home / "hub",
        )
    return cache_exists


def _resolve_device_name(device: str | None) -> str:
    """Resolve a requested device preference to the final runtime device.

    Uses strict mode for explicit device requests (cpu, cuda, mps, gpu):
    raises ValueError if the requested device is unavailable or invalid.
    Uses permissive mode for 'auto': automatically falls back through
    CUDA > MPS > CPU without raising errors.
    """
    requested = (device or "auto").strip().lower()

    if requested == "auto":
        resolved = gpu.detect_device("auto", strict=False)
        logger.info("Auto-selected runtime device via poliglota.gpu.detect_device(): %s", resolved)
        return resolved

    if requested not in {"cpu", "cuda", "mps", "gpu"}:
        msg = f"Unsupported device '{requested}'. Supported: auto, cpu, cuda, mps, gpu"
        raise ValueError(msg)

    resolved = gpu.detect_device(requested, strict=True)
    logger.info("Resolved device selection: requested=%s -> final=%s", requested, resolved)
    return resolved


def resolve_device_name(device: str | None) -> str:
    """Public wrapper for runtime device resolution."""
    return _resolve_device_name(device)


def _get_engine(
    engine_name: str,
    model_name: str,
    device: str,
    batch_size: int,
) -> Any:
    """Build the selected translation engine while keeping Marian as the default."""
    engine_key = (engine_name or os.environ.get("POLIGLOTA_ENGINE") or "marian").strip().lower()
    resolved_device = _resolve_device_name(device)
    logger.info(
        "Selecting translation engine: engine=%s model=%s requested_device=%s "
        "final_device=%s batch_size=%s",
        engine_key,
        model_name,
        device,
        resolved_device,
        batch_size,
    )

    if engine_key == "pytorch":
        try:
            pytorch_module = importlib.import_module("poliglota.engines.pytorch_engine")
            engine_cls = pytorch_module.PyTorchTranslationEngine
        except ModuleNotFoundError as exc:
            msg = (
                "PyTorch engine is not available in this build. Install the "
                "optional ML dependencies or choose the Marian engine."
            )
            raise RuntimeError(msg) from exc

        adapter = engine_cls(model_name=model_name, device=resolved_device)
        adapter.batch_size = max(1, int(batch_size))
        logger.info(
            "Initializing PyTorch engine with device=%s and batch_size=%s",
            resolved_device,
            adapter.batch_size,
        )
        return adapter

    if engine_key == "marian":
        try:
            marian_module = importlib.import_module("poliglota.engines.marian")
            adapter_cls = marian_module.MariansNMTAdapter
        except ModuleNotFoundError as exc:
            msg = (
                "Marian engine is not available in this build. Install the engine "
                "implementation or use a compatible environment."
            )
            raise RuntimeError(msg) from exc

        adapter = adapter_cls(model_name=model_name, device=resolved_device)
        adapter.batch_size = max(1, int(batch_size))
        try:
            logger.info(
                "Loading Marian model",
                extra={
                    "model": model_name,
                    "device": resolved_device,
                    "batch_size": adapter.batch_size,
                },
            )
            adapter.load_model(device=resolved_device)
        except FileNotFoundError as exc:
            msg = (
                f"Model '{model_name}' is not available locally. Prepare it in the "
                "local Hugging Face cache (HF_HOME) or pass a model that is already "
                "cached."
            )
            raise FileNotFoundError(msg) from exc
        return adapter

    msg = f"Unsupported engine '{engine_name}'. Supported values: marian, pytorch."
    raise ValueError(msg)


def _get_marian_adapter(model_name: str, device: str) -> Any:
    """Create and initialize a Marian adapter for the current environment."""
    try:
        marian_module = importlib.import_module("poliglota.engines.marian")
        adapter_cls = marian_module.MariansNMTAdapter
    except ModuleNotFoundError as exc:
        msg = (
            "Marian engine is not available in this build. Install the engine "
            "implementation or use a compatible environment."
        )
        raise RuntimeError(msg) from exc

    adapter = adapter_cls(model_name=model_name, device=device)
    try:
        logger.info(
            "Loading Marian model",
            extra={"model": model_name, "device": device},
        )
        adapter.load_model()
    except FileNotFoundError as exc:
        msg = (
            f"Model '{model_name}' is not available locally. Prepare it in the local "
            "Hugging Face cache (HF_HOME) or pass a model that is already cached."
        )
        raise FileNotFoundError(msg) from exc
    return adapter


def _select_default_motor(source_lang: str, target_lang: str) -> str:
    """Select the default translation model for a language pair.

    The selection order follows _DEFAULT_MOTOR_PRIORITY. When ``HF_HUB_OFFLINE=1``
    is set, a candidate model is accepted only if it is already present in the local
    Hugging Face cache. The environment variable ``POLIGLOTA_DEFAULT_MOTOR`` can
    override the auto-selection completely.

    Args:
        source_lang: Source locale code such as ``en_US`` or ``pt_BR``.
        target_lang: Target locale code such as ``es`` or ``de``.

    Returns:
        The canonical Hugging Face model identifier for the selected default motor.

    Raises:
        ValueError: When neither engine supports the requested language pair.

    Examples:
        >>> _select_default_motor("en_US", "es")
        'Helsinki-NLP/opus-mt-en-es'
        >>> _select_default_motor("pt_BR", "pt")
        'Helsinki-NLP/opus-mt-tc-big-en-pt'

    """
    override = (os.environ.get("POLIGLOTA_DEFAULT_MOTOR") or "").strip()
    if override:
        logger.info("Selected default motor: %s", override)
        return override

    source_code = _locale_to_engine_code(source_lang).lower()
    target_code = _locale_to_engine_code(target_lang).lower()
    if not source_code or not target_code:
        msg = (
            f"Unsupported default motor pair: '{source_lang}' -> '{target_lang}'. "
            "No available model supports this language combination."
        )
        raise ValueError(msg)

    offline_mode = os.environ.get("HF_HUB_OFFLINE") == "1"

    def _model_in_cache(model_name: str) -> bool:
        cache_root = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
        candidate_names = {model_name.replace("/", "--")}
        if "/" in model_name:
            org, repo = model_name.split("/", 1)
            candidate_names.add(f"models--{org}--{repo}")
        return any((cache_root / "hub" / name).exists() for name in candidate_names)

    def _can_use(model_name: str, direction: tuple[str, str]) -> bool:
        expected_source, expected_target = direction
        if source_code != expected_source or target_code != expected_target:
            return False
        return not (offline_mode and not _model_in_cache(model_name))

    for model in _DEFAULT_MOTOR_PRIORITY:
        direction = _DEFAULT_MOTOR_DIRECTIONS.get(model, ("", ""))
        if direction and _can_use(model, direction):
            logger.info("Selected default motor: %s", model)
            return model

    msg = (
        f"Unsupported default motor pair: '{source_lang}' -> '{target_lang}'. "
        "No available model supports this language combination."
    )
    raise ValueError(msg)


def select_default_motor(source_lang: str, target_lang: str) -> str:
    """Public wrapper for default motor selection."""
    return _select_default_motor(source_lang, target_lang)


def translate_with_placeholders(
    text: str,
    source_locale: str,
    target_locale: str,
    *,
    preserve_placeholders: bool,
    model_name: str,
    device: str,
    batch_size: int,
) -> tuple[str, dict[str, int], float]:
    """Public wrapper for single-string placeholder-aware translation."""
    return _translate_with_placeholders(
        text,
        source_locale,
        target_locale,
        preserve_placeholders=preserve_placeholders,
        model_name=model_name,
        device=device,
        batch_size=batch_size,
    )


def _run_translate(
    text: str,
    source: str,
    target: str,
    *,
    engine: str,
    model: str | None,
    device: str,
    preserve_placeholders: bool,
    batch_size: int,
    json_output: bool,
) -> int:
    """Translate a string through the offline Marian engine.

    Motor Selection:
        If --model is not specified, auto-selects the first model in
        _DEFAULT_MOTOR_PRIORITY whose language set contains both the source and
        target language codes (currently Opus-MT pairs for en/es, en/fr and
        en/pt). Selection respects HF_HUB_OFFLINE=1 (offline mode accepts only
        cached models). Override with POLIGLOTA_DEFAULT_MOTOR environment
        variable.

    Offline Capability Validation:
        Calls _verify_offline_capability() before model load. If HF_HUB_OFFLINE=1
        and cache missing, raises RuntimeError with clear error message.

    Resource Footprint Validation:
        Calls _validate_resource_footprint() for non-blocking warnings if model
        exceeds 2GB disk or 2GB RAM thresholds (emitted to logger, non-fatal).

    Batch Size Auto-scaling:
        MariansNMTAdapter.translate_batch() automatically adjusts batch_size based
        on device memory. On OOM: reduces batch_size and retries; fallback to CPU
        if GPU memory exhausted.

    Args:
        text: Text string to translate.
        source: Source locale code (e.g. pt_BR).
        target: Target locale code (e.g. en_US).
        engine: Translation engine name (marian or pytorch).
        model: Specific HuggingFace model name; if None, auto-selected.
        device: Device to run inference on (auto, cpu, cuda, mps, gpu).
        preserve_placeholders: Whether to preserve ARB placeholders.
        batch_size: Initial batch size for inference (auto-scaled on demand).
        json_output: If True, output JSON instead of plain text.

    Returns:
        Exit code (0 on success, 1 on error).

    """
    normalized_engine = (engine or "marian").strip().lower()
    if normalized_engine not in {"marian", "pytorch"}:
        print(f"Error: Unsupported engine '{engine}'. Use one of: marian, pytorch.")
        return 1

    try:
        resolved_device = _resolve_device_name(device)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1
    logger.info("Final device selected for translation: %s", resolved_device)

    if model is None or not str(model).strip():
        try:
            model = _select_default_motor(source, target)
            if not json_output:
                print(f"Using default motor: {model}")
        except ValueError as exc:
            print(f"Error: {exc}")
            return 1

    cache = _get_translation_cache()
    cache_options = {
        "engine": normalized_engine,
        "device": resolved_device,
        "batch_size": batch_size,
        "preserve_placeholders": preserve_placeholders,
    }

    cached = None
    if cache.enabled:
        cached = cache.get(
            text,
            source,
            target,
            model_name=model,
            options=cache_options,
        )
        if cached is not None:
            translated, placeholder_stats, elapsed_ms = cached
            logger.info(
                "Using cached translation for model=%s source=%s target=%s",
                model,
                source,
                target,
            )
            payload = {
                "text": text,
                "source": source,
                "target": target,
                "translated": translated,
                "time_ms": round(elapsed_ms),
                "preserved_placeholders": placeholder_stats["preserved"],
            }
            if json_output:
                print(json.dumps(payload, ensure_ascii=False))
                return 0
            print(translated)
            return 0

    try:
        if normalized_engine == "marian":
            _verify_offline_capability(model)
            _validate_resource_footprint(model)
        adapter = _get_engine(
            normalized_engine,
            model,
            resolved_device,
            batch_size,
        )
        logger.info(
            "Translation adapter selected: engine=%s model=%s device=%s batch_size=%s",
            normalized_engine,
            model,
            getattr(adapter, "device", resolved_device),
            getattr(adapter, "batch_size", batch_size),
        )
        if normalized_engine == "marian":
            translated, placeholder_stats, elapsed_ms = _translate_with_placeholders(
                text,
                source,
                target,
                preserve_placeholders=preserve_placeholders,
                model_name=model,
                device=resolved_device,
                batch_size=batch_size,
            )
        else:
            translated = adapter.translate(
                text,
                _locale_to_engine_code(source),
                _locale_to_engine_code(target),
            )
            placeholder_stats = {"preserved": 0, "substituted": 0, "missing": 0}
            elapsed_ms = 0.0
            logger.info(
                "PyTorch inference completed on device=%s for model=%s",
                getattr(adapter, "device", resolved_device),
                model,
            )

        if cache.enabled:
            cache.set(
                text,
                source,
                target,
                model_name=model,
                options=cache_options,
                value=(translated, placeholder_stats, elapsed_ms),
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
        "time_ms": round(elapsed_ms),
        "preserved_placeholders": placeholder_stats["preserved"],
    }

    if json_output:
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    print(translated)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected command and return the process exit code."""
    _configure_console_encoding()

    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        from . import cli_interactive

        return cli_interactive.run_interactive()

    parser = _build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "func", None) is not None:
        return args.func(args)

    if getattr(args, "command", None) == "validate":
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
    if getattr(args, "command", None) == "sync":
        return _run_sync(args.root, args.source, args.dry_run, args.format)
    if getattr(args, "command", None) == "list-locales":
        return _run_list_locales(args.root, args.format)
    if getattr(args, "command", None) == "translate":
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
    if (
        getattr(args, "command", None) == "interactive"
        or getattr(args, "command", None) == "guiado"
    ):
        from . import cli_interactive

        return cli_interactive.run_interactive()

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
