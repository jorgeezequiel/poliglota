"""Shared helpers for portable audit scripts."""

from __future__ import annotations

import argparse
from pathlib import Path


def resolve_repo_root(script_path: Path | str | None = None) -> Path:
    """Return the repository root, derived from the current script location."""
    candidate = Path(script_path).resolve() if script_path is not None else Path(__file__).resolve()
    return candidate.parents[2] if candidate.name.endswith(".py") else candidate


def add_common_audit_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Add CLI arguments used across the audit scripts."""
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root to treat as the project base. If omitted, it is inferred from the script path.",
    )
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=None,
        help="Root of the corpus to audit. If omitted, the script will look for a local test corpus under the repo.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=None,
        help="Directory where JSON reports should be written. Defaults to <repo-root>/reports.",
    )
    parser.add_argument(
        "--python-executable",
        type=Path,
        default=None,
        help="Python interpreter to use when launching CLI checks. Defaults to sys.executable.",
    )
    return parser


def resolve_paths(*, repo_root: Path | None = None, corpus_root: Path | None = None, report_dir: Path | None = None, python_executable: Path | None = None) -> dict[str, Path | None]:
    """Resolve the repo and output paths in a portable way."""
    resolved_repo = (repo_root or resolve_repo_root()).resolve()
    resolved_report = report_dir.resolve() if report_dir is not None else (resolved_repo / "reports").resolve()
    resolved_corpus = corpus_root.resolve() if corpus_root is not None else None
    resolved_python = python_executable.resolve() if python_executable is not None else None
    return {
        "repo_root": resolved_repo,
        "corpus_root": resolved_corpus,
        "report_dir": resolved_report,
        "python_executable": resolved_python,
    }
