"""Simple bounded request queue for translation workflows."""

from __future__ import annotations

import threading
from collections import deque
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


class QueueFullError(RuntimeError):
    """Raised when a new request is submitted while the queue is full."""


class RequestQueue:
    """Synchronous queue that serializes work in submission order.

    The queue keeps each submitted payload counted as pending until the queue is
    explicitly shut down. This preserves the configured backlog limit without
    introducing unsafe parallel execution or background job management.
    """

    def __init__(self, *, handler: Callable[[Any], Any], max_pending: int = 32) -> None:
        """Initialize the queue with a handler and bounded pending list."""
        if max_pending <= 0:
            msg = "max_pending must be greater than zero"
            raise ValueError(msg)
        self.handler = handler
        self.max_pending = max_pending
        self._pending: deque[Any] = deque()
        self._lock = threading.RLock()
        self._closed = False
        self.metrics: dict[str, int] = {
            "received": 0,
            "completed": 0,
            "failed": 0,
            "pending": 0,
        }

    @property
    def is_closed(self) -> bool:
        """Return True when the queue has been shut down."""
        return self._closed

    def submit(self, payload: Any) -> Any:
        """Submit a payload for processing and return the handler result."""
        with self._lock:
            if self._closed:
                msg = "RequestQueue is closed"
                raise RuntimeError(msg)

            if len(self._pending) >= self.max_pending:
                msg = "Request queue is full"
                raise QueueFullError(msg)

            self.metrics["received"] += 1
            self._pending.append(payload)
            self.metrics["pending"] = len(self._pending)

        try:
            result = self.handler(payload)
        except Exception:
            with self._lock:
                self.metrics["failed"] += 1
                self.metrics["pending"] = len(self._pending)
            raise

        with self._lock:
            self.metrics["completed"] += 1
            self.metrics["pending"] = len(self._pending)
        return result

    def shutdown(self) -> None:
        """Close the queue and clear any pending work."""
        with self._lock:
            self._closed = True
            self._pending.clear()
            self.metrics["pending"] = len(self._pending)


__all__ = ["QueueFullError", "RequestQueue"]
