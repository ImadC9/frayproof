"""A pytest-compatible assertion without a runtime dependency on pytest."""

from pathlib import Path

from .contract import Contract
from .engine import check
from .loaders.openai import SnapshotInput


def assert_contract(
    before: SnapshotInput,
    after: SnapshotInput,
    contract: Contract | str | Path | None = None,
) -> None:
    report = check(before, after, contract)
    if not report.passed:
        raise AssertionError(report.to_text())
