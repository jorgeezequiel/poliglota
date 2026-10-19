# Third-party translation resources

This document explains the boundary between the Poliglota license and the
translation resources that users may obtain separately.

## Summary

- **Poliglota's original code is distributed under the MIT License** (see
  `LICENSE` at the repository root).
- **Translation models, weights, tokenizers, vocabularies, language packages
  and similar resources are separate third-party artifacts.** They are not
  covered by Poliglota's MIT License.
- The MIT License of Poliglota **does not replace, override, or extend** the
  licenses of those resources. Each resource keeps its own license and terms
  of use, as defined by its provider.
- Poliglota is not a distributor or licensor of those resources. They are
  obtained by the user, separately, according to the user's own choice.

## Current state

No translation engine has been selected, no translation resources are bundled
with this repository, and no models have been downloaded by the project. This
document describes the intended separation of concerns; it does not list,
endorse, or license any specific resource.

## What users should be able to verify

Before downloading or using a translation resource, the user should be able to
consult, when the information is available:

- the resource's identification (name and version);
- its source (where it comes from);
- its license and terms of use.

Where Poliglota later assists in obtaining a resource, it should surface this
information when available, rather than asserting a license on the provider's
behalf.

## What Poliglota does not guarantee

The project **does not guarantee** that every model or language package is
free, redistributable, or usable for a given purpose (including commercial
use). Availability, quality, and licensing of translation resources vary
between providers, and some models may be restricted to non-commercial use.

Users are responsible for reviewing the license of any resource they obtain
and for complying with it.

## Redistribution

- Do not redistribute third-party resources as if they were covered by
  Poliglota's MIT License.
- If a third-party resource is ever bundled or referenced, its own license
  text and notices must be preserved and documented separately.
- The MIT text is not modified to impose extra restrictions on third-party
  resources; the separation is achieved by scope, not by changing the license.
