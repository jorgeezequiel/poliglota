from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.ci_reporting import MATRIX_OSES, PYTHON_VERSIONS, build_summary


def _jobs(*, gpu: str = "skipped") -> dict[str, dict[str, str]]:
    return {
        "quality": {"result": "success"},
        "unit-tests": {"result": "success"},
        "integration-cpu": {"result": "success"},
        "integration-gpu": {"result": gpu},
    }


def _write_all_junit(results_dir: Path) -> None:
    for os_name in MATRIX_OSES:
        for version in PYTHON_VERSIONS:
            for category in ("unit", "integration-cpu"):
                name = f"junit-{category}-{os_name}-py{version}.xml"
                report = results_dir / "artifact" / name
                report.parent.mkdir(parents=True, exist_ok=True)
                report.write_text(
                    '<testsuite tests="3" failures="0" errors="0" skipped="1"/>',
                    encoding="utf-8",
                )


@pytest.mark.unit
def test_workflow_preserves_full_matrix_and_separates_test_selection() -> None:
    workflow_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    unit_matrix = jobs["unit-tests"]["strategy"]["matrix"]

    assert unit_matrix["os"] == list(MATRIX_OSES)
    assert unit_matrix["python-version"] == list(PYTHON_VERSIONS)
    assert jobs["integration-cpu"]["strategy"]["matrix"] == unit_matrix
    cpu_test = next(
        step
        for step in jobs["integration-cpu"]["steps"]
        if step.get("name", "").startswith("Executar testes integração")
    )
    assert "not gpu and not unit" in cpu_test["run"]
    assert "--ignore=tests/test_version_consistency.py" in cpu_test["run"]
    assert cpu_test["env"]["HF_HUB_OFFLINE"] == "1"
    assert "runner.os == 'macOS'" in cpu_test["run"]
    assert "-vv -s --timeout=120" in cpu_test["run"]
    assert "--timeout-method=thread" in cpu_test["run"]
    assert "-o faulthandler_timeout=90" in cpu_test["run"]
    assert "-q --timeout=300" in cpu_test["run"]


@pytest.mark.unit
def test_workflow_keeps_real_cpu_torch_gpu_manual_and_summary_required() -> None:
    workflow_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    cpu_steps = jobs["integration-cpu"]["steps"]
    gpu = jobs["integration-gpu"]
    summary = jobs["summary"]

    assert any("whl/cpu" in str(step.get("run", "")) for step in cpu_steps)
    cpu_requirements = (
        Path(__file__).resolve().parents[1] / ".github" / "requirements-ci-cpu.txt"
    ).read_text(encoding="utf-8")
    assert "transformers" in cpu_requirements
    assert gpu["runs-on"] == ["self-hosted", "gpu", "cuda"]
    assert gpu["if"] == "github.event_name == 'workflow_dispatch'"
    assert "integration-gpu" in summary["needs"]
    assert summary["if"] == "always()"
    assert any(step.get("name") == "Instalar parser seguro de JUnit" for step in summary["steps"])
    assert "continue-on-error" not in str(workflow)


@pytest.mark.unit
def test_summary_requires_each_matrix_report_and_reports_gpu_as_skipped(tmp_path: Path) -> None:
    _write_all_junit(tmp_path)

    text, successful = build_summary(tmp_path, _jobs(), "push")

    assert successful
    assert "GPU job is manual and was not requested" in text
    assert "18; encontrados: 18" in text
    assert "skipped" in text


@pytest.mark.unit
def test_summary_rejects_unexpected_or_duplicate_junit_reports(tmp_path: Path) -> None:
    _write_all_junit(tmp_path)
    original = tmp_path / "artifact" / "junit-unit-ubuntu-latest-py3.11.xml"
    duplicate = tmp_path / "another-artifact" / original.name
    duplicate.parent.mkdir()
    duplicate.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")
    extra = tmp_path / "artifact" / "junit-old.xml"
    extra.write_text('<testsuite tests="1"/>', encoding="utf-8")

    text, successful = build_summary(tmp_path, _jobs(), "push")

    assert not successful
    assert "duplicate JUnit (2)" in text
    assert "Unexpected JUnit artifact: junit-old.xml" in text


@pytest.mark.unit
def test_summary_fails_for_missing_junit_or_failed_job(tmp_path: Path) -> None:
    _write_all_junit(tmp_path)
    (tmp_path / "artifact" / "junit-unit-ubuntu-latest-py3.11.xml").unlink()
    jobs = _jobs()
    jobs["quality"]["result"] = "cancelled"

    text, successful = build_summary(tmp_path, jobs, "push")

    assert not successful
    assert "finished as cancelled" in text
    assert "missing/duplicate JUnit" in text


@pytest.mark.unit
def test_summary_fails_if_manually_requested_gpu_is_skipped(tmp_path: Path) -> None:
    _write_all_junit(tmp_path)

    text, successful = build_summary(tmp_path, _jobs(gpu="skipped"), "workflow_dispatch")

    assert not successful
    assert "GPU was requested manually" in text
    assert "integration-gpu-self-hosted-cuda-py3.13" in text


@pytest.mark.unit
def test_summary_requires_gpu_junit_when_dispatch_gpu_succeeds(tmp_path: Path) -> None:
    _write_all_junit(tmp_path)
    gpu_report = tmp_path / "artifact" / "junit-integration-gpu-cuda-py3.13.xml"
    gpu_report.write_text(
        '<testsuite tests="1" failures="0" errors="0" skipped="0"/>',
        encoding="utf-8",
    )

    text, successful = build_summary(tmp_path, _jobs(gpu="success"), "workflow_dispatch")

    assert successful
    assert "self-hosted CUDA test executed" in text
    assert "integration-gpu-self-hosted-cuda-py3.13`: 1 collected" in text


@pytest.mark.unit
def test_summary_reports_gpu_failure_separately(tmp_path: Path) -> None:
    _write_all_junit(tmp_path)

    text, successful = build_summary(tmp_path, _jobs(gpu="failure"), "workflow_dispatch")

    assert not successful
    assert "integration-gpu" in text
    assert "failure" in text
