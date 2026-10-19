"""Compatibility shim.

ARB validation now lives in :mod:`poliglota.formats.arb`. This module is kept
so existing imports (``from poliglota.validator import ...``) keep working.
"""

from __future__ import annotations

from .formats.arb import validate_placeholders, validate_root

__all__ = ["validate_placeholders", "validate_root"]
