# Good first issue drafts

These are local drafts. No external issue has been created.

## Add an Anthropic message loader

Translate Anthropic user/assistant content blocks into the neutral model without
changing existing checks. Preserve source locations and exact-message identity.
Add clean, orphaned, parallel-call, and multimodal fixtures. Define how the
top-level system field is represented. Document unsupported cases explicitly.

Acceptance: equivalent OpenAI and Anthropic histories produce equivalent findings.

## Add an optional color text renderer

Keep `Report.to_text()` stable for logs and snapshots. Add opt-in CLI color with
TTY detection and `NO_COLOR` support. JSON must stay byte-stable and color-free.

Acceptance: tests cover TTY, redirected output, explicit override, and JSON.

## Expose a contract JSON schema

Generate a schema that describes boolean check shorthand as well as option
objects and pin selectors. Ensure version is integer `1`, and unknown keys are
rejected. Document editor setup for YAML authoring.

Acceptance: schema validation and runtime contract validation agree on fixtures.

## Add a rule for outstanding batches interrupted by a new turn

Today `tool_pairs` reports unanswered calls and `structure` rejects misplaced
results. Add an optional structure rule that points to the new user/assistant
message interrupting a pending batch. Preserve existing default reports until
the new rule is explicitly enabled.

Acceptance: tests include partial parallel results and final pending batches.

## Add user-facing report examples for warning policies

Extend the demo capture to show warning-only exit `0`, pin severity overrides,
and input error JSON. Capture actual command output and test it for drift.

Acceptance: every transcript is generated from committed fixtures.
