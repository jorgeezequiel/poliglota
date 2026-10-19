"""Language identifiers used across Poliglota."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Locale:
    """A language selected by the user.

    ``code`` is Poliglota's own identifier for the language (for example
    ``"en"``, ``"pt_BR"``, ``"es"``, ``"ja"`` or ``"de"``). It is intentionally
    *not* converted into any engine-specific code here: each translation
    engine resolves the code it expects through
    :meth:`poliglota.core.engine.TranslationEngine.engine_language`, so no
    language and no language pair is privileged by the core.

    ``display_name`` is an optional human-readable name for user interfaces.
    """

    code: str
    display_name: str | None = None

    def __post_init__(self) -> None:
        """Reject empty language codes early."""
        if not isinstance(self.code, str) or not self.code.strip():
            msg = "Locale code must be a non-empty string"
            raise ValueError(msg)

    def __str__(self) -> str:
        """Return the locale code."""
        return self.code
