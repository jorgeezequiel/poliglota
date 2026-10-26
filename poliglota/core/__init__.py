"""Format-agnostic core contracts and rules for Poliglota.

The core defines:

- language identifiers (:class:`~poliglota.core.locale.Locale`);
- translation requests, results and issues (:mod:`poliglota.core.translation`);
- the translation-engine contract (:mod:`poliglota.core.engine`);
- the localization-format contract (:mod:`poliglota.core.format`).

Modules in this package must not import localization-format adapters (for
example ARB) or translation engines, so the core keeps working without
Flutter, ARB or Android XML being present.
"""

from .engine import TranslationEngine
from .format import FormatAdapter, LocalizedDocument, LocalizedResource
from .locale import Locale
from .translation import (
    IssueSeverity,
    TranslationIssue,
    TranslationRequest,
    TranslationResult,
)

__all__ = [
    "FormatAdapter",
    "IssueSeverity",
    "Locale",
    "LocalizedDocument",
    "LocalizedResource",
    "TranslationEngine",
    "TranslationIssue",
    "TranslationRequest",
    "TranslationResult",
]
