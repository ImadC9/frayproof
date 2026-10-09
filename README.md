# Frayproof

Check that an AI agent's conversation context still follows your rules after
compaction, retry reconstruction, handoff, or memory hydration.

Frayproof is a standalone Python tool for context contracts you own. Declare
stable pins and positional retention rules, compare before and after, then
measure whether the
contract would catch nine kinds of context corruption. It works on existing
OpenAI-style message lists without adopting an agent framework. No model or API
key is needed by the checker.

The hosted Linux/Windows matrix passes on Python 3.12, 3.13, and 3.14.
Python 3.12 or newer is required.
The distribution, Python import, and command are all named `frayproof`.

## Install

```bash
python -m pip install frayproof
```

From a source checkout or the unpacked source distribution:

```bash
python -m pip install .
```

Or install the prepared wheel:

```bash
python -m pip install dist/frayproof-0.1.0-py3-none-any.whl
```

Installing dependencies may use the network; the installed checker runs offline.

## Find the bugs your contract misses

A passing compactor output does not tell you whether your contract would catch a
bug. `mutate` runs the real compactor once, confirms its output passes, then tests
independent corruptions at every eligible site against the same contract.
It reports each site and collapses identical outputs within an operator.

This compactor keeps the last two closed exchanges: three tool calls and their
results, plus the latest user request. Its weak contract
allows instructions anywhere and has no preservation pins:

```bash
frayproof mutate --target examples/mutation_compactor.py:compact --input fixtures/mutation_session.json --contract examples/weak_contract.yaml
```

<!-- demo:mutation-weak -->
```text
BASELINE PASS: real transformation satisfies the contract.
MUTATION SCORE: 12/20 caught (60.00%); 8 survived, 0 skipped.
CAUGHT drop_tool_call [after[3].tool_calls[0]]: Rejected by tool_pair_integrity.
CAUGHT drop_tool_call [after[6].tool_calls[0]]: Rejected by tool_pair_integrity.
CAUGHT drop_tool_call [after[6].tool_calls[1]]: Rejected by tool_pair_integrity.
CAUGHT drop_tool_result [after[4]]: Rejected by tool_pair_integrity.
CAUGHT drop_tool_result [after[7]]: Rejected by tool_pair_integrity.
CAUGHT drop_tool_result [after[8]]: Rejected by tool_pair_integrity.
CAUGHT duplicate_tool_id [after[3].tool_calls[0]]: Rejected by unique_tool_ids.
CAUGHT duplicate_tool_id [after[6].tool_calls[0]]: Rejected by unique_tool_ids.
CAUGHT duplicate_tool_id [after[6].tool_calls[1]]: Rejected by unique_tool_ids.
SURVIVED remove_pinned_text [after[0]]: Instruction or pinned text loss passed; add or strengthen content pins.
CAUGHT swap_call_result [after[3].tool_calls[0]->after[4]]: Rejected by tool_pair_integrity, structure.
CAUGHT swap_call_result [after[6].tool_calls[0]->after[7]]: Rejected by tool_pair_integrity, structure.
CAUGHT swap_call_result [after[6].tool_calls[1]->after[8]]: Rejected by tool_pair_integrity, structure.
SURVIVED move_instruction [after[0]]: Instruction relocation passed; check the instruction-placement policy.
SURVIVED drop_latest_user [after[9]]: Latest user message loss passed; enable retain.latest_user_message: exact.
SURVIVED truncate_tool_result [after[4]]: Result text truncation passed; enable retain.tool_results: complete.
SURVIVED truncate_tool_result [after[7]]: Result text truncation passed; enable retain.tool_results: complete.
SURVIVED truncate_tool_result [after[8]]: Result text truncation passed; enable retain.tool_results: complete.
SURVIVED drop_recent_exchange [after[2:5]]: Whole exchange loss passed; set retain.recent_exchanges to the required window.
SURVIVED drop_recent_exchange [after[5:9]]: Whole exchange loss passed; set retain.recent_exchanges to the required window.
```

The weak contract catches 12 integrity faults while eight losses or relocations
survive. The default checks also miss latest-user loss, result truncation, and
whole-exchange loss. Protect the latest request, the last two closed exchanges,
and complete retained results with a reusable contract:

```yaml
pins:
  - name: system-prompt
    role: system
retain:
  latest_user_message: exact
  recent_exchanges: 2
  tool_results: complete
```

This is `examples/mutation_contract.yaml`. It selects messages from the original
session and contains no fixture-specific strings. Instructions remain in the
leading block under the default structure policy:

```bash
frayproof mutate --target examples/mutation_compactor.py:compact --input fixtures/mutation_session.json --contract examples/mutation_contract.yaml
```

