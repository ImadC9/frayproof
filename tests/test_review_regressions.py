"""Release-review reproductions plus SDK-null and opaque-metadata regressions."""

import asyncio
import json
from copy import deepcopy
from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st
from typer.testing import CliRunner

from frayproof import Contract, ContractViolation, InputError, check, guard, load_snapshot, validate
from frayproof.model import Message, Snapshot, ToolCall
from frayproof.mutate import run_mutations
from frayproof.mutate.mutators import generate_mutations

from .conftest import call, result, user

POLICIES = [
    {"pins": [{"name": "users", "role": "user"}]},
    {"retain": {"latest_user_message": "exact"}},
    {"retain": {"recent_exchanges": 1}},
]


def neutral_session():
    return load_snapshot(
        [
            dict(user("Original"), provider={"important": "metadata"}),
            {"role": "assistant", "content": "Original reply"},
            user("Latest"),
        ]
    )


@pytest.mark.parametrize("policy", POLICIES)
def test_replaced_neutral_fields_fail_exact_checks(policy):
    before = neutral_session()
    after = Snapshot(tuple(replace(m, content="Changed") for m in before.messages))
    config = Contract.model_validate(policy)
    assert check(before, before, config).passed
    assert not check(before, after, config).passed
    assert after.messages[0].identity != before.messages[0].identity
    assert json.loads(after.messages[0].identity)["provider"] == {"important": "metadata"}
    assert before.messages[0].content == "Original"


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("asynchronous", [False, True])
def test_guard_rejects_replaced_neutral_outputs(policy, asynchronous):
    def transform(snapshot):
        return Snapshot(tuple(replace(m, content="Changed") for m in snapshot.messages))

    async def async_transform(snapshot):
        return transform(snapshot)

    protected = guard(Contract.model_validate(policy))(
        async_transform if asynchronous else transform
    )
    with pytest.raises(ContractViolation):
        if asynchronous:
            asyncio.run(protected(neutral_session()))
        else:
            protected(neutral_session())


def test_current_nested_fields_and_metadata_affect_identity():
    before = load_snapshot(
        [dict(user([{"type": "text", "text": "Original"}]), provider={"value": 1})]
    )
    config = Contract.model_validate({"pins": [{"name": "users", "role": "user"}]})
    for change in [
        lambda m: m.content[0].update(text="Changed"),
        lambda m: m.metadata["provider"].update(value=2),
    ]:
        after = deepcopy(before)
        change(after.messages[0])
        assert not check(before, after, config).passed


def test_neutral_roundtrip_preserves_message_call_and_function_metadata():
    raw = [dict(call("a"), provider={"state": None}), result("a")]
    raw[0]["tool_calls"][0]["provider_id"] = "opaque call metadata"
    raw[0]["tool_calls"][0]["function"]["provider_schema"] = {"nullable": None}
    neutral = load_snapshot(raw)
    config = Contract.model_validate({"pins": [{"name": "assistant", "role": "assistant"}]})
    assert check(raw, neutral, config).passed and check(neutral, raw, config).passed
    assert json.loads(neutral.messages[0].identity) == raw[0]
    changed_call = replace(neutral.messages[0].tool_calls[0], arguments='{"new":1}')
    after = Snapshot(
        (replace(neutral.messages[0], tool_calls=(changed_call,)), neutral.messages[1])
    )
    assert not check(neutral, after, config).passed
    assert changed_call.function_metadata["provider_schema"] == {"nullable": None}
    assert changed_call.metadata["provider_id"] == "opaque call metadata"
    assert check(neutral, load_snapshot(neutral), config).passed


def test_model_fields_cannot_be_masked_by_metadata():
    message = Message(
        "user", "Actual", metadata={"content": "Fake", "role": "assistant", "tool_calls": ["fake"]}
    )
    assert json.loads(message.identity) == user("Actual")
    tool = ToolCall(
        "a", "read", "{}", metadata={"id": "fake"}, function_metadata={"arguments": "fake"}
    )
    assert tool.to_dict()["id"] == "a" and tool.to_dict()["function"]["arguments"] == "{}"


@pytest.mark.parametrize("discriminator", [[], {}, None, 1, True])
def test_malformed_discriminators_raise_input_error_at_all_boundaries(discriminator):
    raw = [{"role": "assistant", "content": [{"type": discriminator}]}]
    pin = Contract.model_validate({"pins": [{"name": "text", "contains": "keep"}]})
    neutral = Snapshot((Message("assistant", raw[0]["content"]),))
    assert neutral.messages[0].text_parts == ()  # helpers are safe even before loading
    for operation in [
        lambda: validate(raw),
        lambda: check([user("keep")], raw, pin),
        lambda: run_mutations(raw, lambda m: m),
        lambda: validate(neutral),
    ]:
        with pytest.raises(InputError, match=r"content\[0\].type must be a string"):
            operation()


@pytest.mark.parametrize("discriminator", [[], {}])
def test_malformed_block_cli_emits_json_exit_two(tmp_path, discriminator):
    from frayproof.cli import app

    path = tmp_path / "malformed.json"
    path.write_text(
        json.dumps([{"role": "assistant", "content": [{"type": discriminator}]}]), encoding="utf-8"
    )
    outcome = CliRunner().invoke(app, ["validate", "--snapshot", str(path), "--format", "json"])
    assert outcome.exit_code == 2 and outcome.stderr == ""
    assert json.loads(outcome.stdout)["schema_version"] == 1
    assert "type must be a string" in json.loads(outcome.stdout)["error"]


@pytest.mark.parametrize(
    "factory",
    [
        lambda: Message("user", "x", tool_calls=(None,)),
        lambda: Message("user", "x", tool_calls=False),
        lambda: Message("user", "x", metadata=None),
        lambda: Message("user", {"invalid": "content"}),
        lambda: "not a message",
    ],
)
def test_invalid_neutral_shapes_are_input_errors(factory):
    with pytest.raises(InputError):
        validate(Snapshot((factory(),)))


