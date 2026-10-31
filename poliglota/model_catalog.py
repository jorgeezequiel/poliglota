"""Shared model catalog and compatibility checks for Poliglota."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

_MODEL_CATALOG: Final[dict[str, set[tuple[str, str]]]] = {
    "Helsinki-NLP/opus-mt-en-es": {("en", "es"), ("es", "en")},
    "Helsinki-NLP/opus-mt-en-fr": {("en", "fr"), ("fr", "en")},
    "Helsinki-NLP/opus-mt-tc-big-en-pt": {("en", "pt"), ("pt", "en")},
    "facebook/nllb-200-distilled-600M": {
        ("en", "es"),
        ("es", "en"),
        ("en", "fr"),
        ("fr", "en"),
        ("en", "pt"),
        ("pt", "en"),
        ("pt", "es"),
        ("es", "pt"),
        ("pt", "fr"),
        ("fr", "pt"),
        ("pt", "de"),
        ("de", "pt"),
        ("pt", "ja"),
        ("ja", "pt"),
        ("pt", "ko"),
        ("ko", "pt"),
        ("pt", "it"),
        ("it", "pt"),
        ("pt", "ru"),
        ("ru", "pt"),
    },
    "facebook/m2m100_418M": {
        ("en", "es"),
        ("es", "en"),
        ("en", "fr"),
        ("fr", "en"),
        ("en", "pt"),
        ("pt", "en"),
        ("pt", "es"),
        ("es", "pt"),
        ("pt", "fr"),
        ("fr", "pt"),
        ("pt", "de"),
        ("de", "pt"),
        ("pt", "ja"),
        ("ja", "pt"),
        ("pt", "ko"),
        ("ko", "pt"),
        ("pt", "it"),
        ("it", "pt"),
        ("pt", "ru"),
        ("ru", "pt"),
    },
}

_MODEL_PRIORITY: Final[tuple[str, ...]] = (
    "Helsinki-NLP/opus-mt-en-es",
    "Helsinki-NLP/opus-mt-en-fr",
    "Helsinki-NLP/opus-mt-tc-big-en-pt",
    "facebook/nllb-200-distilled-600M",
    "facebook/m2m100_418M",
)


@dataclass(frozen=True, slots=True)
class ModelCompatibility:
    """Compatibility result for one model/language-pair check."""

    model: str
    source: str
    target: str
    compatible: bool
    reason: str = ""


def _normalize_lang_code(value: str | None) -> str:
    text = (value or "").strip().lower()
    if "_" in text:
        text = text.split("_", 1)[0]
    if "-" in text:
        text = text.split("-", 1)[0]
    return text


def resolve_default_model_for_pair(source_lang: str, target_lang: str) -> str:
    """Return the preferred default model for a language pair using catalog priority."""
    source = _normalize_lang_code(source_lang)
    target = _normalize_lang_code(target_lang)
    if not source or not target:
        msg = f"Unsupported default motor pair: '{source_lang}' -> '{target_lang}'."
        raise ValueError(msg)

    for model in _MODEL_PRIORITY:
        if (source, target) in _MODEL_CATALOG.get(model, set()):
            return model

    msg = (
        f"Unsupported default motor pair: '{source_lang}' -> '{target_lang}'. "
        "No available model supports this language combination."
    )
    raise ValueError(msg)


def supported_models_for_pair(source_lang: str, target_lang: str) -> list[str]:
    """Return all catalog models compatible with the given pair."""
    source = _normalize_lang_code(source_lang)
    target = _normalize_lang_code(target_lang)
    models: list[str] = []
    for model, supported_pairs in _MODEL_CATALOG.items():
        if (source, target) in supported_pairs:
            models.append(model)
    return models


def validate_model_compatibility(model: str, source_lang: str, target_lang: str) -> ModelCompatibility:
    """Check whether a model is compatible with a given language pair."""
    source = _normalize_lang_code(source_lang)
    target = _normalize_lang_code(target_lang)
    supported = _MODEL_CATALOG.get(model)
    if supported is None:
        return ModelCompatibility(
            model=model,
            source=source,
            target=target,
            compatible=False,
            reason="modelo não presente no catálogo oficial do Poliglota",
        )

    compatible = (source, target) in supported or (target, source) in supported
    if not compatible:
        return ModelCompatibility(
            model=model,
            source=source,
            target=target,
            compatible=False,
            reason="modelo incompatível com o par origem → destino",
        )

    return ModelCompatibility(
        model=model,
        source=source,
        target=target,
        compatible=True,
        reason="compatível com o par de idiomas",
    )


def resolve_default_models_for_targets(source_lang: str, target_langs: list[str]) -> dict[str, str]:
    """Resolve one model per target locale, raising when a target is unsupported."""
    resolved: dict[str, str] = {}
    for target_lang in target_langs:
        resolved[target_lang] = resolve_default_model_for_pair(source_lang, target_lang)
    return resolved
