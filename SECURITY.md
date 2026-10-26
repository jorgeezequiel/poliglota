# Security Policy

## Scope

Poliglota is a local, offline translation and localization toolkit. At this
stage it has no runtime dependencies and does not send data to any online
service. There is no silent online fallback.

## Sensitive data

- Never commit credentials, API keys, tokens, certificates, or private keys.
- Use only test/sandbox identifiers during development.
- `.env` files and key material are ignored by `.gitignore`; keep it that way.

## Models and downloaded resources

- Translation models and language resources are large and must not be committed
  to the repository. The `.gitignore` ignores dedicated model directories and
  model-only extensions.
- Any future download of models must be explicit and user-initiated, and its
  license must be reviewed before use.

## Reporting a vulnerability

Since the project is in early development and has no public release channel
configured, report security concerns privately to the project maintainer rather
than in a public issue. Do not include secrets in a report.
