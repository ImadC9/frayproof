"""Deterministic report serialization; no clocks, model calls or snapshot contents."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from .checks.base import Violation


@dataclass(frozen=True)
class Report:
    violations: tuple[Violation, ...] = ()

    @property
    def passed(self) -> bool:
        return not any(v.severity == "error" for v in self.violations)

    @property
    def errors(self) -> int:
        return sum(v.severity == "error" for v in self.violations)

    @property
    def warnings(self) -> int:
        return sum(v.severity == "warning" for v in self.violations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
            "violations": [asdict(v) for v in self.violations],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)

    def to_text(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [f"{status}: {self.errors} error(s), {self.warnings} warning(s)"]
        for v in self.violations:
            detail = ""
            if v.tool_call_id is not None:
                detail += f" tool_call_id={json.dumps(v.tool_call_id, ensure_ascii=False)}"
            if v.pin is not None:
                detail += f" pin={json.dumps(v.pin, ensure_ascii=False)}"
            if v.rule is not None:
                detail += f" rule={json.dumps(v.rule, ensure_ascii=False)}"
            lines.append(
                f"{v.severity.upper()} {v.check} {v.snapshot}[{v.message_index}]: "
                f"{v.message}{detail}"
            )
        return "\n".join(lines)
