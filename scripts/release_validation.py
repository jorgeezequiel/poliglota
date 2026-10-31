"""Utilities for validating release tags and Python package artifacts."""

from __future__ import annotations

import argparse
import re
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

SEMVER_VERSION_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SEMVER_TAG_PATTERN = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def validate_tag(tag: str) -> str:
    """Validate a stable git tag and return the version without the leading ``v``."""
    if not isinstance(tag, str):
        raise ValueError("Tag must be a string.")
    if not tag:
        raise ValueError("Tag is required.")
    if any(ord(ch) > 127 for ch in tag):
        raise ValueError(f"Tag '{tag}' must use ASCII characters only.")
    if not SEMVER_TAG_PATTERN.fullmatch(tag):
        raise ValueError(
            f"Invalid tag '{tag}'. Expected format: vMAJOR.MINOR.PATCH using stable SemVer."
        )
    return tag[1:]


def read_project_versions(root: Path) -> dict[str, str]:
    """Read version metadata from the sources that must stay in sync."""
    root = Path(root)
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.exists():
        raise FileNotFoundError(f"Missing file: {pyproject_path}")
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    pyproject_version = str(pyproject["project"]["version"])

    version_path = root / "VERSION"
    if not version_path.exists():
        raise FileNotFoundError(f"Missing file: {version_path}")
    version_file = version_path.read_text(encoding="utf-8").strip()

    init_path = root / "poliglota" / "__init__.py"
    if not init_path.exists():
        raise FileNotFoundError(f"Missing file: {init_path}")
    init_text = init_path.read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', init_text, flags=re.MULTILINE)
    if match is None:
        raise ValueError("Missing or invalid __version__ assignment in poliglota/__init__.py")
    init_version = match.group(1)

    return {
        "pyproject.toml": pyproject_version,
        "VERSION": version_file,
        "poliglota/__init__.py": init_version,
    }


def assert_project_versions_match(root: Path) -> str:
    """Ensure every project version source remains in sync and return the shared version."""
    versions = read_project_versions(root)
    unique = set(versions.values())
    if len(unique) != 1:
        raise ValueError(f"Project versions are inconsistent: {versions}")
    value = next(iter(unique))
    if not SEMVER_VERSION_PATTERN.fullmatch(value):
        raise ValueError(f"Project version '{value}' is not a valid stable SemVer string.")
    return value


def validate_tag_against_project(tag: str, root: Path) -> str:
    """Validate the git tag and ensure it matches the project metadata."""
    version = validate_tag(tag)
    project_version = assert_project_versions_match(root)
    if version != project_version:
        raise ValueError(
            f"Tag version '{version}' does not match the project metadata version '{project_version}'."
        )
    return version


def _extract_metadata_from_wheel(path: Path) -> tuple[str, str]:
    """Inspect a wheel and return the package name and version from the METADATA file."""
    if not path.exists():
        raise FileNotFoundError(f"Missing wheel: {path}")
    try:
        with zipfile.ZipFile(path) as archive:
            metadata_name = next(
                (entry for entry in archive.namelist() if entry.endswith(".dist-info/METADATA")),
                None,
            )
            if metadata_name is None:
                raise ValueError(f"No METADATA file found inside {path.name}")
            metadata = archive.read(metadata_name).decode("utf-8")
    except zipfile.BadZipFile as exc:  # pragma: no cover - exercised by tests with a bad archive
        raise ValueError(f"Wheel is corrupted or not a valid ZIP archive: {path.name}") from exc

    name_match = re.search(r"^Name: (.+)$", metadata, flags=re.MULTILINE)
    version_match = re.search(r"^Version: (.+)$", metadata, flags=re.MULTILINE)
    if name_match is None or version_match is None:
        raise ValueError(f"Wheel metadata is malformed in {path.name}")

    return name_match.group(1).strip(), version_match.group(1).strip()


