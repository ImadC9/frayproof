# Roadmap

## 0.1.0: first release

The five checks, OpenAI Chat Completions loader, YAML contracts, CLI, Python API,
runtime guard, pytest assertion, mutation testing, offline examples, and packaging.
All publishing is manual and requires the maintainer's explicit instruction.

## First-release headline: mutation testing

`frayproof mutate` measures the contract against nine output fault classes at
every eligible site, checks the real baseline first, and explains survivors and
skips. The offline demo measures a weak contract at 12/20 and a stronger one at
20/20. This takes priority over adapters and additional loaders. See
[mutation testing](MUTATION_TESTING.md).

Site enumeration and user-message, result-text, and whole-exchange losses are
implemented. Position-based retention now protects these losses without
fixture-specific strings. Next add a user test-command mode with clear
isolation and timeout semantics. The current score measures contracts, not user
test suites.

## 0.2 and beyond

- Anthropic loader translating into the existing neutral model.
- Thin LangGraph adapter around `guard`.
- Obligation tracking using contract-declared markers or structured state.
- OpenTelemetry GenAI trace ingestion.
- SARIF output and a reusable GitHub Action.
- More framework adapters, including the OpenAI Agents SDK.

Any semantic LLM judge belongs in a separate optional layer. Core checks must
remain deterministic and usable offline.
