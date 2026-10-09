from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from ..contract import Contract, Severity
from ..model import Snapshot


@dataclass(frozen=True)
class Violation:
    check: str
    message: str
    message_index: int
    severity: Severity = "error"
    snapshot: Literal["before", "after"] = "after"
    tool_call_id: str | None = None
    pin: str | None = None
    rule: str | None = None


class Check(Protocol):
    def __call__(self, after: Snapshot, contract: Contract) -> list[Violation]: ...
