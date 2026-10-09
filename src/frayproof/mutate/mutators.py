"""Deterministic faults at every eligible site in detached OpenAI message lists."""

from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Any

from ..contract import Contract
from ..loaders import load_snapshot
from ..model import INSTRUCTION_ROLES, Snapshot, is_text_block
from ..selection import closed_exchanges

Messages = list[dict[str, Any]]


@dataclass(frozen=True)
class Mutation:
    name: str
    description: str
    messages: Messages | None
    message_index: int | None = None
    skip_reason: str | None = None
    sites: tuple[str, ...] = ()


def _calls(messages: Messages) -> list[tuple[int, int, str]]:
    return [
        (index, position, call["id"])
        for index, message in enumerate(messages)
        if message.get("role") == "assistant"
        for position, call in enumerate(message.get("tool_calls") or [])
        if call.get("id")
    ]


def _site(index: int, position: int | None = None) -> str:
    return f"after[{index}]" + (f".tool_calls[{position}]" if position is not None else "")


def _candidate(name, description, changed, index, site=None):
    return Mutation(name, description, changed, index, sites=(site or _site(index),))


def _drop_call(messages: Messages) -> list[Mutation]:
    result_ids = {m.get("tool_call_id") for m in messages if m.get("role") == "tool"}
    calls = _calls(messages)
    counts = Counter(call_id for _, _, call_id in calls)
    candidates = []
    for index, position, call_id in calls:
        if call_id not in result_ids or counts[call_id] != 1:
            continue
        changed = deepcopy(messages)
        del changed[index]["tool_calls"][position]
        if not changed[index]["tool_calls"]:
            changed[index].pop("tool_calls")
            # Avoid an unrelated empty-assistant error masking weak orphan protection.
            neutral = load_snapshot([changed[index]]).messages[0]
            if not neutral.has_content and not (neutral.refusal or "").strip():
                del changed[index]
        candidates.append(
            _candidate(
                "drop_tool_call",
                "Remove a tool call, leaving its result.",
                changed,
                index,
                _site(index, position),
            )
        )
    return candidates


def _drop_result(messages: Messages) -> list[Mutation]:
    ids = {call_id for _, _, call_id in _calls(messages)}
    counts = Counter(m.get("tool_call_id") for m in messages if m.get("role") == "tool")
    candidates = []
    for index, message in enumerate(messages):
        if (
            message.get("role") == "tool"
            and message.get("tool_call_id") in ids
            and counts[message.get("tool_call_id")] == 1
        ):
            changed = deepcopy(messages)
            del changed[index]
            candidates.append(
                _candidate(
                    "drop_tool_result", "Remove a tool result, leaving its call.", changed, index
                )
            )
    return candidates


def _duplicate_id(messages: Messages) -> list[Mutation]:
    candidates = []
    for index, position, _ in _calls(messages):
        changed = deepcopy(messages)
        changed[index]["tool_calls"].append(deepcopy(changed[index]["tool_calls"][position]))
        candidates.append(
            _candidate(
                "duplicate_tool_id",
                "Duplicate a call with the same ID.",
                changed,
                index,
                _site(index, position),
            )
        )
    return candidates


def _edit_text(message: dict, edit) -> None:
    content = message.get("content")
    if isinstance(content, str):
        message["content"] = edit(content)
    elif isinstance(content, list):
        for block in content:
            if is_text_block(block):
                block["text"] = edit(block["text"])


def _remove_literal(part: str, text: str) -> str:
    # Deletion can join characters into a new match ("aababa" -> "aba").
    # Each pass shrinks the part; selectors are always nonempty.
    while text in part:
        part = part.replace(text, "")
    return part


def _remove_text(
    messages: Messages, before: Snapshot, after: Snapshot, contract: Contract
) -> list[Mutation]:
    selectors = []
    for pin in contract.pins:
        if pin.contains is not None:
            if not any(pin.contains in part for m in before.messages for part in m.text_parts):
                continue
            indices = [
                index
                for index, m in enumerate(after.messages)
                if any(pin.contains in part for part in m.text_parts)
            ]
            if indices:
                selectors.append(
                    (
                        indices[0],
                        pin.contains,
                        f"Remove text protected by pin {pin.name!r}.",
                        f"pin:{pin.name}",
                        True,
                    )
                )
        else:
            protected = {m.identity for m in before.messages if m.role == pin.role}
            for index, m in enumerate(after.messages):
                if m.identity in protected and any(part.strip() for part in m.text_parts):
                    text = next(part for part in m.text_parts if part.strip())
                    selectors.append(
                        (
                            index,
                            text,
                            f"Change content protected by pin {pin.name!r}.",
                            f"pin:{pin.name}@{_site(index)}",
                            False,
                        )
                    )
    if not selectors:
        for index, m in enumerate(after.messages):
            if m.role in INSTRUCTION_ROLES:
                line = next(
                    (line for part in m.text_parts for line in part.splitlines() if line.strip()),
                    None,
                )
                if line is not None:
                    selectors.append(
                        (
                            index,
                            line,
                            "Remove instruction text; no matching text pin.",
                            _site(index),
                            False,
                        )
                    )
    candidates = []
    for index, text, description, site, all_copies in selectors:
        changed = deepcopy(messages)
        # Presence pins require removing every copy. Exact role pins protect each
        # occurrence, so only their selected message is changed.
        for message in changed if all_copies else [changed[index]]:
            _edit_text(message, lambda part, selected=text: _remove_literal(part, selected))
        candidates.append(_candidate("remove_pinned_text", description, changed, index, site))
    return candidates


