# Changelog
## [0.0.1] - 2026-10-24

### Added
- GPU support via PyTorch with CUDA detection and fallback
- CLI flags `--device` for GPU/CPU selection
- Comprehensive benchmark: CPU vs. GPU on PazCall corpus
- VRAM validation and automatic device switching
- Context manager for resource cleanup

### Fixed
- t5-small model loading on GPU with proper memory management
- Batch size reduction on OOM errors
- Device fallback logic in PyTorchTranslationEngine
- MPS (Metal Performance Shaders) runtime check on non-macOS platforms

### Changed
- PyTorch engine now validates VRAM before GPU initialization
- Reduced VRAM requirement for t5-small from 1.5 GB to 0.8 GB

### Verified
- CUDA availability and tensor operations on GTX 1050 Ti
- pt-BR to en-US and pt-BR to es-ES translation pairs
- Benchmark results in reports/PAZCALL_CPU_GPU_RESULTS.json



All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project aims to follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `LICENSE`: the project's original code is now released under the MIT License
  (Copyright (c) 2026 Jorge Ezequiel de Lima Santos).
- `docs/third-party-resources.md`: explains that translation models, weights,
  tokenizers, vocabularies and language packages are third-party resources with
  their own licenses, not covered by Poliglota's MIT License.
- `poliglota/core/`: format- and engine-agnostic contracts — `Locale`,
  `TranslationRequest`, `TranslationResult`, `TranslationIssue`,
  `TranslationEngine` protocol, `FormatAdapter` protocol and the
  `LocalizedResource` / `LocalizedDocument` models.
- `poliglota/formats/arb.py`: `ARBFormatAdapter` implementing the
  `FormatAdapter` contract (discovery, read, write).
- `tests/test_core_contracts.py` and `tests/test_formats_arb_adapter.py`,
  including a guard that fails if `poliglota/core/` imports format adapters.
- `docs/` (architecture, supported formats, ARB workflow, testing),
  `CHANGELOG.md`, `CONTRIBUTING.md` and `SECURITY.md`.
- `pyproject.toml`: a `dev` optional-dependency extra declaring the development
  tools (`pytest`, `ruff`), installable with `pip install -e ".[dev]"`.

### Changed

- ARB implementation moved from the top-level modules into
  `poliglota/formats/arb.py`. Behavior and CLI syntax are unchanged.
- `poliglota/{arb_reader,models,validator,syncer}.py` are now compatibility
  shims re-exporting from `poliglota/formats/arb.py`.
- `pyproject.toml` `packages` now lists `poliglota`, `poliglota.core` and
  `poliglota.formats`.
- `.gitignore`: removed the blanket `*.bin` ignore (generic extensions may be
  legitimate project files) while keeping model directories and model-only
  extensions ignored; also ignores the internal phase report files and local
  tool directories (`.codegraph/`, `.omo/`).
- `pyproject.toml`: build requirement raised to `setuptools>=77`; license
  metadata expressed as an SPDX expression (`license = "MIT"` together with
  `license-files`, PEP 639); project authors declared; supported Python range
  stated explicitly (`requires-python = ">=3.11"`).
- Code-quality pass: the repository now passes `ruff check` and
  `ruff format --check` with zero findings. Findings were fixed without
  functional changes (import organization, `TYPE_CHECKING`-only and absolute
  imports, docstring conventions, `pathlib`, `str.removesuffix`). Rules that
  do not apply are scoped narrowly in `pyproject.toml` (`T201` for the CLI
  entry point; test-specific rules under `tests/`), and the remaining inline
  suppression (`TRY004` in `poliglota/formats/arb.py`) carries a written
  justification and preserves the existing exception type.
- `poliglota/core/translation.py`: `IssueSeverity` is now a `StrEnum`; the
  user-visible issue formatting is unchanged.
- `docs/development/testing.md`: the linting section no longer describes the
  checks as work in progress; it now reflects that both Ruff commands pass in
  the reference environment.

### Fixed

- `poliglota sync` with a source locale that does not exist now prints a
  clear error message and exits with code 1, instead of an unhandled
  `ValueError` traceback; no ARB file is modified, and a regression test
  covers the behavior (`tests/test_poliglota.py`).

### Notes

- Marian and PyTorch/Transformers translation engine paths are present in the
  current codebase and are treated as optional local-engine flows, not as
  universally validated production guarantees.
- The project is still in an early stage and does not currently have a public
  release tag or published version record beyond the package metadata in
  `pyproject.toml`.
- Future versioning and release decisions are governed by the SemVer and
  changelog policy described in `CONTRIBUTING.md`.
