"""Registry for localization format adapters."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from poliglota.core import FormatAdapter


class FormatRegistry:
    """Simple registry for format adapters.

    Stores and retrieves adapters by name. Allows the CLI and other consumers
    to work with multiple formats without hardcoding format-specific details.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._adapters: dict[str, FormatAdapter] = {}

    def register(self, adapter: FormatAdapter) -> None:
        """Register a format adapter by its name."""
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> FormatAdapter:
        """Retrieve a format adapter by name.

        Raises KeyError if the format is not registered.
        """
        if name not in self._adapters:
            msg = f"Format '{name}' not registered. Available: {', '.join(self._adapters.keys())}"
            raise KeyError(msg)
        return self._adapters[name]

    def all(self) -> dict[str, FormatAdapter]:
        """Return a dict of all registered adapters."""
        return self._adapters.copy()

    def names(self) -> list[str]:
        """Return a sorted list of all registered format names."""
        return sorted(self._adapters.keys())
