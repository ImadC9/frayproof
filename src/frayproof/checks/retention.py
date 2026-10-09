"""Protect selected original turns and retained tool-result content without literal pins."""

from ..contract import Contract
from ..model import Snapshot, canonical
from ..selection import closed_exchanges
from .base import Violation


def retention(before: Snapshot, after: Snapshot, contract: Contract) -> list[Violation]:
    rules = contract.retain
    severity = contract.checks.retention.severity
    violations = []
    cursor = 0
    exchange_violations = []
    if rules.recent_exchanges:
        spans = closed_exchanges(before)[-rules.recent_exchanges :]
        identities = [m.identity for m in after.messages]
        for start, end in spans:
            expected = [m.identity for m in before.messages[start:end]]
            position = next(
                (
                    i
                    for i in range(cursor, len(identities) - len(expected) + 1)
                    if identities[i : i + len(expected)] == expected
                ),
                None,
            )
            if position is None:
                exchange_violations.append(
                    Violation(
                        "retention",
                        f"Retained exchange before[{start}:{end}] "
                        "was removed, changed, split, or reordered.",
                        start,
                        severity,
                        snapshot="before",
                        rule="recent_exchanges",
                    )
                )
            else:
                cursor = position + len(expected)
    if rules.latest_user_message:
        original = next(
            ((i, m) for i, m in reversed(list(enumerate(before.messages))) if m.role == "user"),
            None,
        )
        latest = next(
            ((i, m) for i, m in reversed(list(enumerate(after.messages))) if m.role == "user"),
            None,
        )
        # Do not reuse a user occurrence already consumed by a protected exchange.
        if original is not None and (
            latest is None or latest[0] < cursor or latest[1].identity != original[1].identity
        ):
            violations.append(
                Violation(
                    "retention",
                    "Latest user message was removed, changed, or replaced as the latest turn.",
                    original[0],
                    severity,
                    snapshot="before",
                    rule="latest_user_message",
                )
            )
    violations.extend(exchange_violations)
    if rules.tool_results:
        originals: dict[str, set[str]] = {}
        for message in before.messages:
            if message.role == "tool" and message.tool_call_id:
                originals.setdefault(message.tool_call_id, set()).add(canonical(message.content))
        for index, message in enumerate(after.messages):
            if (
                message.role == "tool"
                and message.tool_call_id in originals
                and canonical(message.content) not in originals[message.tool_call_id]
            ):
                violations.append(
                    Violation(
                        "retention",
                        "Retained tool result content changed; complete content must be preserved.",
                        index,
                        severity,
                        tool_call_id=message.tool_call_id,
                        rule="tool_results",
                    )
                )
    return violations
