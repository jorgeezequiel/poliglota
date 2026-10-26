# Contributing

Thanks for your interest in Poliglota. This project is in early development, so
guidelines are intentionally lightweight for now.

## Before you start

- Open an issue to discuss significant changes before implementing them.
- Keep changes focused and minimal.
- Do not add translation engines, model downloads, or network calls without
  prior discussion.
- Treat model artifacts, caches, and weighted resources as external user-managed
  resources unless the change explicitly documents a separate local workflow.
- Prefer documentation updates that clarify boundaries and limitations when a
  feature is still conceptual or unverified.

## Non-negotiable principles

Poliglota is built on nine foundational principles that govern all contributions and future development:

1. **Qualidade contextual**: Translation must be better than word-for-word; preserve meaning, context, terminology, placeholders, and structure. Do not claim commercial-grade quality guarantees.

2. **Modelos gratuitos padrão**: Select, test, and recommend free models; never establish defaults without evidence.

3. **Liberdade de modelos**: Users configure their own model directories, substitute recommended models, and use acquired models (if compatible). Model selection is the user's choice.

4. **Liberdade sobre código**: Users can clone, modify, fork, and distribute modified versions (respecting MIT and third-party licenses).

5. **Recursos separados do repositório**: Models, weights, tokenizers, caches, and downloads must live outside GitHub. No silent downloads or downloads without user consent.

6. **Consumo controlado**: Balance quality, speed, CPU, GPU, RAM, VRAM, and storage. Provide configurable limits and adaptive strategies. Fail with clear errors when necessary.

7. **CPU e GPU transparentes**: Requested device ≠ detected device ≠ actually used device. GPU selection must fail clearly when unavailable; auto mode may choose transparently.

8. **Funcionamento offline**: After resource preparation, translation works locally without online services. Network operations must be separate and identified.

9. **Sem fiscalização de licenças**: Do not block models or automatically audit licenses. Documentation explains separation and user responsibility.

These principles are not negotiable. All code changes, documentation updates, and feature proposals must align with them. If a contribution conflicts with any principle, it will be rejected.

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

## Mandatory checks before PR merge

The following checks are **required** and must pass before any pull request is merged. These are not optional or subjective:

### 1. Validation (required)
- Run `python -m pytest` and confirm all tests pass (or explicitly document pre-existing failures if unrelated to your changes).
- For format-related changes, run format-specific validation tests.
- For engine-related changes, run engine-specific tests and confirm device fallback behavior.

### 2. Round-trip I/O (required for format/locale changes)
- For changes to `poliglota/formats/`, confirm that read → modify → write → read produces identical output (round-trip consistency).
- For changes to locale handling, validate that all supported locales load and save without data loss.
- Test with real `.arb`, `.yaml`, `.json`, and `.xml` files if the change affects multiple formats.

### 3. Zero lint violations (required)
- Run `python -m ruff check poliglota tests` and confirm no violations.
- Run `python -m ruff format --check poliglota tests` and confirm formatting is correct.
- Fix all violations before requesting review. Type errors and linting issues are non-negotiable.

### 4. Documentation alignment (required for feature changes)
- Update `docs/` files to reflect new behavior.
- If a change affects device selection, model loading, or offline behavior, update the relevant guide.
- If a new format adapter is added, add it to `docs/supported-formats.md` with its status (Implemented/Experimental/Planned).
- Reference `docs/LIMITATIONS.md` if introducing known limitations.

### 5. Nine principles compliance (required for all changes)
- Verify the change does not violate any of the nine non-negotiable principles (see "Non-negotiable principles" above).
- If uncertain, open an issue to discuss before implementing.

All five checks must pass. If any check fails, the PR will not be merged.

## Versioning and release policy

Poliglota follows Semantic Versioning (SemVer) as the release policy, with the
package metadata in `pyproject.toml` as the single source of truth for the
published version.

### Version source of truth

- `pyproject.toml` declares the official package version.
- `poliglota.__version__` mirrors that value for runtime introspection.
- `VERSION` is a plain-text mirror of the same version, kept for tooling that
  reads the version from a file.
- `tests/test_version_consistency.py` validates all three sources plus the
  installed package metadata, and runs as a required CI job (`quality`).
- Because the three sources are validated automatically, changing a version
  means updating all of them in the same change; never let them diverge.

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
