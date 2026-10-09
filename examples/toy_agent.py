"""An offline toy session with good and deliberately broken compactors."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from frayproof import ContractViolation, guard, load_contract

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = load_contract(Path(__file__).with_name("contract.yaml"))


def compact(messages):
    """Replace a completed old exchange with a summary, preserving instructions."""
    instructions = [deepcopy(m) for m in messages if m["role"] in {"system", "developer"}]
    return instructions + [
        {
            "role": "assistant",
            "content": "Summary: read test_app.py. The test expects add(1, 2) to return 3.",
        },
        deepcopy(messages[-1]),
    ]


@guard(CONTRACT)
def safe_compact(messages):
    return compact(messages)


@guard(CONTRACT)
def broken_compact(messages):
    """Plant the orphaned-result bug by removing only the assistant call."""
    return [deepcopy(m) for m in messages if not m.get("tool_calls")]


def main():
    messages = json.loads((ROOT / "fixtures/clean_session.json").read_text(encoding="utf-8"))
    print(f"Safe compaction: {len(messages)} -> {len(safe_compact(messages))} messages")
    try:
        broken_compact(messages)
    except ContractViolation as exc:
        print("Broken compaction blocked:")
        print(exc.report.to_text())


if __name__ == "__main__":
    main()
