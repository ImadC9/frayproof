"""Public exception types. Input errors are distinct from contract violations."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .report import Report


class InputError(ValueError):
    """A snapshot or contract cannot be decoded into the supported format."""


class ContractViolation(RuntimeError):
    """A guarded transformation violated its contract; inspect ``report``."""

    def __init__(self, report: Report) -> None:
        self.report = report
        super().__init__(report.to_text())


class ContractWarning(UserWarning):
    """Warning emitted by a guard configured with ``on_violation='warn'``."""
