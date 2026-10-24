# Contributing

Thanks for your interest in Poliglota. This project is in early development, so
guidelines are intentionally lightweight for now.

## Before you start

- Open an issue to discuss significant changes before implementing them.
- Keep changes focused and minimal.
- Do not add translation engines, model downloads, or network calls without
  prior discussion.

## Development workflow

1. Create a virtual environment with the interpreter you want to test. Windows
   example (Python 3.13.11 is the current reference environment):

   ```powershell
   py -3.13 -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

2. Install Poliglota in editable mode. With network access, the recommended
   form also installs the development tools declared in `pyproject.toml`
   (`pytest` and `ruff`):

   ```bash
   python -m pip install -e ".[dev]"
   ```

   Without network access, install `setuptools>=77` and `wheel` from a local
   source first, then run:

   ```bash
   python -m pip install -e . --no-build-isolation --no-index
   ```

3. Run the test suite:

   ```bash
   python -m pytest
   ```

4. Run lint/format if `ruff` is available:

   ```bash
   python -m ruff check poliglota tests
   python -m ruff format --check poliglota tests
   ```

## Code guidelines

- Keep `poliglota/core/` free of format- and engine-specific code.
- Add formats as `FormatAdapter` implementations under `poliglota/formats/`.
- Never suppress type errors (`as any`, `# type: ignore`) to make code pass.
- Add or update tests for behavior changes.

## Versioning and release policy

Poliglota follows Semantic Versioning (SemVer) as the release policy, with the
package metadata in `pyproject.toml` as the single source of truth for the
published version.

### Version source of truth

- `pyproject.toml` declares the official package version.
- `poliglota.__version__` mirrors that value for runtime introspection.
- A separate `VERSION` file is not added by default because it would create a
  second editable version source and make divergence more likely.
- If a `VERSION` file is ever introduced, it must be generated from the package
  metadata or validated automatically against it before any release process.

### Version increment rules

- `MAJOR`: incompatible public changes or breaking behavior changes in the CLI,
  package API, or file-format compatibility expectations.
- `MINOR`: new features or capabilities that preserve backward compatibility.
- `PATCH`: bug fixes and operational corrections that do not change the public
  contract.
- `0.x.y`: this project is still pre-1.0, so changes that alter user-facing
  behavior should still be documented carefully even when the major version is 0.
- Pre-releases use the SemVer suffix convention, for example:
  `0.2.0-alpha.1`, `0.2.0-beta.1`, `0.2.0-rc.1`.

### Changelog policy

- Keep a section named `Unreleased` for work not yet associated with a version.
- When a version is prepared, move the unreleased items into a new versioned
  section such as `## [0.1.0] - YYYY-MM-DD`.
- Use the Keep a Changelog categories: `Added`, `Changed`, `Deprecated`, `Removed`,
  `Fixed`, and `Security`.
- Group changes by user impact, not by raw commit list.
- Do not add entries without evidence in code or tests.

### Git tags and future releases

- Version tags should correspond to the version assigned in `pyproject.toml`.
- Example naming convention: `v0.1.0`.
- Tags are a release record, not a reason to increment the version by themselves.
- A version should only be tagged after the changelog, packaging metadata, and
  relevant validation have been checked.

### Release checklist before a future version

1. Confirm the version in `pyproject.toml` and `poliglota.__version__` match.
2. Review `CHANGELOG.md` and move `Unreleased` entries into the target version.
3. Confirm relevant tests pass.
4. Validate package metadata and buildability with the local environment.
5. Document any known limitations, hardware requirements, or model/cache
   prerequisites.
6. Only then create the version tag and record the release note.

## Pull requests

- Describe what changed and why.
- Include the real test output.
- Do not commit secrets, credentials, models, or large binary artifacts.
- Update `CHANGELOG.md` when the change is user-visible or release-relevant.

## License

Poliglota is released under the MIT License (see `LICENSE`). By submitting a
contribution, you agree that it may be distributed under the same MIT License.
You keep the copyright of your own contributions; there is no Contributor
License Agreement and no copyright assignment. If your contribution includes
code or resources from a third party, state their origin and license so they
can be documented.
