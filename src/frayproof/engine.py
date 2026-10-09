from __future__ import annotations

from pathlib import Path

from .checks.pins import pinned_content
from .checks.retention import retention
from .checks.structure import structure
from .checks.tool_pairs import tool_pair_integrity
from .checks.unique_ids import unique_tool_ids
from .contract import Contract, resolve_contract
from .errors import InputError
from .loaders.openai import SnapshotInput, load_snapshot
from .report import Report


def _run(before, after, contract: Contract) -> Report:
    violations = []
    for options, check_fn in (
        (contract.checks.tool_pairs, tool_pair_integrity),
        (contract.checks.unique_tool_ids, unique_tool_ids),
        (contract.checks.structure, structure),
    ):
        if options.enabled:
            violations.extend(check_fn(after, contract))
    if before is not None and contract.checks.pinned_content.enabled:
        violations.extend(pinned_content(before, after, contract))
    if before is not None and contract.checks.retention.enabled:
        violations.extend(retention(before, after, contract))
    return Report(tuple(violations))


def validate(
    messages: SnapshotInput,
    contract: Contract | str | Path | None = None,
) -> Report:
    """Check one snapshot. Enabled pins and retention rules require check()."""
    resolved = resolve_contract(contract)
    if resolved.pins and resolved.checks.pinned_content.enabled:
        raise InputError("Pinned content needs a before snapshot; use check instead of validate")
    if resolved.retain.active and resolved.checks.retention.enabled:
        raise InputError("Retention needs a before snapshot; use check instead of validate")
    return _run(None, load_snapshot(messages), resolved)


def check(
    before_messages: SnapshotInput,
    after_messages: SnapshotInput,
    contract: Contract | str | Path | None = None,
) -> Report:
    """Validate after and enforce pins and retention against before. Does not validate before."""
    resolved = resolve_contract(contract)
    return _run(load_snapshot(before_messages), load_snapshot(after_messages), resolved)
