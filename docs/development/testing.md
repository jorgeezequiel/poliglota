# Development and testing

## Supported Python and reference environment

- Declared support: **Python 3.11 or newer** (`requires-python = ">=3.11"` in
  `pyproject.toml`). The supported range is not reduced by the reference
  environment below.
- Reference environment for the latest validation: **Python 3.13.11 on
  Windows**, selected with the `py -3.13` launcher (pip 25.3).
- No runtime dependencies at this stage.

## Creating a virtual environment

Windows example, selecting the interpreter explicitly with the `py` launcher:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
```

Adjust `-3.13` to any interpreter within the supported range.

## Installing Poliglota

Three variants exist; choose according to your network access.

1. **Normal install** (runtime only). Requires access to PyPI the first time,
   because `pip` fetches the declared build requirements (`setuptools>=77`,
   `wheel`) from the package index:

   ```bash
   python -m pip install -e .
   ```

2. **Development install**. Same as above, plus the `dev` extra declared in
   `pyproject.toml` (`pytest` and `ruff`):

   ```bash
   python -m pip install -e ".[dev]"
   ```

3. **Offline install** (no network access). Requires `setuptools>=77` and
   `wheel` to be already available in the environment (for example, installed
   earlier from a local source), then:

   ```bash
   python -m pip install -e . --no-build-isolation --no-index
   ```

   Note: on Python 3.12+ a fresh virtual environment ships only `pip`. The
   offline variant fails in such an environment until `setuptools>=77` and
   `wheel` are present.

## Running tests

```bash
python -m pytest
```

The test suite runs without network access and currently covers:

- `tests/test_poliglota.py` — the validate/sync behavior at the library and
  CLI levels, including a regression test for `sync` with a missing source
  locale (error message and exit code 1, with the ARB files left untouched).
- `tests/test_core_contracts.py` — the core contracts and a decoupling guard
  that fails if any module in `poliglota/core/` imports a format adapter or
  ARB code.
- `tests/test_formats_arb_adapter.py` — the `ARBFormatAdapter` contract:
  discovery, read, write round-trip, and parity with the legacy discovery.

## Linting

The project uses `ruff` (configuration lives in `pyproject.toml`). With the
`dev` extra installed:

```bash
python -m ruff check poliglota tests
python -m ruff format --check poliglota tests
```

If `ruff` is not installed in the environment, the lint step cannot run; this
is an environment limitation, not a code result. Do not report lint as passing
unless it was actually executed.

Note: in the reference environment the repository passes both commands with
zero findings (`ruff check` reports `All checks passed!` and
`ruff format --check` reports all files already formatted; validated with
`ruff` 0.17.1 on Python 3.13.11). Rule exclusions and per-file ignores are
declared in `pyproject.toml`; any inline suppression carries a written
justification.

## What needs internet access

- **Requires internet access:** installing from PyPI (normal and development
  installs, and installing `setuptools`/`wheel` beforehand for the offline
  variant).
- **Tested without internet access:** creating the virtual environment, the
  test suite, every current CLI command (`validate`, `sync`, `list-locales`),
  and the offline install variant once the build requirements are present in
  the environment.

## Guidelines

- Keep `poliglota/core/` free of format- and engine-specific code.
- Add new formats as `FormatAdapter` implementations under
  `poliglota/formats/`, with tests.
- Do not download models or install translation engines as part of the test
  suite.
