#!/usr/bin/env python3
"""
Phase C — Production Flow Audit.

Traces the CLI flow using a local corpus and explicit arguments, without relying on
machine-specific paths or a fixed CUDA venv.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from ._portable import add_common_audit_arguments, resolve_paths


def run_command(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> dict:
    """Run a command and capture output."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": "Command timed out",
            "success": False,
        }
    except Exception as exc:  # pragma: no cover - defensive wrapper for subprocess issues
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
            "success": False,
        }


def audit_cli_flow(*, repo_root: Path, corpus_root: Path | None, python_executable: Path | None = None) -> dict:
    """Audit the CLI flow with a portable corpus and interpreter selection."""
    if not repo_root.exists():
        raise FileNotFoundError(f"Repository root not found: {repo_root}")
    if corpus_root is None:
        raise ValueError("A corpus_root is required for the CLI flow audit.")
    if not corpus_root.exists():
        raise FileNotFoundError(f"Corpus root not found: {corpus_root}")

    python_cmd = [str(python_executable or Path(sys.executable))]
    default_env = os.environ.copy()
    tests: list[dict[str, object]] = []

    print("[TEST 1] CLI Help Command")
    result = run_command([*python_cmd, "-m", "poliglota", "--help"], cwd=repo_root, env=default_env)
    tests.append({
        "name": "CLI Help",
        "command": "python -m poliglota --help",
        "returncode": result["returncode"],
        "success": result["success"],
        "output_sample": result["stdout"][:500] if result["stdout"] else "(empty)",
    })
    print(f"Status: {'PASS' if result['success'] else 'FAIL'} (exit code: {result['returncode']})")

    print("\n[TEST 2] List Locales")
    result = run_command(
        [*python_cmd, "-m", "poliglota", "list-locales", "--root", str(corpus_root), "--format", "arb"],
        cwd=repo_root,
        env=default_env,
    )
    tests.append({
        "name": "List Locales",
        "command": "python -m poliglota list-locales --root ... --format arb",
        "returncode": result["returncode"],
        "success": result["success"],
        "output_sample": result["stdout"][:500] if result["stdout"] else "(empty)",
    })
    print(f"Status: {'PASS' if result['success'] else 'FAIL'} (exit code: {result['returncode']})")

    print("\n[TEST 3] Validate Source Locale (pt_BR)")
    result = run_command(
        [
            *python_cmd,
            "-m",
            "poliglota",
            "validate",
            "--root",
            str(corpus_root),
            "--source",
            "pt_BR",
            "--format",
            "arb",
            "--check-keys",
            "--check-placeholders",
        ],
        cwd=repo_root,
        env=default_env,
    )
    tests.append({
        "name": "Validate pt_BR Source",
        "command": "python -m poliglota validate --source pt_BR ...",
        "returncode": result["returncode"],
        "success": result["returncode"] == 0,
        "output_sample": result["stdout"][:500] if result["stdout"] else result["stderr"][:500],
    })
    print(f"Status: {'PASS' if result['success'] else 'FAIL'} (exit code: {result['returncode']})")

    print("\n[TEST 4] Translate Single String (pt_BR -> en_US, pytorch/cpu)")
    result = run_command(
        [
            *python_cmd,
            "-m",
            "poliglota",
            "translate",
            "--source",
            "pt_BR",
            "--target",
            "en_US",
            "--engine",
            "pytorch",
            "--device",
            "cpu",
            "Saldo",
        ],
        cwd=repo_root,
        env={**default_env, "OMP_NUM_THREADS": "2"},
    )
    tests.append({
        "name": "Translate String (pytorch/cpu)",
        "command": "python -m poliglota translate --engine pytorch --device cpu ...",
        "returncode": result["returncode"],
        "success": result["success"],
        "output_sample": result["stdout"][:500] if result["stdout"] else result["stderr"][:500],
    })
    print(f"Status: {'PASS' if result['success'] else 'FAIL'} (exit code: {result['returncode']})")

    print("\n[TEST 5] Invalid Device Request (should FAIL gracefully)")
    result = run_command(
        [
            *python_cmd,
            "-m",
            "poliglota",
            "translate",
            "--source",
            "pt_BR",
            "--target",
            "en_US",
            "--engine",
            "pytorch",
            "--model",
            "facebook/nllb-200-distilled-600M",
            "--device",
            "invalid_device_xyz",
            "Teste",
        ],
        cwd=repo_root,
        env=default_env,
    )
    tests.append({
        "name": "Invalid Device (expected to fail)",
        "command": "python -m poliglota translate --device invalid_device_xyz ...",
        "returncode": result["returncode"],
        "success": result["returncode"] != 0,
        "output_sample": result["stderr"][:500] if result["stderr"] else result["stdout"][:500],
    })
    print(f"Status: {'PASS (correctly failed)' if result['returncode'] != 0 else 'FAIL (should have failed)'}")

    print("\n[TEST 6] CPU device translation")
    result = run_command(
        [
            *python_cmd,
            "-m",
            "poliglota",
            "translate",
            "--source",
            "pt_BR",
            "--target",
            "en_US",
            "--engine",
            "pytorch",
            "--device",
            "cpu",
            "Saldo",
        ],
        cwd=repo_root,
        env={**default_env, "OMP_NUM_THREADS": "2"},
    )
    tests.append({
        "name": "CPU Device (should work)",
        "command": "python -m poliglota translate --device cpu ...",
        "returncode": result["returncode"],
        "success": result["success"],
        "output_sample": result["stdout"][:500] if result["stdout"] else result["stderr"][:500],
    })
    print(f"Status: {'PASS' if result['success'] else 'FAIL'} (exit code: {result['returncode']})")

    return {
        "tests": tests,
        "total_tests": len(tests),
        "passed_tests": sum(1 for test in tests if test["success"]),
        "failed_tests": sum(1 for test in tests if not test["success"]),
    }


def main(argv: list[str] | None = None) -> int:
    """Run the CLI flow audit with explicit paths."""
    parser = argparse.ArgumentParser(description="Run a portable CLI flow validation for the project.")
    add_common_audit_arguments(parser)
    args = parser.parse_args(argv)
    paths = resolve_paths(
        repo_root=args.repo_root,
        corpus_root=args.corpus_root,
        report_dir=args.report_dir,
        python_executable=args.python_executable,
    )
    repo_root = paths["repo_root"]
    corpus_root = paths["corpus_root"] or repo_root
    report_dir = paths["report_dir"]

    print("=" * 80)
    print("PHASE C — PRODUCTION FLOW AUDIT")
    print("=" * 80)
    print()

    result = audit_cli_flow(repo_root=repo_root, corpus_root=corpus_root, python_executable=paths["python_executable"])
    report_path = report_dir / "phase_c_flow_audit.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\n[OK] Report saved to: {report_path}")
    print(f"Passed: {result['passed_tests']}/{result['total_tests']}")
    return 0 if result["failed_tests"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