def _extract_metadata_from_sdist(path: Path) -> tuple[str, str]:
    """Inspect an sdist and return the package name and version from PKG-INFO."""
    if not path.exists():
        raise FileNotFoundError(f"Missing source distribution: {path}")
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            pkginfo_member = next(
                (member for member in archive.getmembers() if member.name.endswith("PKG-INFO")),
                None,
            )
            if pkginfo_member is None:
                raise ValueError(f"No PKG-INFO file found inside {path.name}")
            metadata = archive.extractfile(pkginfo_member).read().decode("utf-8")
    except tarfile.TarError as exc:  # pragma: no cover - exercised by tests with a bad archive
        raise ValueError(f"Source distribution is corrupted or not a valid tar.gz archive: {path.name}") from exc

    name_match = re.search(r"^Name: (.+)$", metadata, flags=re.MULTILINE)
    version_match = re.search(r"^Version: (.+)$", metadata, flags=re.MULTILINE)
    if name_match is None or version_match is None:
        raise ValueError(f"Source distribution metadata is malformed in {path.name}")

    return name_match.group(1).strip(), version_match.group(1).strip()


def validate_distribution_artifacts(dist_dir: str | Path, expected_version: str) -> tuple[Path, Path]:
    """Validate the wheel and sdist files, ensuring both exist and carry the expected metadata."""
    dist_path = Path(dist_dir)
    wheels = sorted(dist_path.glob("*.whl"))
    sdists = sorted(dist_path.glob("*.tar.gz"))

    if len(wheels) != 1:
        raise ValueError(f"Expected exactly one wheel in {dist_path}, found {len(wheels)}: {wheels}")
    if len(sdists) != 1:
        raise ValueError(
            f"Expected exactly one source distribution in {dist_path}, found {len(sdists)}: {sdists}"
        )

    wheel = wheels[0]
    sdist = sdists[0]

    wheel_name, wheel_version = _extract_metadata_from_wheel(wheel)
    sdist_name, sdist_version = _extract_metadata_from_sdist(sdist)

    if wheel_name != "poliglota":
        raise ValueError(f"Wheel package name mismatch: expected 'poliglota', found {wheel_name!r}")
    if sdist_name != "poliglota":
        raise ValueError(f"Source distribution package name mismatch: expected 'poliglota', found {sdist_name!r}")

    if wheel_version != expected_version:
        raise ValueError(
            f"Wheel metadata version mismatch: expected {expected_version!r}, found {wheel_version!r}"
        )
    if sdist_version != expected_version:
        raise ValueError(
            f"Source distribution metadata version mismatch: expected {expected_version!r}, found {sdist_version!r}"
        )

    return wheel, sdist


def classify_release_response(status_code: int | None, payload: dict | None) -> str:
    """Classify a GitHub release API response as missing, draft, published, or unexpected."""
    if status_code == 404:
        return "missing"
    if status_code == 200:
        if payload is None:
            raise ValueError("GitHub release API returned HTTP 200 with no JSON payload.")
        draft = payload.get("draft")
        if isinstance(draft, bool):
            return "draft" if draft else "published"
        raise ValueError(f"GitHub release API returned HTTP 200 but missing a valid 'draft' flag: {payload!r}")
    if status_code in {401, 403, 422, 500}:
        raise ValueError(f"GitHub release API returned an error status: {status_code}")
    if status_code is None:
        raise ValueError("GitHub release API call did not return a valid HTTP status code.")
    raise ValueError(f"Unexpected GitHub release API status code: {status_code}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate release state and package artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    tag_parser = subparsers.add_parser("tag", help="Validate a release tag against project metadata.")
    tag_parser.add_argument("--tag", required=True)
    tag_parser.add_argument("--root", default=".")

    dist_parser = subparsers.add_parser("dist", help="Validate the wheel and sdist metadata.")
    dist_parser.add_argument("--dist-dir", default="dist")
    dist_parser.add_argument("--version", required=True)

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        if args.command == "tag":
            validate_tag_against_project(args.tag, Path(args.root))
            print(f"Validated tag {args.tag} against project metadata.")
            return 0
        if args.command == "dist":
            validate_distribution_artifacts(args.dist_dir, args.version)
            print(f"Validated wheel and sdist metadata for version {args.version}.")
            return 0
        parser.error(f"Unsupported command: {args.command}")
        return 2
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"release validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