<!-- demo:mutation-strong -->
```text
BASELINE PASS: real transformation satisfies the contract.
MUTATION SCORE: 20/20 caught (100.00%); 0 survived, 0 skipped.
CAUGHT drop_tool_call [after[3].tool_calls[0]]: Rejected by tool_pair_integrity, retention.
CAUGHT drop_tool_call [after[6].tool_calls[0]]: Rejected by tool_pair_integrity, retention.
CAUGHT drop_tool_call [after[6].tool_calls[1]]: Rejected by tool_pair_integrity, retention.
CAUGHT drop_tool_result [after[4]]: Rejected by tool_pair_integrity, retention.
CAUGHT drop_tool_result [after[7]]: Rejected by tool_pair_integrity, retention.
CAUGHT drop_tool_result [after[8]]: Rejected by tool_pair_integrity, retention.
CAUGHT duplicate_tool_id [after[3].tool_calls[0]]: Rejected by unique_tool_ids, retention.
CAUGHT duplicate_tool_id [after[6].tool_calls[0]]: Rejected by unique_tool_ids, retention.
CAUGHT duplicate_tool_id [after[6].tool_calls[1]]: Rejected by unique_tool_ids, retention.
CAUGHT remove_pinned_text [pin:system-prompt@after[0]]: Rejected by pinned_content.
CAUGHT swap_call_result [after[3].tool_calls[0]->after[4]]: Rejected by tool_pair_integrity, structure, retention.
CAUGHT swap_call_result [after[6].tool_calls[0]->after[7]]: Rejected by tool_pair_integrity, structure, retention.
CAUGHT swap_call_result [after[6].tool_calls[1]->after[8]]: Rejected by tool_pair_integrity, structure, retention.
CAUGHT move_instruction [after[0]]: Rejected by structure.
CAUGHT drop_latest_user [after[9]]: Rejected by retention.
CAUGHT truncate_tool_result [after[4]]: Rejected by retention.
CAUGHT truncate_tool_result [after[7]]: Rejected by retention.
CAUGHT truncate_tool_result [after[8]]: Rejected by retention.
CAUGHT drop_recent_exchange [after[2:5]]: Rejected by retention.
CAUGHT drop_recent_exchange [after[5:9]]: Rejected by retention.
```

The reusable contract catches 20/20 on the same session and mutant sites.
Literal pins for a fixture's requests and results cannot serve as a general
policy written in advance. Retention works with changing session content.
Counts in other sessions depend on eligible sites and pin declarations.
Compare per-operator results and shared sites as well as the aggregate score.
Scores measure this contract on this output, and do not run your own test suite.
**`--target` imports and executes the selected file, including top-level code.**

Scores cover the applicable mutants in this output. Inapplicable operators are
reported as skipped and stay out of the denominator. Warning-only findings count
as survivors. A score of 100% does not prove a compactor correct. See the
[mutation testing guide](docs/MUTATION_TESTING.md) for operators and limits.

## See individual bugs

From the repository root, these commands use the committed fixtures. All output
below was captured from the actual commands and is checked by the test suite.
The fixtures are hand-written reproductions of the described failure patterns,
not transcripts claimed to be collected from production systems.

Validate a clean session:

```bash
frayproof validate --snapshot fixtures/clean_session.json
```

<!-- demo:clean -->
```text
PASS: 0 error(s), 0 warning(s)
```

Remove the assistant tool call and leave its result:

```bash
frayproof validate --snapshot fixtures/orphaned_result.json
```

<!-- demo:orphan -->
```text
FAIL: 1 error(s), 0 warning(s)
ERROR tool_pair_integrity after[2]: Tool result has no earlier assistant tool call. tool_call_id="call_1"
```

The orphan points to `after[2]` and exits `1`. Message indices are zero-based.

A legitimate compaction removes a whole completed exchange, replaces it with a
summary, and keeps the pinned instructions:

```bash
frayproof check --before fixtures/clean_session.json --after fixtures/legitimate_compaction.json --contract examples/contract.yaml
```

<!-- demo:compaction -->
```text
PASS: 0 error(s), 0 warning(s)
```

A retry that rebuilds the system prompt but loses the production constraint fails:

```bash
frayproof check --before fixtures/clean_session.json --after fixtures/dropped_constraint.json --contract examples/contract.yaml
```

<!-- demo:constraint -->
```text
FAIL: 2 error(s), 0 warning(s)
ERROR pinned_content before[0]: Pinned message was removed or changed. pin="system-prompt"
ERROR pinned_content before[0]: Pinned text no longer appears in message content. pin="no-prod-writes"
```

The missing pins refer to their original location in `before`, even though that
content is gone from `after`.

