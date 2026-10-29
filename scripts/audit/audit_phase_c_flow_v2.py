#!/usr/bin/env python3
"""Phase C — Production Flow Audit (v2).

This variant prefers the active Python interpreter instead of a fixed GPU venv and
is portable across developer workstations.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from ._portable import add_common_audit_arguments, resolve_paths


def run_cmd(args: list[str], *, cwd: Path | None = None, python_executable: Path | None = None) -> dict:
    """Run a command and capture output using the active interpreter."""
    try:
        command = list(args)
        if args and args[0] == "poliglota":
            executable = python_executable or Path(sys.executable)
            command = [str(executable), "-m", "poliglota", *args[1:]]

        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0,
        }
    except Exception as exc:  # pragma: no cover - subprocess safety
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
            "success": False,
        }


def main(argv: list[str] | None = None) -> int:
    """Run a portable CLI smoke-test for the production workflow."""
    parser = argparse.ArgumentParser(description="Portable production-flow smoke test for the package CLI.")
    add_common_audit_arguments(parser)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=None,
        help="Optional corpus path used for validation checks.",
    )
    args = parser.parse_args(argv)

    paths = resolve_paths(
        repo_root=args.repo_root,
        corpus_root=args.corpus or args.corpus_root,
        report_dir=args.report_dir,
        python_executable=args.python_executable,
    )
    repo_root = paths["repo_root"]
    corpus_root = paths["corpus_root"] or repo_root
    report_dir = paths["report_dir"]
    python_executable = paths["python_executable"]

    print("=" * 80)
    print("PHASE C — PRODUCTION FLOW AUDIT (CLI)")
    print("=" * 80)
    print()

    tests: list[tuple[str, bool]] = []

    print("[TEST 1/8] Help command")
    r = run_cmd(["poliglota", "--help"], cwd=repo_root, python_executable=python_executable)
    tests.append(("Help", r["success"]))
    print(f"Status: {'PASS' if r['success'] else 'FAIL'}")
    if not r["success"]:
        print(f"Error: {r['stderr'][:200]}")

    print("\n[TEST 2/8] Validate source locale (pt_BR)")
    r = run_cmd(
        ["poliglota", "validate", "--root", str(corpus_root), "--source", "pt_BR", "--format", "arb"],
        cwd=repo_root,
        python_executable=python_executable,
    )
    tests.append(("Validate pt_BR", r["success"]))
    print(f"Status: {'PASS' if r['success'] else 'FAIL'}")
    if not r["success"]:
        print(f"Error: {r['stderr'][:200]}")

    print("\n[TEST 3/8] Translate string (pytorch/cpu)")
    r = run_cmd(
        [
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
        python_executable=python_executable,
    )
    tests.append(("Translate pytorch/cpu", r["success"]))
    print(f"Status: {'PASS' if r['success'] else 'FAIL'}")
    print(f"Output: {r['stdout'][:150] if r['stdout'] else r['stderr'][:150]}")

    print("\n[TEST 4/8] Invalid device (expected FAIL)")
    r = run_cmd(
        [
            "poliglota",
            "translate",
            "--source",
            "pt_BR",
            "--target",
            "en_US",
            "--device",
            "invalid_xyz",
            "Teste",
        ],
        cwd=repo_root,
        python_executable=python_executable,
    )
    tests.append(("Invalid device fails", r["returncode"] != 0))
    print(f"Status: {'PASS (correctly failed)' if r['returncode'] != 0 else 'FAIL (should fail)'}")

    print("\n[TEST 5/8] CPU device")
    r = run_cmd(
        [
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
        python_executable=python_executable,
    )
    tests.append(("CPU device", r["success"]))
    print(f"Status: {'PASS' if r['success'] else 'FAIL'}")

    print("\n[TEST 6/8] Unsupported language (expected FAIL)")
    r = run_cmd(
        ["poliglota", "translate", "--source", "pt_BR", "--target", "xyz_ZZ", "--device", "cpu", "Teste"],
        cwd=repo_root,
        python_executable=python_executable,
    )
    tests.append(("Unsupported language fails", r["returncode"] != 0))
    print(f"Status: {'PASS (correctly failed)' if r['returncode'] != 0 else 'FAIL (should fail)'}")

    print("\n[TEST 7/8] Default model")
    r = run_cmd(["poliglota", "translate", "--source", "pt_BR", "--target", "en_US", "Teste"], cwd=repo_root, python_executable=python_executable)
    tests.append(("Default model", r["success"]))
    print(f"Status: {'PASS' if r['success'] else 'FAIL'}")

    report = {
        "phase": "C",
        "total_tests": len(tests),
        "passed_tests": sum(1 for _, success in tests if success),
        "failed_tests": sum(1 for _, success in tests if not success),
        "tests": [{"name": name, "success": success} for name, success in tests],
    }

    report_path = report_dir / "phase_c_flow_audit.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n[OK] Report saved to: {report_path}")

    return 0 if report["failed_tests"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
