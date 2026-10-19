"""Compatibility shim.

:class:`ArbFile` is an ARB-specific model and now lives in
:mod:`poliglota.formats.arb`. This module is kept so existing imports
(``from poliglota.models import ArbFile``) keep working.
"""

from __future__ import annotations

from .formats.arb import ArbFile

__all__ = ["ArbFile"]
