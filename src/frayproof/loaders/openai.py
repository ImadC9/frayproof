"""Load OpenAI Chat Completions message arrays, retaining exact message identity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..errors import InputError
from ..model import Message, Snapshot, ToolCall, canonical

SnapshotInput = Snapshot | list[dict[str, Any]] | str | Path


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _string(value: Any, location: str, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str):
        raise InputError(f"{location} must be a string" + (" or null" if nullable else ""))
    return value


def _read_data(source: Any) -> Any:
    """Read wire data once, preserving field presence and rejecting duplicate keys."""
    if not isinstance(source, str | Path):
        return source
    try:
        return json.loads(
            Path(source).read_text(encoding="utf-8-sig"), object_pairs_hook=_object_pairs
        )
    except (OSError, UnicodeError, ValueError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError(f"Cannot read snapshot {str(source)!r}: {exc}") from exc


def load_snapshot(source: SnapshotInput) -> Snapshot:
    """Load a UTF-8 JSON file or a message list. Malformed shape raises InputError.

    Unsupported roles, missing IDs and misplaced messages remain semantic check failures.
    Raw messages are copied so later in-place transformations cannot change the baseline.
    """
    if isinstance(source, Snapshot):
        try:
            if not isinstance(source.messages, tuple | list):
                raise InputError("Snapshot.messages must be a tuple or list")
            if any(not isinstance(message, Message) for message in source.messages):
                raise InputError("Snapshot messages must be neutral Message values")
            if any(not isinstance(message.tool_calls, tuple | list) for message in source.messages):
                raise InputError("Neutral Message.tool_calls must be a tuple or list")
            # Re-enter the same validation boundary using actual current fields.
            source = [message.to_dict() for message in source.messages]
        except (TypeError, ValueError, AttributeError) as exc:
            if isinstance(exc, InputError):
                raise
            raise InputError("Invalid neutral snapshot fields") from exc
    data = _read_data(source)
    if not isinstance(data, list):
        raise InputError("Snapshot must be a JSON array of message objects")
    messages = []
    for index, raw in enumerate(data):
        label = f"messages[{index}]"
        if not isinstance(raw, dict):
            raise InputError(f"{label} must be an object")
        try:
            raw = json.loads(canonical(raw))
        except (TypeError, ValueError, RecursionError) as exc:
            raise InputError(f"{label} must contain finite JSON values") from exc
        role = _string(raw.get("role", ""), f"{label}.role")
        content = raw.get("content")
        if content is not None and not isinstance(content, str | list):
            raise InputError(f"{label}.content must be a string, array of objects, or null")
        if isinstance(content, list) and any(not isinstance(b, dict) for b in content):
            raise InputError(f"{label}.content must contain objects")
        if isinstance(content, list):
            for block_index, block in enumerate(content):
                if "type" in block and not isinstance(block["type"], str):
                    raise InputError(f"{label}.content[{block_index}].type must be a string")
        calls = raw.get("tool_calls", [])
        if calls is None:
            calls = []
        if not isinstance(calls, list):
            raise InputError(f"{label}.tool_calls must be an array or null")
        parsed_calls = []
        for call_index, call in enumerate(calls):
            loc = f"{label}.tool_calls[{call_index}]"
            if not isinstance(call, dict) or not isinstance(call.get("function", {}), dict):
                raise InputError(f"{loc} and its function must be objects")
            function = call.get("function", {})
            parsed_calls.append(
                ToolCall(
                    id=_string(call.get("id", ""), f"{loc}.id"),
                    name=_string(function.get("name", ""), f"{loc}.function.name"),
                    arguments=_string(function.get("arguments", ""), f"{loc}.function.arguments"),
                    type=_string(call.get("type", ""), f"{loc}.type"),
                    metadata={
                        key: value
                        for key, value in call.items()
                        if key not in {"id", "type", "function"}
                    },
                    function_metadata={
                        key: value
                        for key, value in function.items()
                        if key not in {"name", "arguments"}
                    },
                )
            )
        messages.append(
            Message(
                role=role,
                content=content,
                tool_calls=tuple(parsed_calls),
                tool_call_id=_string(
                    raw.get("tool_call_id"), f"{label}.tool_call_id", nullable=True
                ),
                refusal=_string(raw.get("refusal"), f"{label}.refusal", nullable=True),
                metadata={
                    key: value
                    for key, value in raw.items()
                    if key not in {"role", "content", "tool_calls", "tool_call_id", "refusal"}
                },
            )
        )
    return Snapshot(tuple(messages))
