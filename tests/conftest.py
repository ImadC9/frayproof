import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def clean():
    return json.loads((ROOT / "fixtures/clean_session.json").read_text(encoding="utf-8"))


@pytest.fixture
def pinned():
    from frayproof import load_contract

    return load_contract(ROOT / "examples/contract.yaml")


def call(*ids):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": id_, "type": "function", "function": {"name": "read", "arguments": "{}"}}
            for id_ in ids
        ],
    }


def result(id_, content="ok"):
    return {"role": "tool", "tool_call_id": id_, "content": content}


def user(content="hello"):
    return {"role": "user", "content": content}
