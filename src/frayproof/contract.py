"""Versioned, strict YAML contracts. Unknown options and duplicate keys are errors."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .errors import InputError

Severity = Literal["error", "warning"]
Role = Literal["system", "developer", "user", "assistant", "tool"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class CheckOptions(StrictModel):
    enabled: bool = True
    severity: Severity = "error"


class ToolPairOptions(CheckOptions):
    allow_trailing_pending_call: bool = False


class StructureOptions(CheckOptions):
    system_messages: Literal["leading_only", "anywhere", "forbidden"] = "leading_only"


class Checks(StrictModel):
    tool_pairs: ToolPairOptions = Field(default_factory=ToolPairOptions)
    unique_tool_ids: CheckOptions = Field(default_factory=CheckOptions)
    structure: StructureOptions = Field(default_factory=StructureOptions)
    pinned_content: CheckOptions = Field(default_factory=CheckOptions)
    retention: CheckOptions = Field(default_factory=CheckOptions)

    @field_validator(
        "tool_pairs", "unique_tool_ids", "structure", "pinned_content", "retention", mode="before"
    )
    @classmethod
    def bool_options(cls, value: Any) -> Any:
        return {"enabled": value} if isinstance(value, bool) else value


class Pin(StrictModel):
    name: str = Field(min_length=1)
    role: Role | None = None
    match: Literal["exact"] = "exact"
    contains: str | None = Field(default=None, min_length=1)
    severity: Severity | None = None

    @model_validator(mode="after")
    def selector(self) -> Self:
        if (self.role is None) == (self.contains is None):
            raise ValueError("A pin must specify exactly one of role or contains")
        return self


class Retention(StrictModel):
    latest_user_message: Literal["exact"] | None = None
    recent_exchanges: int = Field(default=0, ge=0)
    tool_results: Literal["complete"] | None = None

    @property
    def active(self) -> bool:
        return bool(self.latest_user_message or self.recent_exchanges or self.tool_results)


class Contract(StrictModel):
    version: Literal[1] = 1
    format: Literal["openai"] = "openai"
    checks: Checks = Field(default_factory=Checks)
    pins: tuple[Pin, ...] = ()
    retain: Retention = Field(default_factory=Retention)

    @field_validator("version", mode="before")
    @classmethod
    def integer_version(cls, value: Any) -> Any:
        if type(value) is not int:
            raise ValueError("Contract version must be an integer")
        return value

    @field_validator("pins", mode="before")
    @classmethod
    def pin_list(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def unique_pin_names(self) -> Self:
        names = [pin.name for pin in self.pins]
        if len(set(names)) != len(names):
            raise ValueError("Pin names must be unique")
        return self


class _ContractLoader(yaml.SafeLoader):
    pass


def _mapping(loader: _ContractLoader, node: yaml.MappingNode) -> dict[str, Any]:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str):
            raise InputError("Contract mapping keys must be strings")
        if key in result:
            raise InputError(f"Duplicate contract key: {key!r}")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


_ContractLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_contract(path: str | Path) -> Contract:
    """Read YAML using a safe loader, then validate every option."""
    try:
        data = yaml.load(Path(path).read_text(encoding="utf-8-sig"), Loader=_ContractLoader)
        if not isinstance(data, dict):
            raise InputError("Contract must be a YAML mapping")
        return Contract.model_validate(data)
    except (OSError, UnicodeError, yaml.YAMLError, ValidationError, RecursionError) as exc:
        if isinstance(exc, ValidationError):
            # Pydantic's default error text includes rejected input; keep diagnostics private.
            details = "; ".join(
                f"{'.'.join(map(str, error['loc'])) or 'contract'}: {error['msg']}"
                for error in exc.errors(include_input=False)
            )
        else:
            details = str(exc)
        raise InputError(f"Invalid contract {str(path)!r}: {details}") from exc


def resolve_contract(value: Contract | str | Path | None) -> Contract:
    if value is None:
        return Contract()
    if isinstance(value, Contract):
        return value
    if isinstance(value, str | Path):
        return load_contract(value)
    raise InputError("Contract must be a Contract, a YAML path, or None")
