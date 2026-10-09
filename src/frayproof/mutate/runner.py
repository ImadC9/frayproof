"""Measure declared contracts against corrupted copies of one real transformation output."""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..contract import Contract, resolve_contract
from ..engine import check
from ..errors import InputError
from ..loaders import load_snapshot
from ..loaders.openai import _read_data
from ..model import Snapshot
from ..report import Report
from .mutators import Messages, generate_mutations


@dataclass(frozen=True)
class MutantResult:
    name: str
    description: str
    status: Literal["caught", "survived", "skipped"]
    message_index: int | None
    reason: str
    report: Report | None = None
    sites: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "message_index": self.message_index,
            "sites": list(self.sites),
            "reason": self.reason,
            "report": self.report.to_dict() if self.report is not None else None,
        }


@dataclass(frozen=True)
class MutationReport:
    baseline: Report
    mutants: tuple[MutantResult, ...] = ()

    @property
    def caught(self) -> int:
        return sum(m.status == "caught" for m in self.mutants)

    @property
    def survived(self) -> int:
        return sum(m.status == "survived" for m in self.mutants)

    @property
    def skipped(self) -> int:
        return sum(m.status == "skipped" for m in self.mutants)

    @property
    def applicable(self) -> int:
        return self.caught + self.survived

    @property
    def score(self) -> float | None:
        return round(100 * self.caught / self.applicable, 2) if self.applicable else None

    @property
    def passed(self) -> bool:
        return self.baseline.passed and self.applicable > 0 and self.survived == 0

    def to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "kind": "mutation",
            "passed": self.passed,
            "baseline": self.baseline.to_dict(),
            "caught": self.caught,
            "survived": self.survived,
            "skipped": self.skipped,
            "applicable": self.applicable,
            "score_percent": self.score,
            "operators": self.operators,
            "mutants": [m.to_dict() for m in self.mutants],
        }

    @property
    def operators(self) -> dict:
        """Per-operator counts keep structural catches from hiding retention gaps."""
        groups = {}
        for mutant in self.mutants:
            counts = groups.setdefault(mutant.name, {"caught": 0, "survived": 0, "skipped": 0})
            counts[mutant.status] += 1
        return groups

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)

    def to_text(self) -> str:
        if not self.baseline.passed:
            return "BASELINE FAIL: real transformation violates the contract; no mutants run.\n" + (
                self.baseline.to_text()
            )
        score = f"{self.score:.2f}%" if self.score is not None else "not measured"
        lines = [
            "BASELINE PASS: real transformation satisfies the contract.",
            f"MUTATION SCORE: {self.caught}/{self.applicable} caught ({score}); "
            f"{self.survived} survived, {self.skipped} skipped.",
        ]
        if not self.applicable:
            lines.append("No applicable mutants; no contract coverage was measured.")
        for mutant in self.mutants:
            sites = f" [{', '.join(mutant.sites)}]" if mutant.sites else ""
            lines.append(f"{mutant.status.upper()} {mutant.name}{sites}: {mutant.reason}")
        return "\n".join(lines)


_SURVIVORS = {
    "drop_tool_call": "Removing a call while retaining its result passed; check orphan protection.",
    "drop_tool_result": "Removing a result passed; check pairing and trailing-pending policy.",
    "duplicate_tool_id": "A repeated call ID passed; check unique_tool_ids protection.",
    "remove_pinned_text": "Instruction or pinned text loss passed; add or strengthen content pins.",
    "swap_call_result": "A result before its call passed; check pairing and structure protection.",
    "move_instruction": "Instruction relocation passed; check the instruction-placement policy.",
    "drop_latest_user": (
        "Latest user message loss passed; enable retain.latest_user_message: exact."
    ),
    "truncate_tool_result": (
        "Result text truncation passed; enable retain.tool_results: complete."
    ),
    "drop_recent_exchange": (
        "Whole exchange loss passed; set retain.recent_exchanges to the required window."
    ),
}


def _prepare(messages: Messages | str | Path, contract: Contract | str | Path | None):
    if isinstance(messages, Snapshot):
        raise InputError("Mutation inputs must be OpenAI message lists or JSON file paths")
    resolved = resolve_contract(contract)
    raw = _read_data(messages)
    before = load_snapshot(raw)
    return before, raw, resolved


def _evaluate(before: Snapshot, output: Messages, contract: Contract) -> MutationReport:
    if not isinstance(output, list):
        raise InputError("Mutation target must return an OpenAI message list")
    after = load_snapshot(output)
    baseline = check(before, after, contract)
    if not baseline.passed:
        return MutationReport(baseline)
    messages = deepcopy(output)
    results = []
    for mutation in generate_mutations(messages, before, after, contract):
        if mutation.messages is None:
            results.append(
                MutantResult(
                    mutation.name, mutation.description, "skipped", None, mutation.skip_reason
                )
            )
            continue
        report = check(before, mutation.messages, contract)
        status = "survived" if report.passed else "caught"
        reason = (
            _SURVIVORS[mutation.name]
            if report.passed
            else "Rejected by "
            + ", ".join(dict.fromkeys(v.check for v in report.violations if v.severity == "error"))
            + "."
        )
        results.append(
            MutantResult(
                mutation.name,
                mutation.description,
                status,
                mutation.message_index,
                reason,
                report,
                mutation.sites,
            )
        )
    return MutationReport(baseline, tuple(results))


def run_mutations(
    messages: Messages | str | Path,
    transformation: Callable,
    contract: Contract | str | Path | None = None,
) -> MutationReport:
    """Run a sync transformation once, then check independent corruptions at eligible sites."""
    before, raw, resolved = _prepare(messages, contract)
    try:
        output = transformation(deepcopy(raw))
    except Exception as exc:
        raise InputError(f"Transformation failed: {type(exc).__name__}: {exc}") from exc
    if inspect.isawaitable(output):
        if inspect.iscoroutine(output):
            output.close()
        raise InputError("Async targets require await run_mutations_async(...)")
    return _evaluate(before, output, resolved)


async def run_mutations_async(
    messages: Messages | str | Path,
    transformation: Callable,
    contract: Contract | str | Path | None = None,
) -> MutationReport:
    """Await one async transformation and evaluate the same deterministic fault operators."""
    before, raw, resolved = _prepare(messages, contract)
    try:
        output = transformation(deepcopy(raw))
        if inspect.isawaitable(output):
            output = await output
    except Exception as exc:
        raise InputError(f"Transformation failed: {type(exc).__name__}: {exc}") from exc
    return _evaluate(before, output, resolved)
