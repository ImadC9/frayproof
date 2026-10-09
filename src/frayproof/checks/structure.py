from __future__ import annotations

from ..contract import Contract
from ..model import INSTRUCTION_ROLES, ROLES, Snapshot
from .base import Violation


def structure(after: Snapshot, contract: Contract) -> list[Violation]:
    options = contract.checks.structure
    violations = []
    leading = True
    active_calls: set[str] = set()
    called_ids = {
        call.id
        for message in after.messages
        if message.role == "assistant"
        for call in message.tool_calls
        if call.id
    }

    def emit(message: str, index: int) -> None:
        violations.append(Violation("structure", message, index, options.severity))

    for index, message in enumerate(after.messages):
        if message.role not in ROLES:
            emit("Message role is not supported.", index)
        if message.role in INSTRUCTION_ROLES:
            if options.system_messages == "forbidden":
                emit("Instruction messages are forbidden by the contract.", index)
            elif options.system_messages == "leading_only" and not leading:
                emit("Instruction message must be in the leading instruction block.", index)
        else:
            leading = False
        if message.role == "tool":
            if not message.tool_call_id:
                emit("Tool result must have a nonempty tool_call_id.", index)
            elif message.tool_call_id in called_ids and message.tool_call_id not in active_calls:
                emit("Tool result is outside its assistant tool-call block.", index)
            if message.content is None:
                emit("Tool result must have content (an empty string is allowed).", index)
        else:
            active_calls = (
                {call.id for call in message.tool_calls if call.id}
                if message.role == "assistant"
                else set()
            )
            if message.tool_call_id is not None:
                emit("Only tool messages may have tool_call_id.", index)
        if message.tool_calls and message.role != "assistant":
            emit("Only assistant messages may make tool calls.", index)
        if message.role == "assistant":
            if not (message.has_content or message.tool_calls or (message.refusal or "").strip()):
                emit("Assistant message is completely empty.", index)
        elif message.role != "tool" and message.content is None:
            emit("Non-assistant message must have content.", index)
        for call in message.tool_calls:
            if not call.id.strip():
                emit("Tool call must have a nonempty ID.", index)
            if call.type != "function" or not call.name.strip():
                emit("Tool call must be a named function call.", index)
    return violations
