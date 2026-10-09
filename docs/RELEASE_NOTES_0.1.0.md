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

Validation: 297 tests pass on Linux and Windows with Python 3.12, 3.13, and 3.14;
packaging, fresh-install checks, and a byte-identical local source rebuild pass.
Review regressions cover exact preservation, SDK null fields, malformed content,
literal-loss mutants, and original mutation target input fields.

The mutation score measures declared contracts, not your test suite or every
possible compactor bug. `--target` imports and executes the selected code.

[README and demos](https://github.com/ImadC9/frayproof#readme) ·
[Contracts](https://github.com/ImadC9/frayproof/blob/main/docs/CONTRACTS.md) ·
[Changelog](https://github.com/ImadC9/frayproof/blob/main/CHANGELOG.md)
