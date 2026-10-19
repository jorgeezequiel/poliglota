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

## Pull requests

- Describe what changed and why.
- Include the real test output.
- Do not commit secrets, credentials, models, or large binary artifacts.

## License

Poliglota is released under the MIT License (see `LICENSE`). By submitting a
contribution, you agree that it may be distributed under the same MIT License.
You keep the copyright of your own contributions; there is no Contributor
License Agreement and no copyright assignment. If your contribution includes
code or resources from a third party, state their origin and license so they
can be documented.
