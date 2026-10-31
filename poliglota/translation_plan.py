"""Shared project discovery, model resolution, and translation planning rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import gpu
from .language_detection import DetectionCandidate, detect_source_locale, normalize_locale_code
from .model_catalog import resolve_default_model_for_pair, supported_models_for_pair


@dataclass(slots=True)
class TranslationPlanStep:
    """One destination in the execution plan."""

    source: str
    target: str
    model: str
    device: str
    available_local: bool
    compatible: bool
    status: str
    reason: str = ""


@dataclass(slots=True)
class TranslationPlan:
    """Shared translation plan built from a source and target set."""

    source: str
    targets: list[str]
    detected_candidates: list[DetectionCandidate] = field(default_factory=list)
    steps: list[TranslationPlanStep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_unsupported_targets(self) -> bool:
        return any(not step.compatible for step in self.steps)


def detect_project_languages(
    root: str | Path,
    format_name: str,
    *,
    adapter: Any | None = None,
) -> tuple[list[str], list[DetectionCandidate], bool]:
    """Return normalized locale candidates for a resource tree."""
    result = detect_source_locale(root, format_name, adapter=adapter)
    candidates = [
        normalize_locale_code(candidate.locale_code) or candidate.locale_code
        for candidate in result.candidates
    ]
    unique = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            unique.append(candidate)
            seen.add(candidate)
    return unique, result.candidates, result.inconclusive


def model_available_locally(model: str | None) -> bool:
    """Return whether the model is already available in the local offline cache."""
    if not model or not str(model).strip():
        return False
    try:
        return bool(gpu.check_model_cached(str(model).strip()))
    except (OSError, TypeError, ValueError):
        return False


def resolve_model_for_pair(
    source_lang: str,
    target_lang: str,
    *,
    device: str = "auto",
    explicit_model: str | None = None,
) -> TranslationPlanStep:
    """Resolve a model for one source/target pair and carry compatibility metadata."""
    source = normalize_locale_code(source_lang) or source_lang
    target = normalize_locale_code(target_lang) or target_lang
    normalized_device = (device or "auto").strip() or "auto"
    if explicit_model and explicit_model.strip():
        model_name = explicit_model.strip()
        candidates = supported_models_for_pair(source, target)
        compatible = bool(candidates) and (model_name in candidates or model_name in {"facebook/nllb-200-distilled-600M"})
        if compatible:
            available = model_available_locally(model_name)
            return TranslationPlanStep(
                source=source,
                target=target,
                model=model_name,
                device=normalized_device,
                available_local=available,
                compatible=True,
                status="ready" if available else "missing-local-model",
                reason="modelo escolhido manualmente" if available else "modelo disponível no catálogo, mas ausente localmente",
            )
        return TranslationPlanStep(
            source=source,
            target=target,
            model=model_name,
            device=normalized_device,
            available_local=False,
            compatible=False,
            status="incompatible-model",
            reason="modelo escolhido manualmente não é compatível com o par origem → destino",
        )

    try:
        model_name = resolve_default_model_for_pair(source, target)
    except ValueError as exc:
        return TranslationPlanStep(
            source=source,
            target=target,
            model="",
            device=normalized_device,
            available_local=False,
            compatible=False,
            status="unsupported-pair",
            reason=str(exc),
        )

    available = model_available_locally(model_name)
    return TranslationPlanStep(
        source=source,
        target=target,
        model=model_name,
        device=normalized_device,
        available_local=available,
        compatible=True,
        status="ready" if available else "missing-local-model",
        reason="modelo compatível e disponível localmente" if available else "modelo compatível, mas não instalado localmente",
    )


def build_translation_plan(
    source_lang: str,
    target_langs: list[str],
    *,
    device: str = "auto",
    explicit_model: str | None = None,
    detected_candidates: list[DetectionCandidate] | None = None,
) -> TranslationPlan:
    """Build a shared, per-destination translation plan."""
    source = normalize_locale_code(source_lang) or source_lang
    targets = []
    seen: set[str] = set()
    for target in target_langs:
        normalized = normalize_locale_code(target) or target
        if normalized and normalized not in seen and normalized != source:
            targets.append(normalized)
            seen.add(normalized)

    steps = [
        resolve_model_for_pair(source, target, device=device, explicit_model=explicit_model)
        for target in targets
    ]
    warnings = []
    for step in steps:
        if not step.compatible:
            warnings.append(f"{step.source} -> {step.target}: {step.reason}")
        elif step.status == "missing-local-model":
            warnings.append(
                f"{step.source} -> {step.target}: {step.model} está no catálogo, mas não está instalado localmente."
            )
    return TranslationPlan(
        source=source,
        targets=targets,
        detected_candidates=list(detected_candidates or []),
        steps=steps,
        warnings=warnings,
    )
