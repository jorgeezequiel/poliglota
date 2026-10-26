# Architecture overview

Poliglota separates localization formats, translation engines and the command
line so each layer can evolve independently. The current state is:

- core contracts (locale, translation data, engine and format protocols);
- four format adapters: ARB, JSON, YAML and XML;
- optional local engines (Marian and PyTorch) plus an in-memory response cache;
- quality helpers for glossary, placeholders and validation;
- the CLI commands `validate`, `sync`, `list-locales` and `translate`.

Translation is optional and local: it requires the `[gpu]` extra and a model
that is already available on disk. The project never downloads models on its
own.

## Layers

```
poliglota/
├── core/          # format- and engine-agnostic contracts
│   ├── locale.py       # Locale
│   ├── translation.py  # TranslationRequest / TranslationResult / TranslationIssue
│   ├── engine.py       # TranslationEngine protocol
│   ├── format.py       # FormatAdapter protocol, LocalizedResource/Document
│   └── quality.py      # quality-related contracts
├── formats/       # concrete readers/writers for localization formats
│   ├── arb.py          # ARB: parsing, discovery, validation, sync, adapter
│   ├── json_adapter.py # JSON adapter
│   ├── yaml_adapter.py # YAML adapter
│   ├── xml_adapter.py  # XML adapter (defusedxml)
│   └── registry_init.py # runtime adapter registry
├── engines/       # local translation engines and support utilities
│   ├── marian.py       # Marian/Opus-MT adapter
│   ├── pytorch_engine.py
│   ├── response_cache.py # optional in-memory cache
│   └── request_queue.py  # optional helper (not wired into the CLI)
├── quality/       # glossary, placeholder and validation helpers
├── gpu.py         # device detection and validation
├── config.py      # convenience defaults used by the CLI
└── cli.py         # argparse-based command line
```

### `core` - contracts

`poliglota.core` is deliberately free of any format or engine specifics. A test
(`tests/test_core_contracts.py`) parses every module in `core/` and fails if one
of them imports `poliglota.formats` or anything ARB-related. This keeps the
contracts reusable for other formats and engines.

- `Locale` - a language/region identifier chosen by the caller. It performs no
  normalization: the *tool* code (e.g. `pt_BR`) and the *engine* code (e.g.
  `pb` for Argos, `por_Latn` for NLLB) are different things and must be mapped
  explicitly, never silently.
- `TranslationRequest` / `TranslationResult` / `TranslationIssue` - plain data
  describing what to translate and what came back, plus warnings/errors.
- `TranslationEngine` - a `Protocol` (structural type). It has `name`,
  `engine_language(locale)`, `supports(source, target)` and `translate(...)`.
- `FormatAdapter` / `LocalizedResource` / `LocalizedDocument` - the shape every
  format adapter exposes so the CLI and future orchestration can stay generic.

### `formats` - adapters

`poliglota.formats.arb` implements full ARB support and the `FormatAdapter`
contract (`ARBFormatAdapter`, `name == "arb"`), including placeholder checks,
locale inference and round-trip I/O. ARB is the reference implementation and
the default `--format`.

The JSON, YAML and XML adapters implement the same contract with generic
read/write operations. They are registered in
`poliglota/formats/registry_init.py` and are covered by
`tests/test_formats_registry.py`, `tests/test_formats_roundtrip.py` and
`tests/test_cli_multiformat.py`. Format-specific validation for them is limited
compared with ARB. CSV and gettext have no adapter.

### `engines` - local translation

- `marian.py` wraps Hugging Face sequence-to-sequence models and resolves the
  default model for a language pair from `_DEFAULT_MOTOR_PRIORITY` in
  `poliglota/cli.py`.
- `pytorch_engine.py` provides the alternative `pytorch` engine path.
- `response_cache.py` implements `ResponseCache`, an opt-in in-memory cache
  disabled by default.
- `request_queue.py` implements `RequestQueue`/`QueueFullError` as an optional
  utility; it is not part of the CLI execution path.

### `quality` - glossary and placeholders

`poliglota.quality` hosts glossary handling (`glossary.py`), placeholder
protection (`placeholders.py`) and validation helpers (`validation.py`). The
package has an explicit `__init__.py` so it matches the package list declared in
`pyproject.toml`.

### Compatibility shims

`poliglota/arb_reader.py`, `models.py`, `validator.py` and `syncer.py` are thin
re-export shims pointing at `poliglota.formats.arb`, so existing imports keep
working. New code should import from `poliglota.formats.arb` directly.

### `cli`

`poliglota.cli` wires the adapters and engines to the four commands:
`validate`, `sync`, `list-locales` and `translate`. `--format` always selects
the *adapter* (`arb`, `json`, `yaml`, `xml`); it is not an output format option.
