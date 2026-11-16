"""Static invariants for the release workflow's isolated job environments."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "release.yml"


def _workflow() -> dict:
    return yaml.load(WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.SafeLoader)


def test_release_job_checks_out_tag_and_sets_up_python_before_using_script() -> None:
    workflow = _workflow()
    job = workflow["jobs"]["draft-release"]
    steps = job["steps"]
    names = [step.get("name", "") for step in steps]

    checkout = steps[names.index("Checkout commit referenced by release tag")]
    setup_python = steps[names.index("Configure Python")]
    download = steps[names.index("Download distribution artifacts")]
    validate = steps[names.index("Verify build artifacts before release")]

    assert checkout["uses"].startswith("actions/checkout@")
    assert checkout["with"]["ref"] == "${{ github.ref }}"
    assert setup_python["uses"].startswith("actions/setup-python@")
    assert setup_python["with"]["python-version"] == "3.13"
    assert steps.index(checkout) < steps.index(setup_python) < steps.index(download)
    assert steps.index(download) < steps.index(validate)
    assert (ROOT / "scripts" / "release_validation.py").is_file()
    assert "validate_distribution_artifacts" in validate["run"]
    assert 'Path("dist")' in validate["run"]


def test_release_job_uses_minimal_permissions_and_handles_all_release_states() -> None:
    workflow = _workflow()
    job = workflow["jobs"]["draft-release"]
    assert job["permissions"] == {"contents": "write"}

    steps = job["steps"]
    by_name = {step.get("name", ""): step for step in steps}
    state_step = by_name["Check existing GitHub release state"]
    create_step = by_name["Create draft GitHub release"]
    verify_existing = by_name["Verify existing release remains complete"]

    assert "release-status" in state_step["run"]
    assert 'echo "state=${release_state}"' in state_step["run"]
    assert "steps.existing.outputs.state == 'missing'" in create_step["if"]
    assert "gh release create" in create_step["run"]
    assert "exit 1" in create_step["run"]
    assert "verify-release" in create_step["run"]
    assert "verify-release" in verify_existing["run"]
    assert "steps.existing.outputs.state == 'draft'" in verify_existing["if"]
    assert "steps.existing.outputs.state == 'published'" in verify_existing["if"]
    assert "metadata:" not in str(job["permissions"])


def test_quality_workflows_lint_release_validation_script() -> None:
    for path in (
        ROOT / ".github" / "workflows" / "ci.yml",
        WORKFLOW_PATH,
    ):
        workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.SafeLoader)
        commands = "\n".join(
            step.get("run", "")
            for job in workflow["jobs"].values()
            for step in job.get("steps", [])
        )
        assert "scripts/release_validation.py" in commands
