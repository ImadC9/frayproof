"""Resolve an explicitly selected local callable for the mutation CLI."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import importlib.util
import inspect
import sys
from contextlib import contextmanager
from pathlib import Path

from ..errors import InputError
from .runner import run_mutations, run_mutations_async


@contextmanager
def _import_path(path: Path | None):
    previous = sys.path[:]
    if path is not None:
        sys.path.insert(0, str(path))
    try:
        yield
    finally:
        sys.path[:] = previous


def mutate_target(target: str, messages, contract=None):
    """Import path.py:function or package.module:function and execute it once.

    Local target imports and calls execute arbitrary user code. No test command,
    sandboxing or timeout is implied by this convenience interface.
    """
    location, separator, function_name = target.rpartition(":")
    if not separator or not location or not function_name.isidentifier():
        raise InputError("Target must be path.py:function or package.module:function")
    file_target = location.endswith(".py")
    path = Path(location).resolve() if file_target else None
    module_name = "_frayproof_target_" + hashlib.sha256(location.encode()).hexdigest()
    old_module = sys.modules.get(module_name)
    try:
        with _import_path(path.parent if path is not None else None):
            try:
                if file_target:
                    spec = importlib.util.spec_from_file_location(module_name, path)
                    if spec is None or spec.loader is None:
                        raise InputError("Cannot create an import loader for the target file")
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                else:
                    module = importlib.import_module(location)
                function = getattr(module, function_name)
                if not callable(function):
                    raise InputError("Selected target is not callable")
            except InputError:
                raise
            except Exception as exc:
                raise InputError(f"Cannot import target: {type(exc).__name__}: {exc}") from exc
            if inspect.iscoroutinefunction(function):
                return asyncio.run(run_mutations_async(messages, function, contract))
            return run_mutations(messages, function, contract)
    finally:
        if file_target:
            if old_module is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = old_module
