"""Compatibility shim.

ARB key synchronization now lives in :mod:`poliglota.formats.arb`. This module
is kept so existing imports (``from poliglota.syncer import ...``) keep working.
"""

from __future__ import annotations

from .formats.arb import sync_locale_files

__all__ = ["sync_locale_files"]
