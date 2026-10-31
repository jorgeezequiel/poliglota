"""Desktop GUI launcher for Poliglota."""

from __future__ import annotations

import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .gui_app import PoliglotaGUI
from .gui_config import default_state_path

LOGGER = logging.getLogger(__name__)
LOG_FILE_NAME = "gui.log"
MAX_LOG_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the desktop GUI entry point."""
    parser = argparse.ArgumentParser(description="Open the Poliglota desktop GUI.")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Initial project root to inspect in the desktop UI.",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=None,
        help="Override the JSON file used to remember the form between sessions.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Start in non-graphical mode and print a startup banner instead of opening a window.",
    )
    return parser


def _configure_logging(state_path: Path | None = None) -> Path | None:
    """Send GUI diagnostics to a rotating log file next to the state file."""
    base = state_path if state_path is not None else default_state_path()
    log_path = base.parent / LOG_FILE_NAME
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_path,
            maxBytes=MAX_LOG_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError:
        return None

    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"),
    )
    package_logger = logging.getLogger("poliglota")
    package_logger.setLevel(logging.INFO)
    if not any(isinstance(existing, RotatingFileHandler) for existing in package_logger.handlers):
        package_logger.addHandler(handler)
        LOGGER.info("GUI logging configured at %s", log_path)

    return log_path


def main(argv: list[str] | None = None) -> int:
    """Launch the desktop application or run a headless startup smoke test."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.headless:
        return 0

    _configure_logging(args.state_file)

    app = PoliglotaGUI(project_root=args.project_root, state_path=args.state_file)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
