"""Orchestration helpers for translating localization resource files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from poliglota import cli
from poliglota.formats.operations import discover_resources
from poliglota.formats.registry_init import get_registry

if TYPE_CHECKING:
    from poliglota.engines.response_cache import ResponseCache


@dataclass(slots=True)
class TranslationReport:
    """Summary of a translation run across one or more locale files."""

    processed: int = 0
    translated: int = 0
    skipped: int = 0
    failed: int = 0
    details: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        """Initialize the optional list of per-file failures."""
        if self.details is None:
            self.details = []


def _get_adapter(format_name: str) -> Any:
    """Resolve and return the format adapter for a resource type."""
    registry = get_registry()
    try:
        return registry.get(format_name)
    except KeyError as exc:
        msg = str(exc)
        raise ValueError(msg) from exc


def translate_resource_files(
    root: Path,
    source_locale: str,
    target_locales: list[str],
    format_name: str = "arb",
    output_dir: Path | None = None,
    engine: str | None = None,
    model: str | None = None,
    device: str = "auto",
    batch_size: int = 8,
    preserve_placeholders: bool = True,
    cache: ResponseCache | None = None,
) -> TranslationReport:
    """Translate source locale files into target locale files."""
    adapter = _get_adapter(format_name)
    by_locale = discover_resources(adapter, root)
    if source_locale not in by_locale:
        msg = f"Missing source locale '{source_locale}' in {root}"
        raise ValueError(msg)

    out_dir = output_dir or (Path(root) / ".poliglota_translated")
    out_dir.mkdir(parents=True, exist_ok=True)

    report = TranslationReport()
    source_resources = by_locale[source_locale]

    for target_locale in target_locales:
        if target_locale == source_locale:
            continue
        for src_res in source_resources:
            try:
                src_doc = adapter.read(src_res.path)
            except (OSError, TypeError, ValueError) as exc:
                report.failed += 1
                if report.details is not None:
                    report.details.append({"file": str(src_res.path), "error": str(exc)})
                continue

            try:
                rel = src_res.path.relative_to(root)
            except ValueError:
                rel = Path(src_res.path.name)
            out_path = out_dir / rel
            name = out_path.name
            out_path = out_path.with_name(name.replace(source_locale, target_locale))
            out_path.parent.mkdir(parents=True, exist_ok=True)

            translated_entries = {}
            actual_model = model
            if actual_model is None or not str(actual_model).strip():
                try:
                    actual_model = cli.select_default_motor(source_locale, target_locale)
                except ValueError as exc:
                    msg = str(exc)
                    raise ValueError(msg) from exc

            for key, value in src_doc.entries.items():
                if str(key).startswith("@"):
                    translated_entries[key] = value
                    continue
                if not isinstance(value, str):
                    translated_entries[key] = value
                    continue
                text = value
                try:
                    if cache and getattr(cache, "enabled", False):
                        cached = cache.get(
                            text,
                            source_locale,
                            target_locale,
                            model_name=actual_model,
                            options={"engine": engine, "device": device},
                        )
                        if cached is not None:
                            translated_text = cached[0]
                        else:
                            translated_text, _, _ = cli.translate_with_placeholders(
                                text,
                                source_locale,
                                target_locale,
                                preserve_placeholders=preserve_placeholders,
                                model_name=actual_model,
                                device=device,
                                batch_size=batch_size,
                            )
                            cache.set(
                                text,
                                source_locale,
                                target_locale,
                                model_name=actual_model,
                                options={"engine": engine, "device": device},
                                value=(
                                    translated_text,
                                    {"preserved": 0, "substituted": 0, "missing": 0},
                                    0.0,
                                ),
                            )
                    else:
                        translated_text, _, _ = cli.translate_with_placeholders(
                            text,
                            source_locale,
                            target_locale,
                            preserve_placeholders=preserve_placeholders,
                            model_name=actual_model,
                            device=device,
                            batch_size=batch_size,
                        )
                    translated_entries[key] = translated_text
                    report.translated += 1
                except (OSError, TypeError, ValueError) as exc:
                    report.failed += 1
                    if report.details is not None:
                        report.details.append(
                            {
                                "key": key,
                                "file": str(src_res.path),
                                "error": str(exc),
                            }
                        )
                    translated_entries[key] = value
                    continue

            try:
                from dataclasses import replace

                new_doc = replace(src_doc, entries=translated_entries)
                adapter.write(new_doc, out_path)
                report.processed += 1
            except (OSError, TypeError, ValueError) as exc:
                report.failed += 1
                if report.details is not None:
                    report.details.append({"file": str(out_path), "error": str(exc)})

    return report
