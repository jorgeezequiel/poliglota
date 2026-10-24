# Poliglota

Poliglota is a reusable Python toolkit for validating, synchronizing, and translating textual resources in software localization workflows.

It is designed to help teams work with locale files and translation data without embedding file-format logic into the core domain model. The project targets the general problem of keeping translated resources consistent across locales while reducing manual work in repetitive localization tasks and avoiding unnecessary dependence on external translation services for simple, local workflows.

This repository is not restricted to Flutter or ARB. ARB is an important and well-supported workflow, but the implementation is structured around a generic localization core and a registry of adapters for multiple resource formats.

## Why this project exists

Localization and translation work often involve the same patterns across many codebases:

- validating missing keys across locale variants
- checking placeholder consistency between source and target resources
- synchronizing a base locale into other locales
- translating text locally when an offline or on-premise workflow is preferred
- reducing repeated manual edits in multilingual software projects

Poliglota addresses that by keeping validation, synchronization, and translation logic separate from the concrete format being processed. The goal is to reduce rework and to make the tooling adaptable as resource formats evolve.

This project does not claim to guarantee cost savings or token savings in measured production terms. It is a practical localization helper whose value depends on the project context, the selected engine, the availability of model assets, and the quality of the reviewed output.

## Quick start

### Basic install

```bash
python -m pip install -e .
```

The base install exposes the CLI entrypoint:

```bash
poliglota
```

### Local translation engine install

The repository declares the optional dependencies in `pyproject.toml`:

```bash
python -m pip install -e ".[gpu]"
```

The `gpu` extra installs the ML stack used by the local translation engine flow:

- `torch>=2.7.0`
- `transformers>=5.20.0`
- `huggingface-hub>=0.20.0`

For development tooling:

```bash
python -m pip install -e ".[gpu,dev]"
```

### Typical CLI commands

```bash
poliglota validate --root . --source pt_BR --format arb
poliglota sync --root . --source pt_BR --dry-run --format arb
poliglota list-locales --root . --format json
poliglota translate --source pt_BR --target en_US --text "Olá, mundo!" --engine marian
```

## Operating model and practical use cases

Poliglota is meant for software teams that need to manage multiple locale files in a consistent and repeatable way. Typical scenarios include:

- validating that all locales contain the same keys as the source locale
- synchronization of missing keys into target locales
- checking placeholder mismatches such as `{count}` or `{name}` across files
- translating text locally using cached model assets instead of routing all work through external services
- building a reusable localization pipeline around a modular set of adapters

## Formats and operations

The runtime implementation currently includes these format adapters in the default registry:

| Format | Status in code | CLI support | Validation | Synchronization | Translation workflow | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `arb` | Confirmed | Yes | Confirmed | Confirmed | Supported by the project workflow | Most explicit ARB validation and sync behavior |
| `yaml` | Confirmed | Yes | Confirmed via adapter contract | Confirmed via generic operations | Supported by adapter layer | Format adapter exists in the runtime registry |
| `json` | Confirmed | Yes | Confirmed via adapter contract | Confirmed via generic operations | Supported by adapter layer | Locale files supported by generic operations |
| `xml` | Confirmed | Yes | Confirmed via adapter contract | Confirmed via generic operations | Supported by adapter layer | Adapter exists in the registry |
| Other formats | Not confirmed as implemented in this branch | Not documented as runtime-supported | Unverified | Unverified | Unverified | Requires explicit adapter implementation |

The implementation is therefore broader than ARB-only, but the exact maturity of each adapter can vary by file structure and validation coverage. The code and tests confirm the existence of adapters and CLI support for `arb`, `yaml`, `json`, and `xml`.

## Architecture

The implementation is organized in layers:

- `poliglota/core`: localization models and reusable contracts
- `poliglota/formats`: adapters and registry setup
- `poliglota/quality`: validation helpers for placeholders and quality rules
- `poliglota/engines`: translation engine implementations and protocol layer
- `poliglota/cli.py`: command dispatch and CLI behavior

The registry is initialized in `poliglota.formats.registry_init` and registers the default adapters for YAML, JSON, XML, and ARB. The CLI chooses a format by name and then delegates work to the generic operations layer rather than embedding format-specific behavior in the command surface.

## Translation engines and GPU status

The repository includes two concrete translation engine implementations:

- `marian`: default engine path when no engine is specified
- `pytorch`: PyTorch/Transformers engine alternative backed by Hugging Face model loading

The engine layer is optional in practice and is tied to the `gpu` extra in `pyproject.toml`. The project contains GPU detection and VRAM validation utilities, but those features are implementation pieces, not proof that every CUDA/MPS environment is fully validated for translation performance.

The current state is:

- CPU execution path is implemented and can be selected explicitly
- GPU device detection and VRAM checks are present in the codebase
- GPU-enabled translation behavior is environment-dependent and should be treated as subject to local verification
- benchmark results and real-world performance numbers remain part of the ongoing evaluation, not a documented guarantee

This means the README should describe GPU support as implemented and environment-dependent, not as proven universal acceleration for translation.

## Offline requirements and model preparation

Offline local translation is not automatic; it depends on the selected engine, the model registry or local cache, and the required dependencies.

The implementation expects a model to be available locally when offline mode is in effect, and it includes checks around local cache state and model loading. The code path is designed to handle that explicitly, but it does not guarantee every language pair or every model will work without a compatible environment and cached assets.

Practical requirements include:

- required ML dependencies from `pyproject.toml`
- configured model assets or a valid cached Hugging Face model
- a supported language pair for the chosen engine
- local device compatibility for CPU, CUDA, or MPS paths

This should be read as a requirement for the local translation flow, not as a blanket promise of always-available offline translation.

## Development and validation

The repository uses `pytest` and `ruff` as the development validation workflow.

Run the test suite:

```bash
python -m pytest
```

Run lint and formatting checks:

```bash
python -m ruff check poliglota tests
python -m ruff format --check poliglota tests
```

## Documentation

Relevant documents in this repository include:

- `docs/architecture/overview.md` — architecture overview
- `docs/supported-formats.md` — format support notes
- `docs/guides/translation-engine.md` — translation engine behavior and model assumptions
- `docs/guides/arb-workflow.md` — ARB-specific workflow examples
- `docs/development/testing.md` — testing and validation procedure

## Important caveats

- The project is designed as a reusable localization toolkit, not as a Flutter-only utility.
- ARB remains an important workflow, but the current codebase includes broader runtime support.
- The translation engine stack is optional and depends on extra packages and model assets.
- GPU detection and VRAM checks are implemented, but local GPU translation quality and performance still require environment-specific validation.
- Benchmark evaluation for CPU/GPU performance is ongoing and should not be treated as final or guaranteed.

## License

The project code is released under the MIT License. See `LICENSE` for the original code terms.

Third-party models, weights, tokenizers, and related resources remain subject to their own licenses and terms of use.

