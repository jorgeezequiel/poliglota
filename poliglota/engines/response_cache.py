"""In-memory translation response cache for offline engine workflows."""

from __future__ import annotations

import threading
from collections import OrderedDict
from hashlib import sha256
from typing import Any


class ResponseCache:
    """Bounded in-memory cache for translation responses.

    The cache is intentionally simple and local to the current process. It keys
    requests by the canonicalized source text, language pair, model identity, and
    a serialization of relevant translation options. Results are not persisted to
    disk and are rejected if they are empty, None, or otherwise obviously invalid.
    """

    def __init__(self, max_entries: int = 256, enabled: bool = True) -> None:
        """Initialize the cache with a bounded entry count and runtime state."""
        if max_entries <= 0:
            msg = "max_entries must be greater than zero"
            raise ValueError(msg)
        self.max_entries = max_entries
        self.enabled = enabled
        self._entries: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.RLock()
        self.hit_count = 0
        self.miss_count = 0
        self.evictions = 0

    @property
    def current_size(self) -> int:
        """Return the number of cached entries."""
        with self._lock:
            return len(self._entries)

    @property
    def metrics(self) -> dict[str, int]:
        """Return a snapshot of cache activity counters."""
        with self._lock:
            return {
                "hit_count": self.hit_count,
                "miss_count": self.miss_count,
                "current_size": self.current_size,
                "evictions": self.evictions,
            }

    @staticmethod
    def _normalize_options(options: Any) -> str:
        if options is None:
            return "{}"
        if isinstance(options, str):
            return options
        try:
            import json

            return json.dumps(options, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        except TypeError:
            return repr(options)

    @classmethod
    def _make_key(
        cls,
        text: str,
        source_lang: str,
        target_lang: str,
        *,
        model_name: str | None = None,
        model_version: str | None = None,
        options: dict[str, Any] | list[Any] | str | None = None,
    ) -> str:
        payload = {
            "text": text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "model_name": model_name or "",
            "model_version": model_version or "",
            "options": cls._normalize_options(options),
        }
        return sha256(repr(payload).encode("utf-8")).hexdigest()

    def get(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        *,
        model_name: str | None = None,
        model_version: str | None = None,
        options: dict[str, Any] | list[Any] | str | None = None,
    ) -> Any:
        """Return a cached value if present for the given request signature."""
        if not self.enabled:
            return None

        with self._lock:
            key = self._make_key(
                text,
                source_lang,
                target_lang,
                model_name=model_name,
                model_version=model_version,
                options=options,
            )
            if key in self._entries:
                self.hit_count += 1
                value = self._entries[key]
                self._entries.move_to_end(key)
                return value

            self.miss_count += 1
            return None

    def set(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        *,
        model_name: str | None = None,
        model_version: str | None = None,
        options: dict[str, Any] | list[Any] | str | None = None,
        value: Any,
    ) -> bool:
        """Store a value in the cache for the given request signature."""
        if not self.enabled:
            return False

        if value is None or (isinstance(value, str) and value == ""):
            return False

        with self._lock:
            key = self._make_key(
                text,
                source_lang,
                target_lang,
                model_name=model_name,
                model_version=model_version,
                options=options,
            )
            if key in self._entries:
                self._entries.pop(key)
            self._entries[key] = value

            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
                self.evictions += 1

            return True

    def clear(self) -> None:
        """Discard all cached entries and reset the in-memory store."""
        with self._lock:
            self._entries.clear()


__all__ = ["ResponseCache"]
