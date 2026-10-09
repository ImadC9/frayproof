# Python API

Public imports are available from `frayproof`:

For mutation coverage, import `run_mutations`, `run_mutations_async`, and
`MutationReport` from `frayproof.mutate`. See [mutation testing](MUTATION_TESTING.md)
for operators, scoring, CLI, and runtime behavior.

`MutationReport.operators` gives per-operator caught/survived/skipped counts.
Each mutant's `sites` identifies all candidate locations represented by that
corruption; identical outputs within an operator share one result. The aggregate
score counts corruptions, rather than site labels. This evaluates the contract;
it does not invoke a user test suite.

| Symbol | Behavior |
| --- | --- |
| `load_snapshot(source)` | Convert a message list or JSON file path to a neutral `Snapshot`. |
| `load_contract(path)` | Load and strictly validate a YAML contract. |
| `Contract()` | Default policy: all checks on, no pins or active retention, no pending calls. |
| `validate(messages, contract=None)` | Run single-snapshot checks; enabled pins/retention require `check`. |
| `check(before_messages, after_messages, contract=None)` | Validate after and enforce pins and retention. |
| `guard(contract=None, on_violation="raise")` | Decorate a message transformation. |
| `Report` | Immutable findings, pass/fail, and text/JSON serialization. |
| `InputError` | Invalid snapshot or contract; a subclass of `ValueError`. |
| `ContractViolation` | A guard blocked an invalid transformation; `.report` holds findings. |
| `ContractWarning` | Warning category for `on_violation="warn"`. |

`validate` and `check` accept OpenAI message lists, a `Snapshot`, or file paths
(`str` / `pathlib.Path`). Their contract argument accepts a `Contract`, YAML path,
or `None`. Lists are copied, not mutated. Runtime needs no pytest installation.

`Report.violations` is a tuple of `Violation` values. `Report.passed` is true when
there are no error-severity violations; `errors` and `warnings` are counts.
`to_text()`, `to_json()`, and `to_dict()` expose the same findings. Report ordering
is deterministic: tool pairs, unique IDs, structure, pins in contract order, then
retention of latest user, recent exchanges, and tool results. Retention findings
have a `rule` detail. `contract.retain` exposes the positional rules; see
[retention semantics](CONTRACTS.md#retention) for boundaries and exact matching.
Snapshots are detached from input objects. Treat neutral values as read-only.

Neutral `Message.identity` is a computed property of current fields and opaque
`metadata`, including call/function metadata. It is not a constructor argument
or a reusable cache. Build changed values with `dataclasses.replace()`; loading a
neutral Snapshot validates and detaches its current values. Known optional null
fields are normalized for equality as described in the contract reference.

## Runtime guard

The guarded function's first declared parameter must hold messages. It can take
additional positional and keyword arguments; messages may be passed by keyword.
The function must return a message list or neutral snapshot. Use a small wrapper
for methods whose first parameter is `self`, generators, streaming APIs, or
framework functions returning compound objects.

The guard captures the input before the function runs, then checks the return
value. It supports ordinary `async def` functions and awaits them before checking.
In-place modifications cannot erase the captured baseline. A YAML path is loaded
once at decoration time, not on every call.

`on_violation` controls **error-severity** findings:

- `raise`: raise `ContractViolation` with the report.
- `warn`: issue `ContractWarning` and return the output.
- `log`: log at ERROR to the `frayproof` logger and return the output.

Warning-only reports do not trigger these actions. To inspect warning-only
findings, call `check` directly. Invalid input always raises `InputError`.
Exceptions from the wrapped function propagate. The guard runs after the
transformation and does not roll back in-place changes or other side effects.

## pytest helper

Import `assert_contract` from `frayproof.testing`. It accepts the same three
arguments as `check`, returns `None` on pass, and raises `AssertionError` containing
the report on failure. Warning-only findings pass the assertion.
