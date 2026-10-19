# ARB workflow guide

This guide covers the currently implemented ARB commands. Examples below were
run locally and their real output is reproduced.

## Install (editable, offline)

```bash
python -m pip install -e . --no-build-isolation --no-index
```

`--no-index` keeps the install fully offline; Poliglota has no runtime
dependencies at this stage.

## Expected layout

ARB files are discovered with the `**/*.arb` glob. By convention the file name
encodes the module and the locale: `app_<module>_<locale>.arb`.

```
l10n/
├── pt_BR/app_core_pt_BR.arb
└── en_US/app_core_en_US.arb
```

## Commands

### `list-locales`

```bash
poliglota list-locales --root .
```

Real output:

```
Discovered locales:
- en_US
- pt_BR
```

### `validate`

Checks every locale against a source locale and reports missing keys and
placeholder mismatches.

```bash
poliglota validate --root . --source pt_BR
```

Real output (a source key missing from `en_US`):

```
Validation issues found:
- en_US:app_core_en_US.arb missing keys -> name
```

With no problems it prints:

```
No validation issues found for source locale 'pt_BR'.
```

### `sync`

Copies keys that exist in the source locale but are missing in the targets.
Use `--dry-run` first.

```bash
poliglota sync --root . --source pt_BR --dry-run
```

Real output:

```
Dry run: 1 locale file(s) would be updated.
```

Without `--dry-run` the files are written:

```bash
poliglota sync --root . --source pt_BR
```

If the `--source` locale does not exist in the project, `sync` prints an error
message and exits with code 1 without modifying any ARB file:

```bash
poliglota sync --root . --source fr_FR
```

Real output:

```
Source locale 'fr_FR' not found in .
```

## Notes

- The `--source` value is an explicit parameter. The CLI default (`pt_BR`) is a
  convenience inherited from the original workflow, not a rule about the
  reference language. Future translation commands must require the caller's own
  choice of source and target languages.
- Existing command syntax (`validate`, `sync`, `list-locales` and their flags)
  is preserved by the architectural reorganization.
