from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts.release_validation import (
    assert_project_versions_match,
    classify_release_response,
    read_project_versions,
    validate_distribution_artifacts,
    validate_tag,
    validate_tag_against_project,
)


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v0.0.2", "0.0.2"),
        ("v0.0.3", "0.0.3"),
        ("v1.2.3", "1.2.3"),
    ],
)
def test_valid_release_tags(tag: str, expected: str) -> None:
    assert validate_tag(tag) == expected


@pytest.mark.parametrize(
    "tag",
    [
        "0.0.2",
        "v01.0.0",
        "v1.2",
        "v1.2.3.4",
        "v1.2.3-rc.1",
        "v1.2.3+build.1",
        "v1.2.3-",
        "v\\u0661.\\u0662.\\u0663",
    ],
)
def test_invalid_release_tags(tag: str) -> None:
    with pytest.raises(ValueError, match=r"Invalid tag|Tag must use ASCII characters only"):
        validate_tag(tag)


def test_project_versions_are_consistent() -> None:
    versions = read_project_versions(Path(__file__).resolve().parents[1])
    assert set(versions.values()) == {"0.0.2"}
    assert assert_project_versions_match(Path(__file__).resolve().parents[1]) == "0.0.2"


def test_project_versions_detect_divergence(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.0.3"\n', encoding="utf-8")
    (tmp_path / "VERSION").write_text("0.0.2\n", encoding="utf-8")
    pkg_dir = tmp_path / "poliglota"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text('__version__ = "0.0.2"\n', encoding="utf-8")

    with pytest.raises(ValueError, match="Project versions are inconsistent"):
        assert_project_versions_match(tmp_path)


def test_writer_checks_tag_against_project_metadata(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.0.2"\n', encoding="utf-8")
    (tmp_path / "VERSION").write_text("0.0.2\n", encoding="utf-8")
    pkg_dir = tmp_path / "poliglota"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text('__version__ = "0.0.2"\n', encoding="utf-8")

    assert validate_tag_against_project("v0.0.2", tmp_path) == "0.0.2"

    with pytest.raises(ValueError, match="does not match the project metadata version"):
        validate_tag_against_project("v0.0.3", tmp_path)


def _build_valid_wheel(path: Path, version: str = "0.0.2") -> None:
    metadata = (
        "Metadata-Version: 2.1\n"
        "Name: poliglota\n"
        f"Version: {version}\n"
        "Summary: test package\n"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("poliglota-0.0.2.dist-info/METADATA", metadata)


def test_validate_distribution_artifacts_with_valid_wheel_and_sdist(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    wheel = dist_dir / "poliglota-0.0.2-py3-none-any.whl"
    sdist = dist_dir / "poliglota-0.0.2.tar.gz"

    _build_valid_wheel(wheel)
    with tarfile.open(sdist, "w:gz") as tf:
        payload = b"Metadata-Version: 2.1\nName: poliglota\nVersion: 0.0.2\n"
        info = tarfile.TarInfo("poliglota-0.0.2/PKG-INFO")
        info.size = len(payload)
        tf.addfile(info, io.BytesIO(payload))

    validated_wheel, validated_sdist = validate_distribution_artifacts(dist_dir, "0.0.2")
    assert validated_wheel == wheel
    assert validated_sdist == sdist


def test_distribution_validation_rejects_wrong_package_name(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    wheel = dist_dir / "bad-0.0.2-py3-none-any.whl"
    sdist = dist_dir / "bad-0.0.2.tar.gz"

    with zipfile.ZipFile(wheel, "w") as zf:
        zf.writestr(
            "bad-0.0.2.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: badpkg\nVersion: 0.0.2\n",
        )
    with tarfile.open(sdist, "w:gz") as tf:
        payload = b"Metadata-Version: 2.1\nName: badpkg\nVersion: 0.0.2\n"
        info = tarfile.TarInfo("bad-0.0.2/PKG-INFO")
        info.size = len(payload)
        tf.addfile(info, io.BytesIO(payload))

    with pytest.raises(ValueError, match=r"package name mismatch|package version mismatch"):
        validate_distribution_artifacts(dist_dir, "0.0.2")


def test_distribution_validation_rejects_corrupted_archives(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "poliglota-0.0.2-py3-none-any.whl").write_bytes(b"not a zip")
    (dist_dir / "poliglota-0.0.2.tar.gz").write_bytes(b"not a tar.gz")

    with pytest.raises(ValueError, match=r"corrupted|valid ZIP archive|valid tar.gz archive"):
        validate_distribution_artifacts(dist_dir, "0.0.2")


@pytest.mark.parametrize(
    ("status_code", "payload", "expected"),
    [
        (404, {}, "missing"),
        (200, {"draft": True}, "draft"),
        (200, {"draft": False}, "published"),
    ],
)
def test_classify_release_response(status_code: int, payload: dict, expected: str) -> None:
    assert classify_release_response(status_code, payload) == expected


@pytest.mark.parametrize("status_code", [401, 403, 422, 500])
def test_classify_release_response_rejects_errors(status_code: int) -> None:
    with pytest.raises(ValueError, match=r"error status|Unexpected GitHub release API"):
        classify_release_response(status_code, {})


def test_classify_release_response_rejects_missing_payload() -> None:
    with pytest.raises(ValueError, match=r"no JSON payload|missing a valid 'draft' flag"):
        classify_release_response(200, None)
