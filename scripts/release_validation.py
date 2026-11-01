# ruff: noqa: EM102,TRY003,TRY300,S310,E501
"""Utilities for validating release tags and Python package artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tarfile
import tomllib
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

SEMVER_VERSION_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SEMVER_TAG_PATTERN = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def validate_tag(tag: str) -> str:
    """Validate a stable Git tag and return the version without the leading ``v``."""
    if not isinstance(tag, str):
        msg = "Tag must be a string."
        raise ValueError(msg)
    if not tag:
        msg = "Tag is required."
        raise ValueError(msg)
    if any(ord(ch) > 127 for ch in tag):
        msg = f"Tag '{tag}' must use ASCII characters only."
        raise ValueError(msg)
    if not SEMVER_TAG_PATTERN.fullmatch(tag):
        msg = (
            f"Invalid tag '{tag}'. Expected format: "
            "vMAJOR.MINOR.PATCH using stable SemVer."
        )
        raise ValueError(msg)
    return tag[1:]


def read_project_versions(root: Path) -> dict[str, str]:
    """Read version metadata from the sources that must remain in sync."""
    root = Path(root)

    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.exists():
        raise FileNotFoundError(f"Missing file: {pyproject_path}")
    try:
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        msg = f"Unable to parse {pyproject_path}: {exc}"
        raise ValueError(msg) from exc
    try:
        pyproject_version = str(pyproject["project"]["version"])
    except (KeyError, TypeError) as exc:
        msg = "pyproject.toml is missing the project.version field."
        raise ValueError(msg) from exc

    version_path = root / "VERSION"
    if not version_path.exists():
        raise FileNotFoundError(f"Missing file: {version_path}")
    version_file = version_path.read_text(encoding="utf-8").strip()

    init_path = root / "poliglota" / "__init__.py"
    if not init_path.exists():
        raise FileNotFoundError(f"Missing file: {init_path}")
    init_text = init_path.read_text(encoding="utf-8")
    match = re.search(
        r'^__version__\s*=\s*["\']([^"\']+)["\']',
        init_text,
        flags=re.MULTILINE,
    )
    if match is None:
        msg = "Missing or invalid __version__ assignment in poliglota/__init__.py"
        raise ValueError(msg)
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
        msg = f"Project versions are inconsistent: {versions}"
        raise ValueError(msg)
    value = next(iter(unique))
    if not SEMVER_VERSION_PATTERN.fullmatch(value):
        msg = f"Project version '{value}' is not a valid stable SemVer string."
        raise ValueError(msg)
    return value


def validate_tag_against_project(tag: str, root: Path) -> str:
    """Validate the git tag and ensure it matches the project metadata."""
    version = validate_tag(tag)
    project_version = assert_project_versions_match(root)
    if version != project_version:
        msg = (
            f"Tag version '{version}' does not match the project metadata "
            f"version '{project_version}'."
        )
        raise ValueError(msg)
    return version


def _metadata_lines(metadata_text: str, label: str) -> tuple[str, str]:
    name_matches = re.findall(r"^Name:\s*(.+)$", metadata_text, flags=re.MULTILINE)
    version_matches = re.findall(r"^Version:\s*(.+)$", metadata_text, flags=re.MULTILINE)

    if len(name_matches) != 1:
        msg = (
            f"{label} metadata contains {len(name_matches)} Name entries; "
            "expected exactly one."
        )
        raise ValueError(msg)
    if len(version_matches) != 1:
        msg = (
            f"{label} metadata contains {len(version_matches)} Version entries; "
            "expected exactly one."
        )
        raise ValueError(msg)
    return name_matches[0].strip(), version_matches[0].strip()


def _read_metadata_from_wheel(path: Path) -> tuple[str, str]:
    """Read the wheel metadata and return the canonical name and version."""
    if not path.exists():
        raise FileNotFoundError(f"Missing wheel: {path}")
    try:
        with zipfile.ZipFile(path) as archive:
            metadata_entries = [
                member for member in archive.namelist() if member.endswith(".dist-info/METADATA")
            ]
            if not metadata_entries:
                msg = f"No METADATA file found inside {path.name}"
                raise ValueError(msg)
            if len(metadata_entries) != 1:
                msg = (
                    f"Multiple METADATA files found inside {path.name}; "
                    "expected exactly one."
                )
                raise ValueError(msg)
            try:
                raw = archive.read(metadata_entries[0])
            except KeyError as exc:
                msg = f"Wheel archive member is unreadable: {path.name}"
                raise ValueError(msg) from exc
            try:
                metadata_text = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                msg = f"Wheel metadata is not valid UTF-8: {path.name}"
                raise ValueError(msg) from exc
    except zipfile.BadZipFile as exc:
        msg = f"Wheel is corrupted or not a valid ZIP archive: {path.name}"
        raise ValueError(msg) from exc
    except OSError as exc:
        msg = f"Unable to read wheel archive: {path.name}"
        raise ValueError(msg) from exc

    return _metadata_lines(metadata_text, "Wheel")


def _read_metadata_from_sdist(path: Path) -> tuple[str, str]:
    """Read the sdist metadata and return the canonical name and version."""
    if not path.exists():
        raise FileNotFoundError(f"Missing source distribution: {path}")
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            pkg_info_members = [
                member
                for member in archive.getmembers()
                if member.name.endswith("PKG-INFO")
                and not member.name.endswith(".egg-info/PKG-INFO")
            ]
            if not pkg_info_members:
                msg = f"No PKG-INFO file found inside {path.name}"
                raise ValueError(msg)
            if len(pkg_info_members) != 1:
                msg = (
                    f"Multiple PKG-INFO files found inside {path.name}; "
                    "expected exactly one."
                )
                raise ValueError(msg)
            member = pkg_info_members[0]
            extracted = archive.extractfile(member)
            if extracted is None:
                msg = f"PKG-INFO member is unreadable inside {path.name}"
                raise ValueError(msg)
            data = extracted.read()
            if not data:
                msg = f"PKG-INFO file is empty inside {path.name}"
                raise ValueError(msg)
            try:
                metadata_text = data.decode("utf-8")
            except UnicodeDecodeError as exc:
                msg = f"Source distribution metadata is not valid UTF-8: {path.name}"
                raise ValueError(msg) from exc
    except tarfile.TarError as exc:
        msg = f"Source distribution is corrupted or not a valid tar.gz archive: {path.name}"
        raise ValueError(msg) from exc
    except OSError as exc:
        msg = f"Unable to read source distribution: {path.name}"
        raise ValueError(msg) from exc

    return _metadata_lines(metadata_text, "Source distribution")


def validate_distribution_artifacts(dist_dir: str | Path, expected_version: str) -> tuple[Path, Path]:
    """Validate the wheel and sdist files and ensure both match the expected version."""
    dist_path = Path(dist_dir)
    wheels = sorted(dist_path.glob("*.whl"))
    sdists = sorted(dist_path.glob("*.tar.gz"))

    if len(wheels) != 1:
        msg = (
            f"Expected exactly one wheel in {dist_path}, found {len(wheels)}: {wheels}"
        )
        raise ValueError(msg)
    if len(sdists) != 1:
        msg = (
            f"Expected exactly one source distribution in {dist_path}, "
            f"found {len(sdists)}: {sdists}"
        )
        raise ValueError(msg)

    wheel = wheels[0]
    sdist = sdists[0]

    wheel_name, wheel_version = _read_metadata_from_wheel(wheel)
    sdist_name, sdist_version = _read_metadata_from_sdist(sdist)

    if wheel_name != "poliglota":
        msg = (
            "Wheel package name mismatch: expected 'poliglota', "
            f"found {wheel_name!r}"
        )
        raise ValueError(msg)
    if sdist_name != "poliglota":
        msg = (
            "Source distribution package name mismatch: expected 'poliglota', "
            f"found {sdist_name!r}"
        )
        raise ValueError(msg)

    if wheel_version != expected_version:
        msg = (
            "Wheel metadata version mismatch: expected "
            f"{expected_version!r}, found {wheel_version!r}"
        )
        raise ValueError(msg)
    if sdist_version != expected_version:
        msg = (
            "Source distribution metadata version mismatch: expected "
            f"{expected_version!r}, found {sdist_version!r}"
        )
        raise ValueError(msg)

    return wheel, sdist


def fetch_github_release_state(
    repo: str,
    tag_name: str,
    token: str | None = None,
    timeout: float = 10.0,
) -> tuple[int, dict | None]:
    """Query the GitHub Releases API for a tag and return the HTTP status + payload."""
    if not repo:
        msg = "GitHub repository name is required."
        raise ValueError(msg)
    if not tag_name:
        msg = "GitHub tag name is required."
        raise ValueError(msg)

    url = f"https://api.github.com/repos/{repo}/releases/tags/{tag_name}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "poliglota-release-validation",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload_bytes = response.read()
            status_code = response.getcode()
            try:
                return status_code, json.loads(payload_bytes.decode("utf-8"))
            except json.JSONDecodeError as exc:
                msg = (
                    f"GitHub release API returned invalid JSON for tag '{tag_name}'."
                )
                raise ValueError(msg) from exc
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        if status_code in {401, 403, 422, 500}:
            msg = f"GitHub release API returned an error status: {status_code}"
            raise ValueError(msg) from exc
        body = exc.read()
        try:
            payload = json.loads(body.decode("utf-8")) if body else None
        except json.JSONDecodeError as exc:
            msg = (
                "GitHub release API returned an unexpected non-JSON body "
                f"for tag '{tag_name}'."
            )
            raise ValueError(msg) from exc
        return status_code, payload
    except TimeoutError as exc:
        msg = f"GitHub release API request timed out while checking tag '{tag_name}'."
        raise ValueError(msg) from exc
    except urllib.error.URLError as exc:
        msg = (
            f"GitHub release API request failed for tag '{tag_name}': {exc.reason}"
        )
        raise ValueError(msg) from exc


def classify_release_response(status_code: int | None, payload: dict | None) -> str:
    """Classify a GitHub release API response as missing, draft, published, or unexpected."""
    if status_code == 404:
        return "missing"
    if status_code == 200:
        if payload is None:
            msg = "GitHub release API returned HTTP 200 with no JSON payload."
            raise ValueError(msg)
        draft = payload.get("draft")
        if isinstance(draft, bool):
            return "draft" if draft else "published"
        msg = (
            "GitHub release API returned HTTP 200 but missing a valid 'draft' flag: "
            f"{payload!r}"
        )
        raise ValueError(msg)
    if status_code in {401, 403, 422, 500}:
        msg = f"GitHub release API returned an error status: {status_code}"
        raise ValueError(msg)
    if status_code is None:
        msg = "GitHub release API call did not return a valid HTTP status code."
        raise ValueError(msg)
    if 500 <= status_code < 600:
        msg = f"GitHub release API returned a server error status: {status_code}"
        raise ValueError(msg)
    msg = f"Unexpected GitHub release API status code: {status_code}"
    raise ValueError(msg)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate release tags and package artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    tag_parser = subparsers.add_parser(
        "tag",
        help="Validate a release tag against project metadata.",
    )
    tag_parser.add_argument("--tag", required=True)
    tag_parser.add_argument("--root", default=".")

    dist_parser = subparsers.add_parser(
        "dist",
        help="Validate the wheel and sdist metadata.",
    )
    dist_parser.add_argument("--dist-dir", default="dist")
    dist_parser.add_argument("--version", required=True)

    status_parser = subparsers.add_parser(
        "release-status",
        help="Check a GitHub release state for a tag.",
    )
    status_parser.add_argument("--repo", required=True)
    status_parser.add_argument("--tag", required=True)
    status_parser.add_argument("--token", default=None)
    status_parser.add_argument("--timeout", type=float, default=10.0)

    return parser


def main() -> int:
    """Entry point for shell execution."""
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
        if args.command == "release-status":
            status_code, payload = fetch_github_release_state(
                args.repo,
                args.tag,
                token=args.token,
                timeout=args.timeout,
            )
            state = classify_release_response(status_code, payload)
            print(state)
            return 0
        parser.error(f"Unsupported command: {args.command}")
        return 2
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"release validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
