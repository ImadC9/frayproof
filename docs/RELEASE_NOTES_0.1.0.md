# Frayproof 0.1.0

Find the bugs your conversation context contract misses. Frayproof validates
before/after OpenAI-style message lists, then challenges the contract with nine
deterministic mutation operators at every eligible site.

The included weak contract catches 12/20 corruptions. A reusable contract with
stable system pins and positional retention catches 20/20 on the same session,
without fixture-specific strings. Protect the latest user message, recent closed
exchanges verbatim, and complete retained tool results.

```bash
python -m pip install frayproof
```

Includes CLI JSON/text reports, a Python API, sync/async runtime guards, and a
pytest helper. Python 3.12+, Apache-2.0. No model or API key is needed by the checker.

The mutation score measures declared contracts, not your test suite or every
possible compactor bug. `--target` imports and executes the selected code.

[README and demos](https://github.com/ImadC9/frayproof#readme) ·
[Contracts](https://github.com/ImadC9/frayproof/blob/main/docs/CONTRACTS.md) ·
[Changelog](https://github.com/ImadC9/frayproof/blob/main/CHANGELOG.md)

## Regression coverage

The release regression tests preserve these guarantees:

- **Exact identity:** identity is computed from current neutral fields, with
  opaque provider metadata preserved separately at message, call, and function
  levels. Snapshot loading validates and detaches those values; synchronous and
  asynchronous guards reject changes to protected messages.
- **Malformed content:** nonstring content-block discriminators raise
  `InputError`. JSON CLI output uses the input-error envelope and exit `2`;
  text helpers safely ignore malformed blocks when called directly before loading.
- **Literal loss:** text deletion repeats until the selected literal is gone.
  Property tests cover overlapping matches, matches newly joined by deletion,
  and copies in separate content parts.
- **SDK nulls:** `tool_calls: null` means no calls. Known optional message fields
  normalize null/omission for exact pins and retention, while opaque custom null
  values remain protected.
- **Mutation input:** synchronous and asynchronous targets receive original wire
  fields, including explicit optional fields and empty/null `tool_calls`.
  File input is loaded once; baseline snapshots and mutants remain detached.
  Normalized comparison identity does not reconstruct or replace target input
  or real output. Tests cover a working target needing those fields and a target
  failing only when they are present.

See [review regressions](../tests/test_review_regressions.py),
[mutation-input regressions](../tests/test_mutation_wire_input.py), and
[property tests](../tests/test_properties.py).
Six targeted regression cases failed against the previous installed wheel and
passed with these fixes: three exact-preservation policies, two malformed block
types, and the newly joined literal case.

Run [the installed-wheel probe](../examples/verify_review_fixes.py) from outside
the checkout. It checks the reported defects, CLI behavior, SDK null input/null
equality, and both mutation-input failure directions. Release verification
exercises the probe on Python 3.12 and 3.13.

## Initial validation record

The [initial CI run on 2026-10-09](https://github.com/ImadC9/frayproof/actions/runs/37876640504)
passed the Linux/Windows matrix on Python 3.12, 3.13, and 3.14, with 297 tests
per combination and packaging passing, at commit
`1538e17d4e4b872b3081e49bd916aad846cd0300`.
The release review also recorded fresh-install checks and a byte-identical
local source rebuild.

This is historical release-candidate evidence. Later revisions require a fresh
complete CI gate for the exact revision being published, following the
[release guide](RELEASING.md).
