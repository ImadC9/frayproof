# Contract reference

Contracts use safe YAML, version `1`, and format `openai`. Every field is optional
except a pin's `name` and selector. Empty mappings (`{}`) load the defaults; empty
files, duplicate keys, unknown fields, unsupported versions, and incorrect value
types are input errors. YAML merge keys are unsupported: spell out configuration.

```yaml
version: 1
format: openai
checks:
  tool_pairs:
    enabled: true
    severity: error
    allow_trailing_pending_call: false
  unique_tool_ids:
    enabled: true
    severity: error
  structure:
    enabled: true
    severity: error
    system_messages: leading_only
  pinned_content:
    enabled: true
    severity: error
  retention:
    enabled: true
    severity: error
pins:
  - name: system-prompt
    role: system
    match: exact
  - name: production-constraint
    contains: "Never write to production"
    severity: error
retain:
  latest_user_message: exact
  recent_exchanges: 2
  tool_results: complete
```

Each check accepts `true` or `false` as shorthand for its `enabled` field.
Severity is `error` or `warning`. Errors cause failure; warnings are included in
reports but leave `passed` true and the command exit code at `0`. Individual pins
may override `pinned_content` severity.

| Contract key | Report check name | Rule |
| --- | --- | --- |
| `tool_pairs` | `tool_pair_integrity` | Every tool result refers to an earlier assistant call; every call has a result. |
| `unique_tool_ids` | `unique_tool_ids` | Call IDs are globally unique in a snapshot; an ID has at most one result. |
| `structure` | `structure` | Supported roles, instruction placement, nonempty assistant, and tool-result blocks. |
| `pinned_content` | `pinned_content` | Declared messages or literal text present before survive after. |
| `retention` | `retention` | Position-selected turns and retained result content survive according to `retain`. |

## Pending calls

With `allow_trailing_pending_call: true`, unanswered calls are permitted only in
the final assistant call batch, followed by zero or more tool results for that
batch. Partial results and reverse-order results are supported. A user, assistant,
or instruction message after that batch closes the allowance. Old unanswered
calls are still violations.

## Structure

Roles are `system`, `developer`, `user`, `assistant`, and `tool`. Deprecated
`function` messages, OpenAI Responses API item arrays, and custom tool calls
are unsupported in 0.1.0.

`system_messages` applies to both `system` and `developer` instruction roles:

- `leading_only` (default): any number of instruction messages in an initial block.
- `anywhere`: instruction messages may appear throughout the snapshot.
- `forbidden`: instruction messages cause violations anywhere.

Results must form a contiguous block after the assistant that made their calls.
Within a parallel batch, results can arrive in any order. A result later in the
history after intervening user/assistant/instruction messages fails structure,
even if it has an earlier call. Duplicate results are the uniqueness check's job.
Results whose ID is never called anywhere in the snapshot are reported only by
`tool_pair_integrity`; structure still checks missing IDs and invalid content.
If you disable `tool_pairs`, never-called results will therefore not trigger an
ordering violation from structure alone.

An assistant needs nonblank string content, a nonempty content-block list with
content, tool calls, or a refusal. An empty string tool result is valid; null tool
result content is invalid. A call needs a nonblank ID, type `function`, a nonblank
function name, and string arguments. Arguments are retained verbatim, including
incomplete argument JSON. They are not executed or interpreted by the checks.

This is a conversation integrity policy, not a complete OpenAI API request schema.
Content block payloads and unknown provider metadata are retained, not deeply
validated. In particular, multimodal blocks are opaque to structure, except that
blank text-only assistant blocks are considered empty.

Content arrays contain objects. If a block has a `type` discriminator, it must
be a string; arrays, objects, numbers, booleans, and null discriminators are
malformed input (`InputError`, CLI exit `2`). Unknown string types remain opaque.
`tool_calls: null` is accepted as no calls, matching SDK message dumps.

## Pins

A pin chooses exactly one selector: `role` or `contains`. Names must be unique.

Role pins use `match: exact`. Every before message with that role must appear
unchanged after, including tool calls, name, and other metadata. JSON object key
order is ignored; content list order and all values are preserved. Repeated
identical messages require the same number of occurrences after. Reordering is
allowed by the pin itself; structure may still reject the result.

Exact equality uses current neutral fields plus preserved provider metadata,
not a cached original JSON string. `dataclasses.replace()` changes are compared
as actual changes, including when a guard returns a neutral Snapshot.
Known unused optional message fields are normalized: `tool_calls` omitted,
`null`, or `[]` all mean no calls; omitted/null `refusal`, `tool_call_id`, `name`,
`audio`, `annotations`, and `function_call` are equivalent. Omitted and null
`content` are equivalent too, though structure still requires content for user
and tool messages. Non-null values remain protected. Unknown provider metadata
and nested opaque null values retain their exact meaning; they are not discarded.

