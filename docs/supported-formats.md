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

## Other formats — not implemented

Additional formats (XML, JSON, CSV, gettext, …) are a goal, not a feature.
Nothing beyond ARB is implemented or claimed. New formats should be added as
`FormatAdapter` implementations under `poliglota/formats/`, without adding
format-specific code to `poliglota/core/`.
