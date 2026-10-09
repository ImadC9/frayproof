# Contributing

Use Python 3.12 or newer. From the repository root:

```bash
python -m venv .venv
```

Activate `.venv` using your platform's standard activation script, then:

```bash
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m pytest --cov=frayproof --cov-report=term-missing
python -m build
python -m twine check --strict dist/*
```

For a bug report, include minimal redacted before/after snapshots, the contract, the
expected result, and the actual report. A report's message indices are zero-based.
Never include API keys, private tool outputs, or unredacted user conversations.

Add a regression test for behavior changes. Keep checks deterministic and free of
provider SDK dependencies. Provider loaders translate to the neutral model; checks
must not inspect a provider-specific raw dictionary. Full message identity is
computed by the neutral model's canonical `identity` property from current
fields and opaque provider metadata. Never cache an identity across transformed
message values or silently discard opaque metadata to compare exact messages.

Do not add an LLM judge to the core checks. A legitimate compaction that removes a
whole completed exchange should keep passing unless a declared pin protects it.

Contributions are licensed under Apache-2.0, the project's license.
