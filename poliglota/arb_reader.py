"""Compatibility shim.

The ARB implementation now lives in :mod:`poliglota.formats.arb`. This module
is kept so existing imports (``from poliglota.arb_reader import ...``) keep
working.
"""

from __future__ import annotations

from .formats.arb import (
    arb_content_keys,
    arb_file_key,
    discover_arb_files,
    load_arb,
    locale_from_arb_path,
    module_from_arb_path,
)

__all__ = [
    "arb_content_keys",
    "arb_file_key",
    "discover_arb_files",
    "load_arb",
    "locale_from_arb_path",
    "module_from_arb_path",
]
