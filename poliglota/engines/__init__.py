"""Offline translation engine adapters."""

from .protocol import MariansNMTTranslationEngine, TranslationRequest, TranslationResult

__all__ = [
    "MariansNMTTranslationEngine",
    "TranslationRequest",
    "TranslationResult",
]
