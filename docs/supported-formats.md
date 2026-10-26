# Supported formats

## ARB (Application Resource Bundle) — implemented

ARB is the resource format used by Flutter. Poliglota discovers and processes
ARB files and exposes them through the `FormatAdapter` contract.

What is implemented today:

- Discovery of `**/*.arb` files under a root directory.
- Locale and module inference from the `app_<module>_<locale>.arb` convention.
- Separation of translatable entries from `@`-prefixed metadata (including
  `@@locale`).
- Placeholder consistency checks (`{name}`-style placeholders).
- Key synchronization: copy keys missing in target locales from the source
  locale, with a dry-run mode.
- Read/write round-trip through `ARBFormatAdapter` (metadata preserved,
  `@@locale` injected when missing, `ensure_ascii=False`, 2-space indent).

ARB API surface (`poliglota.formats.arb`):

| Function / class | Purpose |
| --- | --- |
| `discover_arb_files(root)` | find ARB files, return `ArbFile` records |
| `load_arb(path)` | load a single ARB file as a dict |
| `locale_from_arb_path(path)` | infer locale from the file name |
| `module_from_arb_path(path)` | infer module from the file name |
| `arb_content_keys(data)` | list translatable keys |
| `validate_root(root, source)` | validate all locales against a source |
| `validate_placeholders(...)` | placeholder consistency check |
| `sync_locale_files(root, source, dry_run)` | fill missing keys |
| `ARBFormatAdapter` | `FormatAdapter` implementation (`name == "arb"`) |

## JSON, YAML and XML — implemented via generic adapters

These three formats are registered in the runtime registry
(`poliglota/formats/registry_init.py`) and are selectable through `--format`:

| Adapter | `--format` value | Discovery | Read/write | Notes |
| --- | --- | --- | --- | --- |
| `JsonFormatAdapter` | `json` | ✅ | ✅ | Flat key/value locale files |
| `YamlFormatAdapter` | `yaml` | ✅ | ✅ | Requires the format's file naming convention |
| `XmlFormatAdapter` | `xml` | ✅ | ✅ | Parsed with `defusedxml` (safe XML parsing) |

They share the generic `FormatAdapter` contract, so `validate`, `sync` and
`list-locales` work for them at the level covered by
`tests/test_formats_registry.py`, `tests/test_formats_roundtrip.py` and
`tests/test_cli_multiformat.py`. Format-specific validation is intentionally
limited compared with ARB: there is no placeholder model or metadata handling
for these formats yet, and locale inference still depends on file naming
conventions.

## CSV and gettext — planned, not implemented

CSV and gettext have **no adapter** and no support in any command. They are
listed as future work only. New formats must be added as `FormatAdapter`
implementations under `poliglota/formats/`, without adding format-specific code
to `poliglota/core/`.