def _swap(messages: Messages) -> list[Mutation]:
    candidates = []
    for call_index, position, call_id in _calls(messages):
        for result_index in range(call_index + 1, len(messages)):
            message = messages[result_index]
            if message.get("role") == "tool" and message.get("tool_call_id") == call_id:
                changed = deepcopy(messages)
                changed[call_index], changed[result_index] = (
                    changed[result_index],
                    changed[call_index],
                )
                candidates.append(
                    _candidate(
                        "swap_call_result",
                        "Place a result before its tool call.",
                        changed,
                        result_index,
                        f"{_site(call_index, position)}->{_site(result_index)}",
                    )
                )
    return candidates


def _move_instruction(messages: Messages) -> list[Mutation]:
    candidates = []
    for index, message in enumerate(messages):
        if message.get("role") in INSTRUCTION_ROLES and any(
            m.get("role") not in INSTRUCTION_ROLES for m in messages[index + 1 :]
        ):
            changed = deepcopy(messages)
            changed.append(changed.pop(index))
            candidates.append(
                _candidate(
                    "move_instruction",
                    "Move an instruction message after conversation.",
                    changed,
                    index,
                )
            )
    return candidates


def _drop_latest_user(messages: Messages) -> list[Mutation]:
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].get("role") == "user":
            changed = deepcopy(messages)
            del changed[index]
            return [
                _candidate("drop_latest_user", "Remove the latest user message.", changed, index)
            ]
    return []


def _truncate_result(messages: Messages, after: Snapshot) -> list[Mutation]:
    candidates = []
    for index, message in enumerate(after.messages):
        if message.role == "tool" and any(len(part) > 1 for part in message.text_parts):
            changed = deepcopy(messages)
            _edit_text(changed[index], lambda part: part[: max(1, len(part) // 2)])
            candidates.append(
                _candidate(
                    "truncate_tool_result",
                    "Keep the result ID but truncate its text.",
                    changed,
                    index,
                )
            )
    return candidates


def _drop_exchange(messages: Messages, after: Snapshot) -> list[Mutation]:
    # A closed exchange starts at a user turn and ends before the next user turn.
    # The latest user turn has its own operator. Whole batches disappear together.
    candidates = []
    for start, end in closed_exchanges(after):
        changed = deepcopy(messages)
        changed[start:end] = [m for m in changed[start:end] if m.get("role") in INSTRUCTION_ROLES]
        candidates.append(
            _candidate(
                "drop_recent_exchange",
                "Remove a closed user exchange, including its calls and results.",
                changed,
                start,
                f"after[{start}:{end}]",
            )
        )
    return candidates


def generate_mutations(
    messages: Messages, before: Snapshot, after: Snapshot, contract: Contract
) -> tuple[Mutation, ...]:
    """Test every eligible site; collapse identical outputs within each operator."""
    groups = [
        (
            "drop_tool_call",
            _drop_call(messages),
            "No answered assistant call with a unique ID exists in the output.",
        ),
        (
            "drop_tool_result",
            _drop_result(messages),
            "No matching tool result with a unique result ID exists in the output.",
        ),
        (
            "duplicate_tool_id",
            _duplicate_id(messages),
            "No assistant tool call exists in the output.",
        ),
        (
            "remove_pinned_text",
            _remove_text(messages, before, after, contract),
            "No activated textual pin or instruction text in the output.",
        ),
        ("swap_call_result", _swap(messages), "No ordered call/result pair exists in the output."),
        (
            "move_instruction",
            _move_instruction(messages),
            "No instruction can be moved behind a conversation message.",
        ),
        ("drop_latest_user", _drop_latest_user(messages), "No user message exists in the output."),
        (
            "truncate_tool_result",
            _truncate_result(messages, after),
            "No tool result has truncatable text in the output.",
        ),
        (
            "drop_recent_exchange",
            _drop_exchange(messages, after),
            "No closed user exchange exists in the output.",
        ),
    ]
    mutations = []
    for name, candidates, reason in groups:
        unique: dict[str, Mutation] = {}
        for candidate in candidates:
            key = json.dumps(candidate.messages, sort_keys=True, ensure_ascii=False)
            if key in unique:
                previous = unique[key]
                unique[key] = replace(previous, sites=previous.sites + candidate.sites)
            else:
                unique[key] = candidate
        mutations.extend(
            unique.values() if unique else [Mutation(name, reason, None, skip_reason=reason)]
        )
    return tuple(mutations)
