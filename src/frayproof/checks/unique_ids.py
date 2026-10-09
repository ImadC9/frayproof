from __future__ import annotations

from ..contract import Contract
from ..model import Snapshot
from .base import Violation


def unique_tool_ids(after: Snapshot, contract: Contract) -> list[Violation]:
    severity = contract.checks.unique_tool_ids.severity
    calls: set[str] = set()
    results: set[str] = set()
    violations = []
    for index, message in enumerate(after.messages):
        if message.role == "assistant":
            for call in message.tool_calls:
                if not call.id:
                    continue
                if call.id in calls:
                    violations.append(
                        Violation(
                            "unique_tool_ids",
                            "Tool call ID is reused.",
                            index,
                            severity,
                            tool_call_id=call.id,
                        )
                    )
                calls.add(call.id)
        if message.role == "tool" and message.tool_call_id:
            if message.tool_call_id in results:
                violations.append(
                    Violation(
                        "unique_tool_ids",
                        "Tool call has more than one result.",
                        index,
                        severity,
                        tool_call_id=message.tool_call_id,
                    )
                )
            results.add(message.tool_call_id)
    return violations
