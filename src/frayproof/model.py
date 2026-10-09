"""Provider-neutral values consumed by checks, independent of wire-format parsing."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

ROLES = frozenset({"system", "developer", "user", "assistant", "tool"})
INSTRUCTION_ROLES = frozenset({"system", "developer"})
TEXT_TYPES = frozenset({"text", "input_text", "output_text"})
# SDK dumps include these optional provider fields as null when unused.
NULLABLE_METADATA = frozenset({"name", "audio", "annotations", "function_call"})


def is_text_block(block: Any) -> bool:
    return (
        isinstance(block, dict)
        and isinstance(block.get("type"), str)
        and block["type"] in TEXT_TYPES
        and isinstance(block.get("text"), str)
    )


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str
    type: str = "function"
    metadata: dict[str, Any] = field(default_factory=dict, repr=False)
    function_metadata: dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.metadata,
            "id": self.id,
            "type": self.type,
            "function": {
                **self.function_metadata,
                "name": self.name,
                "arguments": self.arguments,
            },
        }


@dataclass(frozen=True)
class Message:
    role: str
    content: str | list[dict[str, Any]] | None
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    refusal: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Build current wire values; metadata cannot override modeled fields."""
        fields = {
            key: value
            for key, value in self.metadata.items()
            if key not in {"role", "content", "tool_calls", "tool_call_id", "refusal"}
            and not (key in NULLABLE_METADATA and value is None)
        }
        fields.update(role=self.role, content=self.content)
        if self.tool_calls:
            fields["tool_calls"] = [call.to_dict() for call in self.tool_calls]
        if self.tool_call_id is not None:
            fields["tool_call_id"] = self.tool_call_id
        if self.refusal is not None:
            fields["refusal"] = self.refusal
        return fields

    @property
    def identity(self) -> str:
        """Canonical current values, never a cached identity copied by replace()."""
        return canonical(self.to_dict())

    @property
    def text_parts(self) -> tuple[str, ...]:
        if isinstance(self.content, str):
            return (self.content,)
        if isinstance(self.content, list):
            return tuple(block["text"] for block in self.content if is_text_block(block))
        return ()

    @property
    def has_content(self) -> bool:
        if isinstance(self.content, str):
            return bool(self.content.strip())
        if isinstance(self.content, list):
            return any(
                bool(block.get("text", "").strip()) if is_text_block(block) else bool(block)
                for block in self.content
            )
        return False


@dataclass(frozen=True)
class Snapshot:
    messages: tuple[Message, ...]


def canonical(value: Any) -> str:
    """Compare full JSON values without depending on dictionary insertion order."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
