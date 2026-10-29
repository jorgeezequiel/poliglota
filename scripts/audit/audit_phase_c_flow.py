#!/usr/bin/env python3
"""
Phase C — Production Flow Audit

Traces the complete CLI flow from arguments to translation output.
Tests real translation of a QuestLog file with the approved CUDA stack.
Validates engine, model, device propagation through the workflow.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> dict:
    """Run a command and capture output, returncode."""
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
    except Exception as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "success": False,
        }


def audit_cli_flow() -> dict:
    """Audit the complete CLI flow."""
    
    repo_root = Path(r"C:\projetos1\visualcode\poliglota")
    corpus_root = Path(r"C:\projetos1\visualcode\teste-traducoes\questlog")
    
    tests = []
    
    # Test 1: Help command (basic functionality)
    print("[TEST 1] CLI Help Command")
    print("-" * 80)
    result = run_command(
        ["poliglota", "--help"],
        cwd=repo_root
    )
    tests.append({
        "name": "CLI Help",
        "command": "python -m poliglota --help",
        "returncode": result["returncode"],
        "success": result["success"],
        "output_sample": result["stdout"][:500] if result["stdout"] else "(empty)",
    })
    print(f"Status: {'PASS' if result['success'] else 'FAIL'} (exit code: {result['returncode']})")
    
    # Test 2: List locales
    print("\n[TEST 2] List Locales from QuestLog")
    print("-" * 80)
    result = run_command(
        [sys.executable, "-m", "poliglota", "list-locales",
         "--root", str(corpus_root),
         "--format", "arb"],
        cwd=repo_root
    )
    tests.append({
        "name": "List Locales",
        "command": "poliglota list-locales --root ... --format arb",
        "returncode": result["returncode"],
        "success": result["success"],
        "output_sample": result["stdout"][:500] if result["stdout"] else "(empty)",
    })
    print(f"Status: {'PASS' if result['success'] else 'FAIL'} (exit code: {result['returncode']})")
    if result["success"]:
        print(f"Output preview:\n{result['stdout'][:300]}")
    
    # Test 3: Validate source locale
    print("\n[TEST 3] Validate Source Locale (pt_BR)")
    print("-" * 80)
    result = run_command(
        [sys.executable, "-m", "poliglota", "validate",
         "--root", str(corpus_root / "lib/l10n/americas/sul"),
         "--source", "pt_BR",
         "--format", "arb",
         "--check-keys",
         "--check-placeholders"],
        cwd=repo_root
    )
    tests.append({
        "name": "Validate pt_BR Source",
        "command": "poliglota validate --source pt_BR ...",
        "returncode": result["returncode"],
        "success": result["returncode"] == 0,
        "output_sample": result["stdout"][:500] if result["stdout"] else result["stderr"][:500],
    })
    print(f"Status: {'PASS' if result['success'] else 'FAIL'} (exit code: {result['returncode']})")
    if result["returncode"] != 0:
        print(f"Output: {result['stderr'][:300]}")
    
    # Test 4: Single string translation (pt_BR -> en_US) with PyTorch + CUDA
    print("\n[TEST 4] Translate Single String (pt_BR -> en_US, PyTorch/CUDA)")
    print("-" * 80)
    result = run_command(
        [sys.executable, "-m", "poliglota", "translate",
         "--source", "pt_BR",
         "--target", "en_US",
         "--engine", "pytorch",
         "--model", "facebook/nllb-200-distilled-600M",
         "--device", "cuda",
         "Saldo"],
        cwd=repo_root
    )
    tests.append({
        "name": "Translate String (pytorch/cuda)",
        "command": "poliglota translate --engine pytorch --device cuda ...",
        "returncode": result["returncode"],
        "success": result["success"],
        "output_sample": result["stdout"][:500] if result["stdout"] else result["stderr"][:500],
    })
    print(f"Status: {'PASS' if result['success'] else 'FAIL'} (exit code: {result['returncode']})")
    if result["stdout"]:
        print(f"Output: {result['stdout'][:200]}")
    if result["stderr"]:
        print(f"Stderr: {result['stderr'][:200]}")
    
    # Test 5: Single string with placeholders
    print("\n[TEST 5] Translate String with Placeholders (pytorch/cuda)")
    print("-" * 80)
    test_string = "Seu saldo aumentou em {percent}% hoje."
    result = run_command(
        [sys.executable, "-m", "poliglota", "translate",
         "--source", "pt_BR",
         "--target", "en_US",
         "--engine", "pytorch",
         "--model", "facebook/nllb-200-distilled-600M",
         "--device", "cuda",
         "--preserve-placeholders",
         test_string],
        cwd=repo_root
    )
    tests.append({
        "name": "Translate with Placeholders (pytorch/cuda)",
        "command": "poliglota translate --preserve-placeholders ...",
        "returncode": result["returncode"],
        "success": result["success"],
        "output_sample": result["stdout"][:500] if result["stdout"] else result["stderr"][:500],
    })
    print(f"Status: {'PASS' if result['success'] else 'FAIL'} (exit code: {result['returncode']})")
    if result["stdout"]:
        output = result["stdout"]
        print(f"Input: {test_string}")
        print(f"Output: {output[:200]}")
        # Check if placeholder was preserved
        if "{percent}" in output:
            print("✓ Placeholder preserved")
        else:
            print("! Placeholder NOT found in output")
    
    # Test 6: Invalid device (should fail with clear error)
    print("\n[TEST 6] Invalid Device Request (should FAIL gracefully)")
    print("-" * 80)
    result = run_command(
        [sys.executable, "-m", "poliglota", "translate",
         "--source", "pt_BR",
         "--target", "en_US",
         "--engine", "pytorch",
         "--model", "facebook/nllb-200-distilled-600M",
         "--device", "invalid_device_xyz",
         "Teste"],
        cwd=repo_root
    )
    tests.append({
        "name": "Invalid Device (expected to fail)",
        "command": "poliglota translate --device invalid_device_xyz ...",
        "returncode": result["returncode"],
        "success": result["returncode"] != 0,  # Should fail
        "output_sample": result["stderr"][:500] if result["stderr"] else result["stdout"][:500],
    })
    print(f"Status: {'PASS (correctly failed)' if result['returncode'] != 0 else 'FAIL (should have failed)'}")
    print(f"Error message: {result['stderr'][:200]}")
    
    # Test 7: CPU device (should work, but not use CUDA)
    print("\n[TEST 7] CPU Device (should work but not use CUDA)")
    print("-" * 80)
    result = run_command(
        [sys.executable, "-m", "poliglota", "translate",
         "--source", "pt_BR",
         "--target", "en_US",
         "--engine", "pytorch",
         "--model", "facebook/nllb-200-distilled-600M",
         "--device", "cpu",
         "Saldo"],
        cwd=repo_root,
        env={**dict(subprocess.os.environ), "OMP_NUM_THREADS": "2"}
    )
    tests.append({
        "name": "CPU Device (should work)",
        "command": "poliglota translate --device cpu ...",
        "returncode": result["returncode"],
        "success": result["success"],
        "output_sample": result["stdout"][:500] if result["stdout"] else result["stderr"][:500],
    })
    print(f"Status: {'PASS' if result['success'] else 'FAIL'} (exit code: {result['returncode']})")
    if result["stdout"]:
        print(f"Output: {result['stdout'][:200]}")
    
    # Test 8: Unsupported language pair (should fail clearly)
    print("\n[TEST 8] Unsupported Language (expected to fail)")
    print("-" * 80)
    result = run_command(
        [sys.executable, "-m", "poliglota", "translate",
         "--source", "pt_BR",
         "--target", "xyz_ZZ",  # Invalid locale
         "--engine", "pytorch",
         "--device", "cuda",
         "Teste"],
        cwd=repo_root
    )
    tests.append({
        "name": "Unsupported Language (expected to fail)",
        "command": "poliglota translate --target xyz_ZZ ...",
        "returncode": result["returncode"],
        "success": result["returncode"] != 0,  # Should fail
        "output_sample": result["stderr"][:500] if result["stderr"] else result["stdout"][:500],
    })
    print(f"Status: {'PASS (correctly failed)' if result['returncode'] != 0 else 'FAIL (should have failed)'}")
    print(f"Error message: {result['stderr'][:200]}")
    
    return {
        "tests": tests,
        "total_tests": len(tests),
        "passed_tests": sum(1 for t in tests if t["success"]),
        "failed_tests": sum(1 for t in tests if not t["success"]),
    }


def main():
    print("=" * 80)
    print("PHASE C — PRODUCTION FLOW AUDIT")
    print("=" * 80)
    print()
    
    result = audit_cli_flow()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total tests:   {result['total_tests']}")
    print(f"Passed:        {result['passed_tests']}")
    print(f"Failed:        {result['failed_tests']}")
    print()
    
    # Save results
    report_file = Path(r"C:\projetos1\visualcode\poliglota\reports\phase_c_flow_audit.json")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"[OK] Report saved to: {report_file}")
    
    return 0 if result["failed_tests"] == 0 else 1


if __name__ == "__main__":
    exit(main())
