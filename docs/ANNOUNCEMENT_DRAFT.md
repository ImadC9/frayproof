# Local announcement draft — unpublished

## Frayproof: find the bugs your context contract misses

Your compactor's output passes its checks. Would those checks notice if it lost
an instruction, split a tool exchange, or reused a call ID?

Frayproof is a standalone Python tool for conversation contracts you own. It
checks before/after message lists, protects stable pins and positional retention,
and then challenges your contract with nine deterministic fault operators at every
eligible site in the real output.

The included demo retains three tool calls and two exchanges. A weak contract
catches **12 of 20** corruptions, but misses lost instructions, latest-user loss,
truncated results, lost exchanges, and relocated system messages. Retain the
latest user message, the last two closed exchanges verbatim, and complete
retained tool results: the reusable contract catches **20 of 20** on the same
sites. It protects requests and results without knowing their text in advance.
The report identifies every site and supplies per-operator counts; overlapping
pins that produce identical corruptions count once.

No LLM judge or API key is needed by the checker. Use the command line, call it
from Python, guard a transformation, or assert a contract in tests. Applicable
mutants, skips, and violations are explained in text or JSON.

The score measures the contract, not your own test suite. It covers applicable
faults in that output; it is not proof that the compactor is correct. The useful result is knowing which declared protections
still let a plausible context bug through.

Frayproof 0.1.0 supports OpenAI Chat Completions message arrays and ships under
Apache-2.0. The demo and mutation testing guide are included with the source.
