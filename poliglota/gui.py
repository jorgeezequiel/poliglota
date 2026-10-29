"""Desktop GUI launcher for Poliglota."""

from __future__ import annotations

import argparse
from pathlib import Path

from .gui_app import PoliglotaGUI


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the desktop GUI entry point."""
    parser = argparse.ArgumentParser(description="Open the Poliglota desktop GUI.")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Initial project root to inspect in the desktop UI.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Start in non-graphical mode and print a startup banner instead of opening a window.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Launch the desktop application or run a headless startup smoke test."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.headless:
        return 0

    app = PoliglotaGUI(project_root=args.project_root)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
