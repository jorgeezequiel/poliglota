"""Offline Marian-NMT engine protocol and request/result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Self


@dataclass(frozen=True, slots=True)
class TranslationRequest:
    """Translation request payload for an offline Marian adapter.

    Args:
        text: Text to translate.
        source_lang: Source language code.
        target_lang: Target language code.
        preserve_placeholders: Whether Phase 4 placeholder tags should be preserved.

    Example:
        >>> request = TranslationRequest("<en>Hello <name></en>", "en", "pt")
        >>> request.target_lang
        'pt'

    """

    text: str
    source_lang: str
    target_lang: str
    preserve_placeholders: bool = True


@dataclass(frozen=True, slots=True)
class TranslationResult:
    """Result returned by an offline Marian translation run.

    Args:
        translated_text: Final translated output.
        source_lang: Source language identifier.
        target_lang: Target language identifier.
        confidence: Decoder confidence score.
        metadata: Extra model diagnostics.

    """

    translated_text: str
    source_lang: str
    target_lang: str
    confidence: float
    metadata: dict[str, str | int | float | bool | None] = field(default_factory=dict)


class MariansNMTTranslationEngine(Protocol):
    """Abstract contract for offline Marian translation engines.

    The implementation must load a local model, expose the supported source/target
    language pairs, translate text in single or batch mode, and free memory when
    the engine is closed.
    """

    @property
    def name(self) -> str:
        """Stable engine identifier."""
        ...

    def engine_language(self, locale: object) -> str:
        """Return the engine language code for ``locale``."""
        ...

    def supports(self, source: object, target: object) -> bool:
        """Return whether a language pair is supported."""
        ...

    def load_model(self, model_path: str | None = None, device: str = "cpu") -> None:
        """Load the Marian model from a local path or a known model identifier."""
        ...

    def get_supported_pairs(self) -> list[tuple[str, str]]:
        """Return the loaded source/target language pairs."""
        ...

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate a single string while preserving placeholders."""
        ...

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        """Translate a list of strings in a single batch."""
        ...

    def get_model_info(self) -> dict[str, str | int | float]:
        """Return metadata for the current model."""
        ...

    def close(self) -> None:
        """Free the loaded model and any attached device memory."""
        ...

    def __enter__(self) -> Self:
        """Support context-manager usage."""
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Release resources when leaving a context-managed block."""
        self.close()


__all__ = [
    "MariansNMTTranslationEngine",
    "TranslationRequest",
    "TranslationResult",
]
