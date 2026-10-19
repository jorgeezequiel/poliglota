"""Translation request, result and issue models (format independent)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .locale import Locale


class IssueSeverity(StrEnum):
    """Severity of a translation issue."""

    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class TranslationIssue:
    """A warning or error produced while planning or running a translation."""

    severity: IssueSeverity
    message: str
    locale: Locale | None = None
    text_index: int | None = None

    def __str__(self) -> str:
        """Render the issue as a single line."""
        prefix = f"[{self.locale}] " if self.locale is not None else ""
        return f"{self.severity.value}: {prefix}{self.message}"


@dataclass(frozen=True, slots=True)
class TranslationRequest:
    """Plain texts to translate from one source language into target languages.

    Texts are independent of any localization format. Format adapters are
    responsible for extracting texts from their files before a request is
    built and for writing translated texts back afterwards.
    """

    source: Locale
    targets: tuple[Locale, ...]
    texts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TranslationResult:
    """Translations produced for a :class:`TranslationRequest`.

    ``translations`` maps each target locale code to one translated text per
    entry of ``TranslationRequest.texts`` (same order, same length).
    """

    source: Locale
    translations: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    issues: tuple[TranslationIssue, ...] = ()

    def translation_for(self, target: Locale) -> tuple[str, ...] | None:
        """Return the translated texts for ``target``, if present."""
        return self.translations.get(target.code)
