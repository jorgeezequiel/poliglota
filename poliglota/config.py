"""Poliglota configuration defaults.

These are convenience defaults for the current ARB commands. They are NOT a
product-wide rule about the "reference" language: ``--source`` is always an
explicit parameter, and future translation commands must require the user's
own choice of source and target languages instead of defaulting to any
language.
"""

from __future__ import annotations

from pathlib import Path

# Default source locale for the legacy ARB commands (``validate`` and ``sync``),
# inherited from the QuestLog workflow that first motivated the tool.
DEFAULT_SOURCE_LOCALE = "pt_BR"

# Glob used to discover ARB files under a project root.
DEFAULT_ARB_GLOB = "**/*.arb"

# Default root scanned by the CLI when ``--root`` is not given.
DEFAULT_ROOT = Path()
