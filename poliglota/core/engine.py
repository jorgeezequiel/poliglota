"""Contract implemented by offline translation engines."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .locale import Locale
    from .translation import TranslationRequest, TranslationResult


class TranslationEngine(Protocol):
    """A machine-translation engine that runs locally.

    Implementations live under ``poliglota.engines`` and own:

    - their own language-code scheme (:meth:`engine_language`);
    - the language pairs they actually support (:meth:`supports`);
    - the resources they need (models, vocabularies, ...), which the resource
      manager installs outside the repository.

    An engine must never fall back to an online service silently: when it
    cannot translate offline, it reports the limitation instead.
    """

    @property
    def name(self) -> str:
        """Stable engine identifier used to select the engine."""
        ...

    def engine_language(self, locale: Locale) -> str:
        """Return the code this engine expects for ``locale``.

        Raises:
            ValueError: when the engine does not know the language.

        """
        ...

    def supports(self, source: Locale, target: Locale) -> bool:
        """Return whether this engine can translate ``source`` into ``target``."""
        ...

    def translate(self, request: TranslationRequest) -> TranslationResult:
        """Translate ``request`` locally and return the result."""
        ...
