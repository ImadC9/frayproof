# Measure the contract

Passing output obeys the declared rules. Mutation testing asks whether those rules
reject specific plausible faults in that output. The committed example catches
12/20 faults with `examples/weak_contract.yaml` and 20/20 with
`examples/mutation_contract.yaml`.
These are measured examples, not coverage of every possible compactor bug.

```bash
frayproof mutate --target examples/mutation_compactor.py:compact --input fixtures/mutation_session.json --contract examples/weak_contract.yaml
```

## What runs

The runner detaches the input, executes the transformation **once** on a private
copy, then checks the real output against the original input. If that baseline
fails, it reports the findings and runs no mutants. Otherwise each operator
corrupts an independent copy of the real output and checks it against the same
original input and contract. Neither caller input nor real output is changed.

The transformation receives a detached copy of the original wire data, preserving
every key, explicit null, empty array, and nested metadata value. Files are read
once with duplicate-key validation. Comparison normalization is applied only to
the neutral snapshots used by checks; it never changes what the target receives.
Mutants likewise start from the real output fields, not a reconstruction of the
normalized comparison identity. Target failures are reported as input errors;
normalization cannot hide a failure that occurs with the actual input.

Operators and reports are deterministic given the same input, output, and
contract. The user-supplied transformation may itself use external services or
be nondeterministic; the checker itself makes no model or network calls.

## Nine fault operators, every eligible site

| Operator | Fault | Required output |
| --- | --- | --- |
| `drop_tool_call` | Remove one answered call, keeping its result. Remove an otherwise empty assistant too, so an empty-assistant defect cannot mask weak orphan protection. | An answered assistant call whose ID is not reused. |
| `drop_tool_result` | Remove one matching result, keeping its call. | A matching result whose ID has only one result. |
| `duplicate_tool_id` | Copy a call with the same ID into its assistant batch. | An assistant call with an ID. |
| `remove_pinned_text` | Remove each activated contains pin's text everywhere; for a role pin, change each preserved textual message separately. Without a textual candidate, remove one nonblank line per instruction message. | Activated textual pin content or instruction text. |
| `swap_call_result` | Swap a call message with its matching later result. | An ordered call/result pair. |
| `move_instruction` | Move an instruction message to the end. | An instruction before a conversation message. |
| `drop_latest_user` | Remove the latest user message, leaving other messages unchanged. | A user message. |
| `truncate_tool_result` | Keep each result's ID and metadata but retain only the first half of each supported text part, at least one character. | A result with a text part of at least two characters. |
| `drop_recent_exchange` | Remove each closed user exchange, including its call/result batches, while preserving instruction messages. | A user turn followed by an assistant/tool message before the next user turn. |

Operators enumerate every eligible call, result, instruction, pin, and closed
exchange in stable message order. Pin selection follows contract order. A
contains pin produces one loss case per activated selector, removing every copy
of its literal text; removing just one copy would legitimately satisfy that pin.
Deletion repeats until the literal is absent, including matches created by
joining the remaining characters. For example, removing `aba` once from `aababa`
would leave `aba`; the finished mutant removes that new match too.
An exact role pin produces a content-change case for each preserved textual
message. Pins absent from before are ignored. Disabled pins remain candidates.
Nontextual role pins have no text-removal candidate; other operators can still
challenge their preservation.

Identical corrupted outputs within an operator count once. Their `sites` are
combined, so overlapping pins cannot inflate the score. Different operators
remain separate fault hypotheses even if they happen to produce the same output.
Locations refer to the real output; a call site includes its position in a
parallel batch. JSON includes per-operator caught/survived/skipped counts.

Latest-user loss has exactly one site. An exchange spans a user message up to
the next user message, and is closed only when that span contains assistant or
tool activity. Every closed exchange in the retained output is challenged, even
if it is older than the newest one; the last user turn is excluded from this
operator. Losing an older exchange may be intentional. Use retention or pins
for the ones your policy requires. The operator does not infer age, importance, or a retention window.

The three loss operators preserve valid structure in ordinary valid sessions
and survive the default checks. Reusable `retain` rules protect the latest user
message, a window of closed exchanges selected from before, and full content for
retained result IDs. Stable literal pins are useful for policy lines; pinning
fixture-specific request/result text is not a practical general policy. Exact
role pins can protect all user/tool messages but also forbid older compaction.
See [retention semantics](CONTRACTS.md#retention). A deliberate loss outside the
retained window may survive; that is a policy choice, not proof of a missing rule.

Without pins, the instruction-loss operator still challenges instruction
preservation. It does not infer importance; its explicit fault assumption is
that losing that instruction should be tested. Survivors may reflect deliberate
policy, such as allowing instruction messages anywhere or permitting a final
pending call. Reports describe the gap for the user to assess.

An inapplicable operator has one explicit skip entry. Skips are
excluded from the denominator. Score is `caught / applicable`
as a percentage. Zero applicable mutants means a null score and a non-passing
result, never 100%. Warning-only findings count as survivors because the contract
still passes. A score of 100% covers the applicable mutants in this one output.

The demo retains three calls/results, two closed exchanges, and a latest request.
Its weak contract catches all 12 integrity faults but misses eight retention or
placement faults. The reusable stronger contract uses a system role pin and
three positional retention rules, catching 20/20 on the same sites. It contains
no fixture-specific strings. Literal pins for these changing requests/results
would cover this fixture, but would not be a practical reusable contract.
Counts depend on eligible sites and declared pins. Compare operators and sites
as well as the aggregate score; the percentage is not a weighted measure of all real-world bugs. Each mutant
copies the output, so large sessions can consume substantial memory and time.

A mutant's top-level `message_index` refers to the affected location in the real
output. Nested violations refer to the corrupted output, or the original before
snapshot for pin loss, just like ordinary reports.

## CLI and API

**`--target` imports and runs the given file or module, including its top-level
code. Use targets you trust.** It accepts `path.py:function` or
`package.module:function`. The callable
takes an OpenAI message list and returns one. The CLI awaits ordinary `async def`
targets. File targets support sibling imports; use dotted module targets for
packages with relative imports. The CLI imports and executes the selected local
code; it provides no sandbox, rollback, or timeout for the target's side effects.

`--format json` emits a versioned report containing baseline findings, mutant
status and explanation, nested violations, counts, and percentage.

- Exit `0`: baseline passes, at least one mutant applies, and all applicable mutants are caught.
- Exit `1`: survivors, failing baseline, or no applicable mutants.
- Exit `2`: invalid inputs/target, import/runtime failure, or malformed output.

Python callers import `run_mutations`, `run_mutations_async`, and `MutationReport`
from `frayproof.mutate`. Arguments are an OpenAI message list or JSON file path,
a callable, and an optional contract object or YAML path. Await the async variant
inside an event loop; it also accepts sync callables. The sync variant rejects
returned awaitables rather than forgetting to await them. Neutral Snapshot
inputs/outputs are unsupported because these first mutators operate on OpenAI
wire-format messages.

This measures the contract against nine output fault classes; it does not mutate
implementation code, prove a compactor correct, or run a user test suite. `--test-cmd`
and other providers remain future work.
