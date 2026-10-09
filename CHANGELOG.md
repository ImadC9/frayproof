# Changelog

## 0.1.0 — 2026-10-09

- Preserve original wire fields when invoking mutation targets and generating
  mutants; comparison normalization cannot hide a real input-dependent failure.

- Fix exact preservation bypasses after replacing neutral fields; compute identity
  from current values while preserving opaque message/call/function metadata.
- Accept SDK-style `tool_calls: null` and normalize known optional null fields.
- Reject malformed content discriminators with `InputError` and JSON CLI exit 2.
- Remove all literal matches in text-loss mutants, including matches newly
  created by deletion, to avoid false survivors.

- Validate OpenAI Chat Completions message snapshots with tool-pair integrity,
  unique tool IDs, and conversation structure checks.
- Compare transformations with exact role pins and literal content pins.
- Retain the latest user request and a window of closed user exchanges exactly,
  and require complete content for retained tool results, without fixture text.
- Expose retention severity/switches and source locations with a rule detail.
- Configure each check's severity and allow pending tool calls only at a trailing batch.
- Emit deterministic text and JSON reports with zero-based source locations.
- Provide `frayproof validate`, `frayproof check`, and a Python API.
- Guard synchronous, asynchronous, and in-place transformations.
- Include a pytest assertion helper, regression fixtures, and an offline toy agent.
- Measure contracts with nine mutation operators at every eligible site, baseline validation, explained
  survivors/skips, site locations, per-operator counts, and sync/async support.
- Challenge latest-user loss, tool-result truncation, and retained exchange loss.
- Count identical corruptions once within an operator, retaining all site labels.
- Report never-called results once, under tool-pair integrity; keep independent
  ordering and content faults in structure.
- Document the content-part boundary limitation of literal text pins.

Obligation tracking, additional providers, and framework adapters
remain on the [roadmap](docs/ROADMAP.md).
