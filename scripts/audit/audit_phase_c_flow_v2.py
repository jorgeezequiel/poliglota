#!/usr/bin/env python3
"""
Phase C — Production Flow Audit (v2)

Tests real translation via poliglota CLI command (installed via setuptools entry point).
Validates engine, model, device propagation through the workflow.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run_cmd(args: list[str]) -> dict:
    """Run command and capture output using GPU venv."""
    try:
        venv_python = Path(r"C:\projetos1\visualcode\poliglota\venv_gpu\Scripts\python.exe")
        # Invoke via -m poliglota instead of poliglota command
        if args[0] == "poliglota":
            args = [str(venv_python), "-m", "poliglota"] + args[1:]
        
        result = subprocess.run(
            args,
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
    except Exception as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "success": False,
        }


def main():
    print("=" * 80)
    print("PHASE C — PRODUCTION FLOW AUDIT (CLI)")
    print("=" * 80)
    print()
    
    tests = []
    repo_root = Path(r"C:\projetos1\visualcode\poliglota")
    
    # Test 1: Help
    print("[TEST 1/8] Help command")
    r = run_cmd(["poliglota", "--help"])
    tests.append(("Help", r["success"]))
    print(f"Status: {'PASS' if r['success'] else 'FAIL'}")
    if not r['success']:
        print(f"Error: {r['stderr'][:200]}")
    
    # Test 2: List locales (simple)
    print("\n[TEST 2/8] Validate source locale (pt_BR)")
    corpus = Path(r"C:\projetos1\visualcode\teste-traducoes\questlog\lib\l10n\americas\sul")
    r = run_cmd(["poliglota", "validate",
                 "--root", str(corpus),
                 "--source", "pt_BR",
                 "--format", "arb"]    )
    tests.append(("Validate pt_BR", r["success"]))
    print(f"Status: {'PASS' if r['success'] else 'FAIL'}")
    if not r['success']:
        print(f"Error: {r['stderr'][:200]}")
    else:
        print(f"Output: {r['stdout'][:200]}")
    
    # Test 3: Simple translate
    print("\n[TEST 3/8] Translate string (pytorch/cuda)")
    r = run_cmd(["poliglota", "translate",
                 "--source", "pt_BR",
                 "--target", "en_US",
                 "--engine", "pytorch",
                 "--model", "facebook/nllb-200-distilled-600M",
                 "--device", "cuda",
                 "Saldo"])
    tests.append(("Translate pytorch/cuda", r["success"]))
    print(f"Status: {'PASS' if r['success'] else 'FAIL'}")
    print(f"Output: {r['stdout'][:150] if r['stdout'] else r['stderr'][:150]}")
    
    # Test 4: With placeholder
    print("\n[TEST 4/8] Translate with placeholder")
    r = run_cmd(["poliglota", "translate",
                 "--source", "pt_BR",
                 "--target", "en_US",
                 "--engine", "pytorch",
                 "--device", "cuda",
                 "--preserve-placeholders",
                 "Seu saldo aumentou em {percent}% hoje."])
    tests.append(("Translate with placeholder", r["success"]))
    print(f"Status: {'PASS' if r['success'] else 'FAIL'}")
    output = r['stdout'] if r['stdout'] else r['stderr']
    print(f"Output: {output[:150]}")
    if "{percent}" in output:
        print("[OK] Placeholder preserved")
    else:
        print("[WARNING] Placeholder missing")
    
    # Test 5: Invalid device (should fail)
    print("\n[TEST 5/8] Invalid device (expected FAIL)")
    r = run_cmd(["poliglota", "translate",
                 "--source", "pt_BR",
                 "--target", "en_US",
                 "--device", "invalid_xyz",
                 "Teste"])
    tests.append(("Invalid device fails", r["returncode"] != 0))
    print(f"Status: {'PASS (correctly failed)' if r['returncode'] != 0 else 'FAIL (should fail)'}")
    if r['stderr']:
        print(f"Error: {r['stderr'][:150]}")
    
    # Test 6: CPU device
    print("\n[TEST 6/8] CPU device")
    r = run_cmd(["poliglota", "translate",
                 "--source", "pt_BR",
                 "--target", "en_US",
                 "--engine", "pytorch",
                 "--device", "cpu",
                 "Saldo"])
    tests.append(("CPU device", r["success"]))
    print(f"Status: {'PASS' if r['success'] else 'FAIL'}")
    print(f"Output: {r['stdout'][:150] if r['stdout'] else r['stderr'][:150]}")
    
    # Test 7: Unsupported language (should fail)
    print("\n[TEST 7/8] Unsupported language (expected FAIL)")
    r = run_cmd(["poliglota", "translate",
                 "--source", "pt_BR",
                 "--target", "xyz_ZZ",
                 "--device", "cuda",
                 "Teste"])
    tests.append(("Unsupported language fails", r["returncode"] != 0))
    print(f"Status: {'PASS (correctly failed)' if r['returncode'] != 0 else 'FAIL (should fail)'}")
    if r['stderr']:
        print(f"Error: {r['stderr'][:150]}")
    
    # Test 8: Without model specification (default)
    print("\n[TEST 8/8] Default model")
    r = run_cmd(["poliglota", "translate",
                 "--source", "pt_BR",
                 "--target", "en_US",
                 "Teste"])
    tests.append(("Default model", r["success"]))
    print(f"Status: {'PASS' if r['success'] else 'FAIL'}")
    print(f"Output: {r['stdout'][:150] if r['stdout'] else r['stderr'][:150]}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    passed = sum(1 for _, s in tests if s)
    total = len(tests)
    print(f"Passed: {passed}/{total}")
    for name, success in tests:
        status = "PASS" if success else "FAIL"
        print(f"  {status}: {name}")
    
    # Save
    report = {
        "phase": "C",
        "total_tests": total,
        "passed_tests": passed,
        "failed_tests": total - passed,
        "tests": [{"name": n, "success": s} for n, s in tests],
    }
    report_file = Path(r"C:\projetos1\visualcode\poliglota\reports\phase_c_flow_audit.json")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(report, indent=2))
    print(f"\n[OK] Report saved to: {report_file}")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    exit(main())