@pytest.mark.parametrize("messages", [None, {}, "", iter([Message("user", "x")])])
def test_invalid_snapshot_containers_are_input_errors(messages):
    with pytest.raises(InputError, match="Snapshot.messages"):
        validate(Snapshot(messages))


def test_unknown_string_block_types_remain_opaque():
    message = {
        "role": "assistant",
        "content": [{"type": "future_provider_block", "payload": {"key": []}}],
    }
    assert validate([message]).passed
    assert json.loads(load_snapshot([message]).messages[0].identity) == message


@pytest.mark.parametrize(
    "field",
    ["tool_calls", "refusal", "tool_call_id", "name", "audio", "annotations", "function_call"],
)
def test_optional_null_fields_equal_omission_for_exact_pins(field):
    sparse = [user("Keep")]
    explicit = [dict(sparse[0], **{field: None})]
    config = Contract.model_validate({"pins": [{"name": "users", "role": "user"}]})
    assert check(sparse, explicit, config).passed and check(explicit, sparse, config).passed
    assert (
        load_snapshot(sparse).messages[0].identity == load_snapshot(explicit).messages[0].identity
    )


def test_sdk_nulls_work_in_validation_retention_and_mutations(tmp_path):
    from frayproof.cli import app

    sparse = [user("Request"), {"role": "assistant", "content": "Answer"}, user("Latest")]
    dumped = deepcopy(sparse)
    dumped[1].update(
        tool_calls=None, refusal=None, audio=None, annotations=None, function_call=None
    )
    config = Contract.model_validate(
        {
            "pins": [{"name": "assistant", "role": "assistant"}],
            "retain": {"latest_user_message": "exact", "recent_exchanges": 1},
        }
    )
    assert validate(dumped).passed and check(sparse, dumped, config).passed
    assert check(dumped, sparse, config).passed
    report = run_mutations(dumped, lambda raw: raw, config)
    assert report.baseline.passed
    path = tmp_path / "sdk_dump.json"
    path.write_text(json.dumps(dumped), encoding="utf-8")
    outcome = CliRunner().invoke(app, ["validate", "--snapshot", str(path), "--format", "json"])
    assert outcome.exit_code == 0 and json.loads(outcome.stdout)["passed"]
    assert (
        load_snapshot([dict(sparse[1], tool_calls=[])]).messages[0].identity
        == load_snapshot([dumped[1]]).messages[0].identity
    )


def test_optional_null_normalization_does_not_discard_opaque_null_metadata():
    config = Contract.model_validate({"pins": [{"name": "users", "role": "user"}]})
    assert not check([user("Keep")], [dict(user("Keep"), custom=None)], config).passed
    assert not check(
        [dict(user("Keep"), provider={"state": None})], [dict(user("Keep"), provider={})], config
    ).passed
    assert not check([dict(user("Keep"), name="human")], [user("Keep")], config).passed


@pytest.mark.parametrize(
    "text,literal", [("aababa", "aba"), ("ababa", "aba"), ("aaaaa", "aa"), ("abcabcabc", "abc")]
)
def test_text_loss_mutant_removes_joined_and_overlapping_occurrences(text, literal):
    before = [{"role": "system", "content": text}, user([{"type": "text", "text": text}])]
    config = Contract.model_validate({"pins": [{"name": "keep", "contains": literal}]})
    snapshot = load_snapshot(before)
    mutants = generate_mutations(before, snapshot, snapshot, config)
    lost = next(m for m in mutants if m.name == "remove_pinned_text")
    assert not any(
        literal in part for m in load_snapshot(lost.messages).messages for part in m.text_parts
    )
    scored = next(
        m
        for m in run_mutations(before, lambda raw: raw, config).mutants
        if m.name == "remove_pinned_text"
    )
    assert scored.status == "caught"


@given(
    st.text(alphabet="ab", min_size=1, max_size=6),
    st.text(alphabet="ab", max_size=40),
    st.text(alphabet="ab", max_size=40),
)
def test_contains_mutants_have_a_verified_text_loss_postcondition(literal, prefix, suffix):
    messages = [{"role": "system", "content": prefix + literal + suffix}]
    config = Contract.model_validate({"pins": [{"name": "keep", "contains": literal}]})
    report = run_mutations(messages, lambda raw: raw, config)
    assert report.operators["remove_pinned_text"] == {"caught": 1, "survived": 0, "skipped": 0}


def test_review_f3_exact_reproduction_is_caught():
    config = Contract.model_validate({"pins": [{"name": "keep", "contains": "aba"}]})
    report = run_mutations([{"role": "system", "content": "aababa"}], lambda raw: raw, config)
    assert report.passed and report.caught == 1 and report.survived == 0 and report.skipped == 8


def test_replacing_neutral_refusal_cannot_reuse_an_old_identity():
    before = load_snapshot([{"role": "assistant", "content": None, "refusal": "Original refusal"}])
    after = Snapshot((replace(before.messages[0], refusal="Changed refusal"),))
    config = Contract.model_validate({"pins": [{"name": "assistant", "role": "assistant"}]})
    assert check(before, before, config).passed
    assert not check(before, after, config).passed


def test_guard_captures_mutable_neutral_content_before_in_place_edits():
    config = Contract.model_validate({"retain": {"latest_user_message": "exact"}})

    @guard(config)
    def transform(snapshot):
        snapshot.messages[0].content[0]["text"] = "Changed"
        return snapshot

    before = load_snapshot([user([{"type": "text", "text": "Original"}])])
    with pytest.raises(ContractViolation):
        transform(before)
