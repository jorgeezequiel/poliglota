"""Contract implemented by localization format adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from .locale import Locale


@dataclass(frozen=True, slots=True)
class LocalizedResource:
    """A localization file discovered on disk.

    ``attributes`` carries adapter-specific extras (for example the ARB module
    name) without leaking format details into the core.
    """

    path: Path
    locale: Locale
    format: str
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LocalizedDocument:
    """A parsed localization file split into translatable and preserved data.

    ``entries`` maps translatable identifiers to their values.
    ``metadata`` holds everything that must survive a write untouched, such as
    locale headers, placeholder descriptors or comments.
    """

    locale: Locale | None
    entries: Mapping[str, Any]
    metadata: Mapping[str, Any] = field(default_factory=dict)


class FormatAdapter(Protocol):
    """Reads, validates and writes one localization format."""

    name: str

    def discover(self, root: Path) -> Sequence[LocalizedResource]:
        """Find localization files for this format under ``root``."""
        ...

    def read(self, path: Path) -> LocalizedDocument:
        """Parse the file at ``path``."""
        ...

    def write(self, document: LocalizedDocument, path: Path) -> None:
        """Write ``document`` to ``path``, preserving its metadata verbatim."""
        ...
