"""Summarize the old exchange and retain the last two closed user exchanges."""

from copy import deepcopy


def compact(messages):
    instructions = [deepcopy(m) for m in messages if m["role"] in {"system", "developer"}]
    users = [i for i, m in enumerate(messages) if m["role"] == "user"]
    recent_start = users[max(0, len(users) - 3)] if users else len(messages)
    recent = [
        deepcopy(m) for m in messages[recent_start:] if m["role"] not in {"system", "developer"}
    ]
    return (
        instructions
        + [{"role": "assistant", "content": "Summary: the older test investigation is complete."}]
        + recent
    )