Text pins use literal, case-sensitive substring matching within a content string
or a text block of type `text`, `input_text`, or `output_text`. They do not search
tool arguments, image URLs, refusal fields, or metadata. The text may move to a
different role. A pin is enforced only when its selector matches something in
before. A text pin protects presence, not occurrence count. No paraphrase or
importance judgment is performed.

Matching happens within **one content part at a time**. Text parts are not joined,
even within the same message. If a compactor splits `Never write to production`
into `Never write ` and `to production` parts, a `contains` pin reports it as lost.
Keep pinned text in a single part for now. Text split across parts in the before
snapshot also does not activate the pin.

Stable policy lines are useful literal pins. Session-specific request and tool
text generally cannot be written into a reusable contract in advance. Exact role
pins can protect every user or tool message dynamically, but that also forbids
removing older messages. Use retention to select the needed portion instead.

## Retention

`retain` resolves against **before**, not the rewritten output. Rules are opt-in;
the defaults are `latest_user_message: null`, `recent_exchanges: 0`, and
`tool_results: null`. Unknown keys/modes and noninteger or negative exchange
counts are input errors; booleans and numeric strings are not counts.

```yaml
pins:
  - name: system-prompt
    role: system
retain:
  latest_user_message: exact
  recent_exchanges: 2
  tool_results: complete
```

`latest_user_message: exact` selects the last user message in before. After must
still have that exact message as its last user message. All source fields,
metadata, multimodal blocks, and content-part order are included, with JSON
object key order and known optional-null differences ignored as above.
Adding an assistant reply is allowed; appending a new
user request fails this rule. Compare the compaction boundary before adding a
new user request. If before has no user, this selector imposes no requirement.

`recent_exchanges: N` keeps the last N **closed** user exchanges. Each starts at
a user message and ends immediately before the next user message, with at least
one assistant or tool message between them. A bare user turn without a response
does not count. The final user turn is open, even if it already has replies;
protect its request with `latest_user_message`. Fewer than N closed exchanges
means all available closed exchanges are protected.

Every message in each selected span must appear verbatim as a contiguous block
in after. This includes calls, arguments, results, replies, and any instruction
messages inside the span. Selected exchanges must retain their relative order.
Summaries or newly generated messages may appear outside those blocks. Blocks
are matched without reusing occurrences, including for identical repeated
exchanges. With both rules enabled, the latest request must follow the protected
blocks; an identical earlier request inside one cannot stand in for it.

`tool_results: complete` compares each after tool result whose `tool_call_id`
appeared in before against the original result content for that ID. Content must
be equal in full: truncation, paraphrasing, added text, changed images, and changed
content parts fail. It compares `content`, not other result metadata. Exact
retention of a recent exchange or a tool role pin also protects that metadata.
Whole older call/result exchanges may disappear. A newly introduced result ID
has no original content to compare. This rule relies on stable call IDs; it does
not infer correspondence after IDs are renamed. Keep `unique_tool_ids` enabled
to avoid ambiguous repeated IDs.

Retention does not infer which older facts matter or prove the origin of
identical JSON messages. With latest-user retention alone, an identical earlier
message that becomes the latest is indistinguishable from the retained original.
Recent-exchange retention prevents reuse among the protected blocks and request;
stable message metadata can distinguish otherwise identical occurrences.

`checks.retention` controls all retention rules and their severity independently
of pins. It accepts boolean shorthand or `{enabled: true, severity: warning}`.
Warning-only retention losses remain mutation survivors. Disable it explicitly
to ignore `retain`; inactive rules add no findings.

`check` validates after and applies pins and retention against before; it does
not validate before. `validate` rejects contracts with enabled pins or active,
enabled retention because it has no before snapshot. Disable the relevant checks
to run only single-snapshot checks from such a contract.

## Input errors and reports

Files contain a JSON array of message objects. UTF-8 and UTF-8 BOM are accepted.
Malformed JSON, duplicate JSON keys, nonfinite numbers, incorrect field types,
and unsupported outer shapes raise `InputError` / exit `2`. Semantically invalid
roles, missing IDs, and misplaced messages become violations / exit `1`.

Every violation includes a `check`, `message`, `severity`, `snapshot`, and
zero-based `message_index`. Structural findings reference `after`; removed pins
reference their original `before` location. Retention of user messages/exchanges
references `before`; changed retained tool content references `after`.
`tool_call_id`, `pin`, and `rule` are optional
details. A removed message can therefore still be located when after is empty.

JSON reports have `schema_version: 1`, `passed`, `errors`, `warnings`, and
`violations`. File/contract input errors in JSON mode emit a separate envelope:
`schema_version` and `error`, with exit `2`. CLI usage errors use the normal
command-line parser diagnostics on stderr. Text reports and successful JSON
reports go to stdout. Text input errors go to stderr.
