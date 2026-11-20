"""Helpers for checking pytest coverage and compiling CI results."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from defusedxml import ElementTree

MATRIX_OSES = ("ubuntu-latest", "windows-latest", "macos-latest")
PYTHON_VERSIONS = ("3.11", "3.12", "3.13")
QUALITY_ONLY = "tests/test_version_consistency.py"


class SelectionCollector:
    """Collect and verify the intended disjoint CI test partition."""

    def __init__(self) -> None:
        """Initialize counts and collection errors."""
        self.counts: Counter[str] = Counter()
        self.errors: list[str] = []

    def pytest_collection_finish(self, session: Any) -> None:
        """Count tests by CI class after pytest has collected the suite."""
        for item in session.items:
            nodeid = item.nodeid.replace("\\", "/")
            marks = {mark.name for mark in item.iter_markers()}
            if "unit" in marks and "gpu" in marks:
                self.errors.append(f"Test cannot be both unit and gpu: {nodeid}")
            if nodeid.startswith(QUALITY_ONLY):
                self.counts["quality"] += 1
            elif "gpu" in marks:
                self.counts["gpu"] += 1
            elif "unit" in marks:
                self.counts["unit"] += 1
            else:
                # Every unmarked test is intentionally part of CPU integration.
                self.counts["cpu"] += 1


def validate_selection() -> int:
    """Collect once and make test marker coverage explicit."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    try:
        import pytest
    except ImportError as exc:
        print(f"pytest is required to validate test selection: {exc}", file=sys.stderr)
        return 2

    collector = SelectionCollector()
    result = pytest.main(["--collect-only", "-qq"], plugins=[collector])
    if result not in (pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED):
        return int(result)
    if collector.errors:
        print("\n".join(collector.errors), file=sys.stderr)
        return 1

    total = sum(collector.counts.values())
    print("CI test partition (disjoint, collected by pytest):")
    print(f"  unit: {collector.counts['unit']}")
    print(f"  CPU integration (including unmarked): {collector.counts['cpu']}")
    print(f"  GPU: {collector.counts['gpu']}")
    print(f"  quality-only (version consistency): {collector.counts['quality']}")
    print(f"  total covered: {total}")
    if total == 0 or collector.counts["gpu"] == 0:
        print("Expected tests were not collected (including the GPU smoke test).", file=sys.stderr)
        return 1
    return 0


def _junit_counts(path: Path) -> tuple[int, int, int, int]:
    root = ElementTree.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else root.findall(".//testsuite")
    if not suites:
        msg = "JUnit report has no testsuite elements"
        raise ValueError(msg)
    return tuple(
        sum(int(suite.get(name, "0")) for suite in suites)
        for name in ("tests", "failures", "errors", "skipped")
    )  # type: ignore[return-value]


