from __future__ import annotations

from collections import Counter

from ..contract import Contract
from ..model import Snapshot
from .base import Violation


def pinned_content(before: Snapshot, after: Snapshot, contract: Contract) -> list[Violation]:
    violations = []
    for pin in contract.pins:
        severity = pin.severity or contract.checks.pinned_content.severity
        if pin.role is not None:
            remaining = Counter(m.identity for m in after.messages if m.role == pin.role)
            for index, message in enumerate(before.messages):
                if message.role != pin.role:
                    continue
                if remaining[message.identity] > 0:
                    remaining[message.identity] -= 1
                else:
                    violations.append(
                        Violation(
                            "pinned_content",
                            "Pinned message was removed or changed.",
                            index,
                            severity,
                            snapshot="before",
                            pin=pin.name,
                        )
                    )
        else:
            index = next(
                (
                    i
                    for i, m in enumerate(before.messages)
                    if any(pin.contains in part for part in m.text_parts)
                ),
                None,
            )
            if index is not None and not any(
                pin.contains in part for m in after.messages for part in m.text_parts
            ):
                violations.append(
                    Violation(
                        "pinned_content",
                        "Pinned text no longer appears in message content.",
                        index,
                        severity,
                        snapshot="before",
                        pin=pin.name,
                    )
                )
    return violations
