# Prior art and name checks

Reviewed 2026-10-09. This is a scoped comparison, not a claim that no equivalent
exists anywhere. Features and registry availability may change.

**Gap:** Existing tools already maintain, repair, or compact conversation histories,
including call/result integrity checks. Frayproof packages deterministic before/after
contracts, explicit content pins, positional retention rules, source-indexed
violations, and an offline CLI
without requiring users to adopt a conversation store or agent framework.
The mutation runner then challenges that user-owned contract with explicit output
faults and explains survivors. Detecting orphaned results alone is not the
novelty; the focus is standalone Python preservation contracts and measurement
of their fault coverage. This comparison does not establish that no other
mutation tool exists.

| Project | Relevant overlap | Frayproof's focus |
| --- | --- | --- |
| [Pydantic AI message history](https://pydantic.dev/docs/ai/core-concepts/message-history/) ([PyPI](https://pypi.org/project/pydantic-ai/)) | Typed histories and deterministic provider-validity repair, including orphaned results and interrupted calls. | Report a contract failure at the transformation boundary rather than repair the history; declare pins over plain OpenAI snapshots. |
| [Conversationalist](https://www.npmjs.com/package/conversationalist) ([source](https://github.com/stevekinney/agent-bureau)) | Immutable TypeScript conversation histories, integrity validation/assertions, pending-call utilities, provider adapters, and compaction. | A standalone Python checker for existing message arrays, with YAML preservation contracts and CLI exit codes. This is the closest directly overlapping validator found. |
| [LangGraph memory](https://docs.langchain.com/oss/python/langgraph/add-memory) | Trimming, deleting, summarizing, and persisting messages; documents provider ordering requirements. | Check arbitrary transformations independently of the graph runtime and storage model. |
| [@tanstack/ai-compaction](https://www.npmjs.com/package/@tanstack/ai-compaction) | Compaction middleware and pluggable strategies for model context. | Validate a compactor's result and declared preserved content rather than implement compaction. |
| [@context-chef/core](https://www.npmjs.com/package/@context-chef/core) | Context compilation, pruning, and compaction planning that keeps call/result turns atomic. | Detect broken outputs from an existing context pipeline without replacing that pipeline. |
| [grok-build compaction utilities](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-chat-state/src/compaction_utils.rs) | Rust validation/sanitization of results lacking preceding calls, plus history repair. | Combine this type of rule with uniqueness, configurable structure, and before/after pins in a separate tool. |
| [Microsoft Agent Framework compaction design](https://github.com/microsoft/agent-framework/blob/main/docs/decisions/0019-python-context-compaction-strategy.md) | Explicit conversation ordering and tool-pair correctness requirements around framework compaction. | Expose these requirements as executable, user-owned contracts across frameworks. |

## Search method and limits

Searched GitHub-indexed code and repositories for context compaction and tool-call
integrity, PyPI for related Python agent/history tooling, and npm for conversation
validators and compactors. Read primary project documentation and source. The
unauthenticated GitHub REST **code** search returned `401`; web-indexed GitHub
source search was used instead. Repository search succeeded. No private code or
credentials were used.

## Final release name

- [PyPI JSON for `frayproof`](https://pypi.org/pypi/frayproof/json): HTTP `404`.
- [npm registry search](https://registry.npmjs.org/-/v1/search?text=frayproof&size=5): zero results.
- [GitHub repository search](https://github.com/search?q=frayproof&type=repositories):
  zero matches.

The distribution, import, CLI, and proposed repository basename are `frayproof`.
These checks do not reserve names or establish trademark availability. Recheck
the package name immediately before publication; a GitHub repository name is
scoped to the chosen owner's account.
