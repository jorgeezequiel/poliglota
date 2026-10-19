# Poliglota

**Offline translation toolkit for developers.**

Poliglota is an open-source Python project designed to help developers translate text and localization resources into multiple languages using locally available translation engines.

Its long-term goal is to make translation workflows more accessible, reduce dependence on online translation services, and help developers save time and AI tokens when working with multilingual applications.

Poliglota is intended to be a practical translation aid, not a replacement for professional human translation or review.

> **Project status:** Early development. Current capabilities, supported formats, and offline translation engines must be verified against the implemented code. Features described as planned are not necessarily available yet.

## Goals

- Translate text into multiple languages using offline translation engines.
- Reduce reliance on online APIs and services with usage limits or per-request costs.
- Help developers automate repetitive translation tasks.
- Support different application frameworks and localization formats through extensible adapters.
- Validate localization resources and identify missing keys or inconsistent placeholders.
- Keep translation workflows reproducible and easy to integrate into development environments.

## How it is intended to work

Poliglota aims to download or configure supported translation libraries and language resources so that translation can run locally after the required components have been installed.

A typical workflow is expected to include:

1. Install Poliglota and select a supported translation engine.
2. Download the required language resources while an internet connection is available.
3. Translate text or localization files locally.
4. Review the generated translations and resolve any warnings.
5. Validate the resulting localization resources before using them in an application.

**Offline requirements:** Initial downloads may require an internet connection. Offline operation depends on the selected engine, its installed dependencies, and the availability of the required language resources. Poliglota does not imply that every language pair is supported offline.

## Current functionality

The implemented scope is a Python command-line interface for Flutter ARB
localization files, backed by a format-agnostic core and an ARB format adapter.

Implemented and tested:

- Locale and localization key discovery in a project tree.
- Validation of localization keys and placeholder consistency.
- Comparison of target locales against a source locale.
- Synchronization of missing keys, with dry-run and write modes.
- A format-agnostic core (`poliglota.core`) for locales, translation
  request/result data and the `FormatAdapter` / `TranslationEngine` contracts.
- An ARB format adapter (`poliglota.formats.arb`).

The offline translation engine and additional localization formats are **not
implemented yet**. See `docs/supported-formats.md` and
`docs/architecture/overview.md` for details.

## Quick start

Poliglota requires Python 3.11 or newer; the reference environment for the
latest validation is **Python 3.13.11 on Windows** (see
[`docs/development/testing.md`](docs/development/testing.md)).

Create a virtual environment first (Windows example, selecting the interpreter
explicitly with the `py` launcher):

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
```

From the project directory, install Poliglota in editable mode (this requires
access to PyPI unless the declared build requirements are already available
locally; see the offline variant in
[`docs/development/testing.md`](docs/development/testing.md)):

```bash
python -m pip install -e .
```

Display the available commands:

```bash
poliglota --help
```

For the current ARB workflow, the commands are:

```bash
poliglota validate --root .
poliglota sync --root . --source pt_BR --dry-run
poliglota list-locales --root .
```

These commands operate on the ARB files found under the given root. Use
`poliglota --help` for the supported arguments, and see
[`docs/guides/arb-workflow.md`](docs/guides/arb-workflow.md) for verified
example output.

## Translation quality and limitations

Machine translation can contain incorrect terminology, unnatural phrasing, grammatical errors, or context-sensitive mistakes.

Poliglota is intended to assist with repetitive translation work, not to guarantee publication-ready results.

For critical, legal, medical, commercial, or highly specialized content, professional review may be necessary.

Translation quality and performance depend on the selected engine, language pair, model, hardware, and text being translated.

## Extensible architecture

Poliglota separates reusable translation functionality from framework-specific
localization handling. The layered structure is in place:

- **Core** (`poliglota.core`) — implemented: locale, translation
  request/result data, and the `FormatAdapter` / `TranslationEngine` contracts.
  Free of any format- or engine-specific code.
- **Format adapters** (`poliglota.formats`) — implemented for ARB.
- **CLI** (`poliglota.cli`) — implemented: `validate`, `sync`, `list-locales`.
- **Translation engines** — planned, not implemented.

See `docs/architecture/overview.md` for the layer rules and the decoupling
guard that enforces them.

## Documentation

- `docs/architecture/overview.md` — project layers and contracts.
- `docs/supported-formats.md` — what is implemented per format.
- `docs/guides/arb-workflow.md` — the ARB commands with real output.
- `docs/development/testing.md` — how to run tests and lint.

## Development

Poliglota requires Python 3.11 or newer and has no runtime dependencies at this
stage. The reference environment for the latest validation is Python 3.13.11 on
Windows. See [`docs/development/testing.md`](docs/development/testing.md) for
setup and test instructions.

The project uses Python packaging configuration in `pyproject.toml`. Automated
tests and code-quality checks are part of the development workflow.

Install Poliglota with the development tools declared in `pyproject.toml`
(`pytest` and `ruff`):

```bash
python -m pip install -e ".[dev]"
```

Run the test suite:

```bash
python -m pytest
```

Run the linter and the formatter check (when `ruff` is installed):

```bash
python -m ruff check poliglota tests
python -m ruff format --check poliglota tests
```

## Contributing

Contributions are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the
full guidelines: discuss significant changes before implementing them, keep
changes focused and minimal, add or update tests, and include the real test
output in pull requests.

Do not add translation engines, model downloads, or network calls without
prior discussion, and never commit secrets, credentials, or model artifacts.

## License

The original code of Poliglota is released under the **MIT License**. See the
[`LICENSE`](LICENSE) file at the repository root.

Copyright (c) 2026 Jorge Ezequiel de Lima Santos.

The MIT License covers Poliglota's original code and the project materials the
author is entitled to license that way. It does **not** cover translation
models, weights, tokenizers, vocabularies, language packages, or other
third-party resources that users may obtain separately: those keep their own
licenses and terms of use, and Poliglota does not guarantee that they can be
freely redistributed. See
[`docs/third-party-resources.md`](docs/third-party-resources.md).
