# Architecture overview

Poliglota is organized in layers so that the translation logic is independent
from any specific localization format or application framework. The project is
in an early stage: the **core contracts** and the **ARB format adapter** exist
and are tested; translation engines are not implemented yet. Engine selection
and implementation are still pending (see `docs/supported-formats.md`).

## Layers

```
poliglota/
├── core/          # format- and engine-agnostic contracts (no ARB, no engine)
│   ├── locale.py       # Locale
│   ├── translation.py  # TranslationRequest / TranslationResult / TranslationIssue
│   ├── engine.py       # TranslationEngine protocol
│   └── format.py       # FormatAdapter protocol, LocalizedResource/Document
├── formats/       # concrete readers/writers for localization formats
│   └── arb.py          # ARB: parsing, discovery, validation, sync, ARBFormatAdapter
├── config.py      # convenience defaults for the current ARB commands
└── cli.py         # argparse-based command line (validate, sync, list-locales)
```

### `core` — contracts

`poliglota.core` is deliberately free of any format or engine specifics. A test
(`tests/test_core_contracts.py`) parses every module in `core/` and fails if one
of them imports `poliglota.formats` or anything ARB-related. This keeps the
contracts reusable for future formats (XML, JSON, CSV, …) and engines.

- `Locale` — a language/region identifier chosen by the caller. It performs no
  normalization: the *tool* code (e.g. `pt_BR`) and the *engine* code (e.g.
  `pb` for Argos, `por_Latn` for NLLB) are different things and must be mapped
  explicitly, never silently.
- `TranslationRequest` / `TranslationResult` / `TranslationIssue` — plain data
  describing what to translate and what came back, plus warnings/errors.
- `TranslationEngine` — a `Protocol` (structural type). It has `name`,
  `engine_language(locale)`, `supports(source, target)` and `translate(...)`.
  No engine is bundled yet.
- `FormatAdapter` / `LocalizedResource` / `LocalizedDocument` — the shape every
  format adapter exposes so the CLI and future orchestration can stay generic.

### `formats` — adapters

`poliglota.formats.arb` implements ARB support and the `FormatAdapter` contract
(`ARBFormatAdapter`, `name == "arb"`). The original ARB functions and the
`ArbFile` model moved here unchanged.

### Compatibility shims

`poliglota/arb_reader.py`, `models.py`, `validator.py` and `syncer.py` are now
thin re-export shims pointing at `poliglota.formats.arb`, so existing imports
keep working. New code should import from `poliglota.formats.arb` directly.

### `cli`

`poliglota.cli` wires the ARB adapter to the three existing commands. Command
syntax and output are unchanged by the reorganization.
