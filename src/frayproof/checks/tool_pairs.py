from __future__ import annotations

from ..contract import Contract
from ..model import Snapshot
from .base import Violation


def tool_pair_integrity(after: Snapshot, contract: Contract) -> list[Violation]:
    options = contract.checks.tool_pairs
    calls: list[tuple[str, int]] = []
    seen: set[str] = set()
    answered: set[str] = set()
    violations = []
    # A pending batch is allowed only at the tail: final assistant plus any partial results.
    tail_index = next(
        (i for i in range(len(after.messages) - 1, -1, -1) if after.messages[i].role != "tool"),
        -1,
    )
    for index, message in enumerate(after.messages):
        if message.role == "assistant":
            for call in message.tool_calls:
                if call.id:
                    calls.append((call.id, index))
                    seen.add(call.id)
        if message.role == "tool" and message.tool_call_id:
            if message.tool_call_id not in seen:
                violations.append(
                    Violation(
                        "tool_pair_integrity",
                        "Tool result has no earlier assistant tool call.",
                        index,
                        options.severity,
                        tool_call_id=message.tool_call_id,
                    )
                )
            else:
                answered.add(message.tool_call_id)
    for call_id, index in calls:
        if call_id in answered or (options.allow_trailing_pending_call and index == tail_index):
            continue
        violations.append(
            Violation(
                "tool_pair_integrity",
                "Tool call has no result.",
                index,
                options.severity,
                tool_call_id=call_id,
            )
        )
    return violations
