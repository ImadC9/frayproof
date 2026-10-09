"""Guard synchronous and asynchronous transformations, including in-place mutation."""

from __future__ import annotations

import inspect
import logging
import warnings
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Literal

from .contract import Contract, resolve_contract
from .engine import check
from .errors import ContractViolation, ContractWarning
from .loaders.openai import load_snapshot
from .report import Report


def guard(
    contract: Contract | str | Path | None = None,
    *,
    on_violation: Literal["raise", "warn", "log"] = "raise",
) -> Callable:
    """Decorate a function whose first parameter is messages and whose return is messages.

    Load the contract once at decoration time and capture the input before calling the
    transformation. Warning-severity findings alone do not trigger on_violation.
    """
    if on_violation not in {"raise", "warn", "log"}:
        raise ValueError("on_violation must be 'raise', 'warn', or 'log'")
    resolved = resolve_contract(contract)

    def handle(report: Report) -> None:
        if report.passed:
            return
        if on_violation == "raise":
            raise ContractViolation(report)
        if on_violation == "warn":
            warnings.warn(report.to_text(), ContractWarning, stacklevel=3)
        else:
            logging.getLogger("frayproof").error(report.to_text())

    def decorate(function: Callable) -> Callable:
        signature = inspect.signature(function)
        parameters = list(signature.parameters)
        if not parameters:
            raise TypeError("Guarded function must accept messages as its first parameter")

        def baseline(args, kwargs):
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            return load_snapshot(bound.arguments[parameters[0]])

        if inspect.iscoroutinefunction(function):

            @wraps(function)
            async def async_wrapper(*args, **kwargs):
                before = baseline(args, kwargs)
                after = await function(*args, **kwargs)
                handle(check(before, after, resolved))
                return after

            return async_wrapper

        @wraps(function)
        def wrapper(*args, **kwargs):
            before = baseline(args, kwargs)
            after = function(*args, **kwargs)
            handle(check(before, after, resolved))
            return after

        return wrapper

    return decorate