def build_summary(
    results_dir: Path,
    job_results: dict[str, dict[str, str]],
    event_name: str,
) -> tuple[str, bool]:
    """Summarize required jobs and require one valid JUnit file per matrix cell."""
    required_jobs = ("quality", "unit-tests", "integration-cpu")
    problems: list[str] = []
    lines = ["## Resumo de Testes CI", "", "### Resultado dos jobs"]
    for name in required_jobs:
        result = job_results.get(name, {}).get("result", "missing")
        lines.append(f"- `{name}`: **{result}**")
        if result != "success":
            problems.append(f"Required job {name} finished as {result}.")

    gpu_result = job_results.get("integration-gpu", {}).get("result", "missing")
    if gpu_result == "skipped" and event_name != "workflow_dispatch":
        gpu_status = "skipped — GPU job is manual and was not requested"
    elif gpu_result == "success":
        gpu_status = "success — self-hosted CUDA test executed"
    else:
        gpu_status = gpu_result
        if event_name == "workflow_dispatch" and gpu_result != "success":
            problems.append(f"GPU was requested manually but finished as {gpu_result}.")
        elif gpu_result not in {"skipped", "success"}:
            problems.append(f"Unexpected GPU job result: {gpu_result}.")
    lines.append(f"- `integration-gpu`: **{gpu_status}**")

    expected: dict[str, str] = {}
    for os_name in MATRIX_OSES:
        for version in PYTHON_VERSIONS:
            expected[f"unit-{os_name}-py{version}"] = f"junit-unit-{os_name}-py{version}.xml"
            expected[f"integration-cpu-{os_name}-py{version}"] = (
                f"junit-integration-cpu-{os_name}-py{version}.xml"
            )
    if event_name == "workflow_dispatch":
        expected["integration-gpu-self-hosted-cuda-py3.13"] = (
            "junit-integration-gpu-cuda-py3.13.xml"
        )

    found_files = list(results_dir.rglob("junit-*.xml")) if results_dir.exists() else []
    by_name: dict[str, list[Path]] = {}
    for path in found_files:
        by_name.setdefault(path.name, []).append(path)

    unexpected = sorted(set(by_name) - set(expected.values()))
    problems.extend(f"Unexpected JUnit artifact: {filename}." for filename in unexpected)

    lines.extend(["", "### Cobertura por sistema/Python"])
    total = failures = errors = skipped = 0
    for combination, filename in expected.items():
        matches = by_name.get(filename, [])
        if len(matches) != 1:
            problems.append(f"Expected one JUnit file for {combination}; found {len(matches)}.")
            lines.append(f"- `{combination}`: **missing/duplicate JUnit ({len(matches)})**")
            continue
        try:
            tests, failed, errored, ignored = _junit_counts(matches[0])
        except (ElementTree.ParseError, OSError, ValueError) as exc:
            problems.append(f"Invalid JUnit for {combination}: {exc}")
            lines.append(f"- `{combination}`: **invalid JUnit**")
            continue
        total += tests
        failures += failed
        errors += errored
        skipped += ignored
        lines.append(
            f"- `{combination}`: {tests} collected, {failed} failed, "
            f"{errored} errors, {ignored} skipped"
        )
        if tests == 0:
            problems.append(f"JUnit for {combination} contains zero tests.")
        if failed or errored:
            problems.append(f"JUnit for {combination} reports failures/errors.")

    if total == 0:
        problems.append("No tests were represented by JUnit reports.")
    lines.extend(
        [
            "",
            "### Totais (execuções da matriz; repetições OS/Python contam por combinação)",
            (
                f"- JUnit esperados: {len(expected)}; encontrados: "
                f"{sum(len(value) for value in by_name.values())}"
            ),
            f"- Testes executados: {total}",
            f"- Falhas: {failures}",
            f"- Erros: {errors}",
            f"- Skipped: {skipped}",
        ]
    )
    if problems:
        lines.extend(["", "### Problemas", *[f"- {problem}" for problem in problems]])
    else:
        lines.extend(["", "Todas as combinações obrigatórias têm JUnit válido e jobs aprovados."])
    return "\n".join(lines) + "\n", not problems


def summarize(results_dir: Path, event_name: str, needs_json: str) -> int:
    """Write the CI summary and return failure if required evidence is absent."""
    try:
        needs = json.loads(needs_json)
        text, successful = build_summary(results_dir, needs, event_name)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"Could not compile CI summary: {exc}", file=sys.stderr)
        return 2
    print(text)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as handle:
            handle.write(text)
    return 0 if successful else 1


def main() -> int:
    """Parse the helper command line and dispatch the requested operation."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate-selection")
    summary_parser = subparsers.add_parser("summarize")
    summary_parser.add_argument("--results-dir", type=Path, required=True)
    summary_parser.add_argument("--event-name", required=True)
    summary_parser.add_argument("--needs-json", required=True)
    args = parser.parse_args()
    if args.command == "validate-selection":
        return validate_selection()
    return summarize(args.results_dir, args.event_name, args.needs_json)


if __name__ == "__main__":
    raise SystemExit(main())
