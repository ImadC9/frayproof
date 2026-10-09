# Release review fixes

The reported F1–F3 defects and SDK-null compatibility issues are covered by
`tests/test_review_regressions.py`. Six targeted regression cases fail against
the previous installed wheel: three exact-preservation policies, two malformed
block types, and the newly joined literal case. They pass with the fixes.

- F1: identity is computed from current fields. Provider metadata remains
  separate at message, call, and function levels. Snapshot loading validates and
  detaches those actual values; sync/async guards reject protected replacements.
- F2: nonstring content discriminators raise `InputError`. JSON CLI output uses
  the error envelope and exit 2. Text helpers also safely ignore malformed blocks
  when called directly before loading.
- F3: text deletion repeats until no selected literal remains. Property tests
  cover overlapping and newly joined matches as well as content-part copies.
- SDK nulls: `tool_calls: null` means no calls. Known optional message fields
  normalize null/omission for exact pins and retention. Opaque custom null values
  remain protected; stripping arbitrary metadata would weaken exact checks.

Run `python examples/verify_review_fixes.py` with an installed wheel. It checks
the three reported defects, CLI behavior, SDK null input, and null equality.
The release verification runs it outside the checkout on Python 3.12 and 3.13.

The follow-up mutation-input regression is covered by
`tests/test_mutation_wire_input.py`: sync/async transformations receive original
fields, including `tool_calls: []` or null, and explicit optional fields. Both a
working target that needs those keys and a target that fails only when they are
present are tested. File loading happens once; baseline snapshots and mutants
remain detached. Normalized identity is used for comparisons, not to reconstruct
the target input or the real output. The installed-wheel probe covers both
failure directions too.

The hosted Linux/Windows Python 3.12/3.13/3.14 matrix passed on 2026-10-09 with
297 tests in each combination. Packaging passed too; see the
[private CI run](https://github.com/ImadC9/frayproof/actions/runs/37876640504).
The user authorized private repository setup and CI. Corrected artifacts remain
unpublished release candidates until publication is explicitly authorized.
