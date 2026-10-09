import json

import pytest
from pydantic import ValidationError

from frayproof import Contract, InputError, load_contract, load_snapshot, validate
from frayproof.contract import resolve_contract

from .conftest import user


@pytest.mark.parametrize(
    "source",
    [
        {},
        None,
        3,
        (),
        ["text"],
        [{"role": 2}],
        [{"role": "user", "content": 3}],
        [user(["not a block"])],
        [{"role": "assistant", "tool_calls": "not an array"}],
        [{"role": "assistant", "tool_calls": [None]}],
        [{"role": "assistant", "tool_calls": [{"function": "read"}]}],
        [{"role": "assistant", "tool_calls": [{"id": 3}]}],
        [dict(user(), tool_call_id=4)],
        [dict(user(), refusal=4)],
        [dict(user(), unsupported=float("nan"))],
        [dict(user(), unsupported={1, 2})],
    ],
)
def test_bad_snapshot_shape_is_input_error(source):
    with pytest.raises(InputError):
        load_snapshot(source)


@pytest.mark.parametrize(
    "text",
    [
        "{",
        "{}",
        "[] trailing",
        '[{"role":"user","role":"tool"}]',
        '[{"role":"user","content":NaN}]',
    ],
)
def test_invalid_json_files(tmp_path, text):
    path = tmp_path / "bad.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(InputError):
        load_snapshot(path)


def test_missing_snapshot_file(tmp_path):
    with pytest.raises(InputError):
        load_snapshot(tmp_path / "missing.json")


def test_utf8_bom_and_unicode(tmp_path):
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps([user("مرحبا café")], ensure_ascii=False), encoding="utf-8-sig")
    assert load_snapshot(path).messages[0].content == "مرحبا café"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "[]",
        "version: 2",
        "version: true",
        "format: anthropic",
        "typo: true",
        "checks:\n  tool_pair: true",
        "checks:\n  structure:\n    system_messages: middle",
        "checks:\n  tool_pairs:\n    allow_trailing_pending_call: yesplease",
        "checks:\n  unique_tool_ids:\n    severity: info",
        "version: 1\nversion: 2",
        "checks:\n  structure: true\n  structure: false",
        "1: value",
        "[unterminated",
        "!!python/object/apply:os.system ['echo unsafe']",
        "pins:\n  - name: x",
        "pins:\n  - name: x\n    role: alien",
        "pins:\n  - name: x\n    role: system\n    contains: hello",
        "pins:\n  - name: x\n    contains: ''",
        "pins:\n  - name: x\n    role: system\n    match: regex",
        "pins:\n  - name: x\n    role: system\n  - name: x\n    role: user",
    ],
)
def test_invalid_contracts(tmp_path, text):
    path = tmp_path / "contract.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(InputError):
        load_contract(path)


def test_contract_missing_file(tmp_path):
    with pytest.raises(InputError):
        load_contract(tmp_path / "missing.yaml")


def test_valid_contract_defaults(tmp_path):
    path = tmp_path / "contract.yaml"
    path.write_text("version: 1\nchecks:\n  tool_pairs: false\n", encoding="utf-8-sig")
    contract = load_contract(path)
    assert not contract.checks.tool_pairs.enabled
    assert contract.checks.structure.enabled
    assert contract.pins == ()


def test_contract_object_is_frozen():
    with pytest.raises(ValidationError):
        Contract().version = 2


def test_invalid_contract_argument():
    with pytest.raises(InputError):
        resolve_contract({})


def test_validate_with_pins_is_explicit_input_error(pinned):
    with pytest.raises(InputError, match="before snapshot"):
        validate([], pinned)
