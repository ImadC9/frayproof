"""Transformations receive original wire fields, independently of comparison normalization."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest

from frayproof import Contract, InputError, load_snapshot
from frayproof.mutate import run_mutations, run_mutations_async
from frayproof.mutate.mutators import generate_mutations


def wire_session(calls):
    return [
        {"content": "Policy", "role": "system", "name": None},
        {"content": "Question", "role": "user", "metadata": {"nested": [None]}},
        {
            "content": "Answer",
            "role": "assistant",
            "tool_calls": calls,
            "refusal": None,
            "audio": None,
            "annotations": None,
            "function_call": None,
        },
        {"content": "Latest", "role": "user"},
    ]


def config():
    return Contract.model_validate(
        {
            "pins": [{"name": "system", "role": "system"}],
            "retain": {"latest_user_message": "exact", "recent_exchanges": 1},
        }
    )


def invoke(source, transform, asynchronous):
    if asynchronous:

        async def target(raw):
            return transform(raw)

        return asyncio.run(run_mutations_async(source, target, config()))
    return run_mutations(source, transform, config())


@pytest.mark.parametrize("calls", [[], None])
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("from_file", [False, True])
def test_working_transform_receives_every_original_field(tmp_path, calls, asynchronous, from_file):
    original = wire_session(calls)
    saved = deepcopy(original)
    source = original
    if from_file:
        source = tmp_path / "input.json"
        source.write_text(json.dumps(original), encoding="utf-8-sig")
    invocations = []

    def transform(raw):
        invocations.append(1)
        assert raw == saved
        assert [list(m) for m in raw] == [list(m) for m in saved]
        assert raw[2]["tool_calls"] == calls  # direct access used to crash
        assert raw[2]["refusal"] is None and raw[0]["name"] is None
        raw[1]["metadata"]["nested"].append("In-place edit")
        return raw

    report = invoke(source, transform, asynchronous)
    # The target ran successfully on the real fields; its intentional change
    # inside a protected exchange is then found against the untouched baseline.
    assert not report.baseline.passed and report.mutants == ()
    assert invocations == [1] and original == saved


@pytest.mark.parametrize("asynchronous", [False, True])
def test_valid_identity_transform_does_not_crash_on_explicit_empty_calls(asynchronous):
    def transform(raw):
        assert raw[2]["tool_calls"] == []
        return raw

    assert invoke(wire_session([]), transform, asynchronous).passed


@pytest.mark.parametrize("asynchronous", [False, True])
def test_real_input_failure_cannot_receive_a_passing_baseline(asynchronous):
    def transform(raw):
        if "tool_calls" in raw[2]:
            raise RuntimeError("Cannot process explicit calls")
        return raw

    with pytest.raises(InputError, match="Transformation failed: RuntimeError"):
        invoke(wire_session([]), transform, asynchronous)


@pytest.mark.parametrize("asynchronous", [False, True])
def test_shape_dependent_contract_violation_is_found_in_real_baseline(asynchronous):
    def transform(raw):
        if raw[2].get("tool_calls") == []:
            raw.pop()
        return raw

    report = invoke(wire_session([]), transform, asynchronous)
    assert not report.baseline.passed and report.mutants == ()
    assert "latest_user_message" in {v.rule for v in report.baseline.violations}


def test_file_is_read_once_and_missing_fields_are_not_inserted(tmp_path, monkeypatch):
    path = tmp_path / "input.json"
    path.write_text('[{"role":"assistant","tool_calls":[],"refusal":"Declined"}]', encoding="utf-8")
    reads = []
    original_read = Path.read_text

    def record_read(self, *args, **kwargs):
        reads.append(self)
        return original_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", record_read)

    def transform(raw):
        assert "content" not in raw[0] and raw[0]["tool_calls"] == []
        return raw

    assert run_mutations(path, transform).baseline.passed
    assert reads == [path]


@pytest.mark.parametrize(
    "text", ['[{"role":"user","role":"assistant"}]', '[{"role":"user","content":"x","value":NaN}]']
)
def test_invalid_wire_files_are_rejected_before_target_runs(tmp_path, text):
    path = tmp_path / "input.json"
    path.write_text(text, encoding="utf-8")

    def transform(raw):
        pytest.fail("Invalid input reached transformation")

    with pytest.raises(InputError):
        run_mutations(path, transform)


def test_mutants_preserve_real_output_fields_and_null_calls():
    raw = wire_session(None)
    snapshot = load_snapshot(raw)
    mutants = generate_mutations(raw, snapshot, snapshot, config())
    moved = next(m for m in mutants if m.name == "move_instruction")
    assert moved.messages[-1] == raw[0]
    assistant = next(m for m in moved.messages if m["role"] == "assistant")
    assert assistant == raw[2] and "tool_calls" in assistant


def test_runner_generates_mutants_from_actual_output(monkeypatch):
    import frayproof.mutate.runner as runner

    original = wire_session([])
    expected = deepcopy(original)
    generate = runner.generate_mutations

    def inspect_output(messages, *args):
        assert messages == expected
        assert [list(m) for m in messages] == [list(m) for m in expected]
        return generate(messages, *args)

    monkeypatch.setattr(runner, "generate_mutations", inspect_output)
    assert run_mutations(original, lambda raw: raw, config()).passed