## Declare the contract

This is `examples/contract.yaml`:

```yaml
version: 1
format: openai
checks:
  tool_pairs:
    allow_trailing_pending_call: true
  unique_tool_ids: true
  structure:
    system_messages: leading_only
pins:
  - name: system-prompt
    role: system
    match: exact
  - name: no-prod-writes
    contains: "Never write to production"
```

Without a contract, tool pairing, unique IDs, and structure run with default error
severity; no pins or retention rules are active. Each check can be disabled or set to `warning`.
Warnings are reported but pass. Unanswered calls are rejected by default; the
example contract allows only a final pending batch, including partial results.

Positional retention selects the last user message and the last N closed user
exchanges from before, so requests and result text can change between sessions.
A closed exchange runs from one user message up to the next and has a response;
the final user turn is protected separately. The result rule requires unchanged
content for retained IDs while allowing older exchanges to be dropped.

Role pins keep every matching message unchanged, including metadata and repeated
occurrences. Text pins use a literal substring in content, and apply only if that
text existed before. They can preserve a line while permitting the rest of its
message to change. See the [complete contract rules](docs/CONTRACTS.md).

## Use it in Python

Load and compare the same real fixtures:

```python
from frayproof import check, load_contract, load_snapshot

before = load_snapshot("fixtures/clean_session.json")
after = load_snapshot("fixtures/legitimate_compaction.json")
report = check(before, after, load_contract("examples/contract.yaml"))
assert report.passed
print(report.to_text())
```

`check` validates after and enforces pins and retention against before. `validate`
runs single-snapshot checks. Enabled pins or active retention rules need `check`;
`validate` raises an input error instead of skipping preservation checks.

## Guard a transformation

The offline toy agent has a good compactor and a planted bug. Its decorated
compactor uses the same contract:

```python
from frayproof import guard
from examples.toy_agent import compact


@guard("examples/contract.yaml", on_violation="raise")
def guarded_compact(messages):
    return compact(messages)
```

`guard` supports synchronous and `async def` functions and captures the original
input before in-place edits. It raises `ContractViolation` on error findings;
`warn` and `log` return the transformed output with a warning or log entry.
It does not roll back mutations or side effects. See the [API guide](docs/API.md).

Run the toy agent:

```bash
python examples/toy_agent.py
```

<!-- demo:toy -->
```text
Safe compaction: 6 -> 3 messages
Broken compaction blocked:
FAIL: 1 error(s), 0 warning(s)
ERROR tool_pair_integrity after[2]: Tool result has no earlier assistant tool call. tool_call_id="call_1"
```

## Assert in tests

This exercises the same example compactor using the pytest-compatible helper:

```python
from frayproof import load_snapshot
from frayproof.testing import assert_contract
from examples.toy_agent import compact


def test_compaction():
    before = load_snapshot("fixtures/clean_session.json")
    # The example compactor accepts raw message lists.
    import json
    from pathlib import Path

    messages = json.loads(Path("fixtures/clean_session.json").read_text(encoding="utf-8"))
    assert_contract(before, compact(messages), "examples/contract.yaml")
```

The helper needs no pytest runtime dependency and raises `AssertionError` with
the report on failure.

## Use in CI

```bash
frayproof check --before fixtures/clean_session.json --after fixtures/legitimate_compaction.json --contract examples/contract.yaml --format json
```

`--format json` prints the same findings for machines. Exit `0` means pass,
including warning-only reports; `1` means contract violations; `2` means bad input
or command usage. Reports include a schema version and every finding's check,
severity, plain-English message, snapshot, and message index.

The repository includes a GitHub Actions test/build matrix. It does not publish.
See [contributing](CONTRIBUTING.md) and the [local release handoff](docs/RELEASING.md).

## Scope

0.1.0 supports OpenAI **Chat Completions** message arrays and function tool calls.
It preserves opaque multimodal content and metadata, but does not implement the
entire provider request schema or validate function-argument JSON. Deprecated
function messages, Responses API item arrays, and other provider formats need
future loaders.

SDK-style `tool_calls: null` is accepted. Known unused optional null fields are
equivalent to omitted fields in exact comparisons; opaque custom metadata stays
protected. Neutral replacements are compared using their current fields.
See [review fixes](docs/REVIEW_FIXES.md) and [contract semantics](docs/CONTRACTS.md).

Frayproof does not judge summary quality or infer which facts matter. Declare pins
and retention for what must survive. See [prior art](PRIOR_ART.md) for existing validators and compaction tools.
Obligation tracking, additional provider loaders, framework adapters, and mutation
testing through user test commands are on the [roadmap](docs/ROADMAP.md).

Apache-2.0. See [LICENSE](LICENSE).
