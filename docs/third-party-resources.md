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

No translation engine is bundled with this repository, and no model weights or
tokenizer artifacts are shipped by the project itself. This document describes
an explicit separation of concerns: the code in Poliglota is MIT-licensed, while
model assets, vocabularies, checkpoints, and similar external resources remain
user-managed artifacts with their own license terms and provenance.

This document does not list, endorse, or license any specific model or
resource. It is a boundary statement, not a recommendation engine.

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

The project **does not guarantee** that every model or language package is free, redistributable, or usable for a given purpose (including commercial use). Availability, quality, and licensing of translation resources vary between providers, and some models may be restricted to non-commercial use.

**Poliglota does not audit, validate, or enforce third-party model licenses.** The project will not:

- Block you from using a model based on its license
- Automatically scan or verify license compliance
- Warn you about license terms (that is your responsibility)
- Prevent you from selecting or caching any model you choose to use

This is intentional. License compliance is a user responsibility, not an automated guard. When you select a model (free, paid, or custom), you are responsible for:

- Reading and understanding its license terms
- Verifying you have the right to use it for your intended purpose
- Complying with any restrictions (e.g., non-commercial use, attribution, redistribution limits)
- Obtaining the model from an authorized source

Poliglota's role is to load and use models you provide; it is not to police them.

## Redistribution

- Do not redistribute third-party resources as if they were covered by
  Poliglota's MIT License.
- If a third-party resource is ever bundled or referenced, its own license
  text and notices must be preserved and documented separately.
- The MIT text is not modified to impose extra restrictions on third-party
  resources; the separation is achieved by scope, not by changing the license.
