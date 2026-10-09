"""Shared positional selectors, resolved on a specific immutable snapshot."""

from .model import Snapshot


def closed_exchanges(snapshot: Snapshot) -> tuple[tuple[int, int], ...]:
    """User-to-next-user spans containing assistant/tool activity; end is exclusive."""
    users = [i for i, message in enumerate(snapshot.messages) if message.role == "user"]
    return tuple(
        (start, end)
        for start, end in zip(users, users[1:], strict=False)
        if any(m.role in {"assistant", "tool"} for m in snapshot.messages[start + 1 : end])
    )
