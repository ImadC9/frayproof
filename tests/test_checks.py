from copy import deepcopy

import pytest

from frayproof import Contract, check, load_snapshot, validate
from frayproof.model import Message, Snapshot

from .conftest import ROOT, call, result, user


def findings(messages, check_name, config=None):
    return [v for v in validate(messages, config).violations if v.check == check_name]


@pytest.mark.parametrize("fixture", ["clean_session", "legitimate_compaction"])
def test_clean_fixtures(fixture):
    assert validate(ROOT / f"fixtures/{fixture}.json").passed


def test_orphan_fixture_exact_index():
    report = validate(ROOT / "fixtures/orphaned_result.json")
    assert [(v.check, v.message_index) for v in report.violations] == [
        ("tool_pair_integrity", 2),
    ]
    assert report.violations[0].tool_call_id == "call_1"


def test_parallel_results_can_arrive_in_any_order():
    assert validate([call("a", "b"), result("b"), result("a")]).passed


def test_missing_result_points_to_call():
    assert findings([user(), call("a")], "tool_pair_integrity")[0].message_index == 1


def test_result_before_call_has_two_pair_failures():
    pairs = findings([result("a"), call("a")], "tool_pair_integrity")
    assert [v.message_index for v in pairs] == [0, 1]


def test_pending_default_is_strict():
    assert not validate(ROOT / "fixtures/pending_batch.json").passed


def test_pending_partial_trailing_batch_is_allowed():
    config = Contract.model_validate(
        {"checks": {"tool_pairs": {"allow_trailing_pending_call": True}}}
    )
    assert validate(ROOT / "fixtures/pending_batch.json", config).passed
    assert validate([call("a", "b")], config).passed


def test_pending_does_not_excuse_old_missing_results():
    config = Contract.model_validate(
        {"checks": {"tool_pairs": {"allow_trailing_pending_call": True}}}
    )
    pairs = findings([call("a"), user(), call("b")], "tool_pair_integrity", config)
    assert [(v.message_index, v.tool_call_id) for v in pairs] == [(0, "a")]
    assert findings([call("a"), user()], "tool_pair_integrity", config)


@pytest.mark.parametrize(
    "messages,index",
    [
        ([call("a", "a"), result("a")], 0),
        ([call("a"), result("a"), call("a"), result("a")], 2),
    ],
)
def test_duplicate_call_ids(messages, index):
    assert findings(messages, "unique_tool_ids")[0].message_index == index


def test_duplicate_result():
    violations = findings([call("a"), result("a"), result("a")], "unique_tool_ids")
    assert len(violations) == 1
    assert violations[0].message_index == 2


@pytest.mark.parametrize(
    "messages",
    [
        [{"role": "alien", "content": "hello"}],
        [{"content": "hello"}],
        [{"role": "assistant", "content": None}],
        [{"role": "assistant", "content": "  "}],
        [{"role": "assistant", "content": []}],
        [{"role": "assistant", "content": [{"type": "text", "text": " "}]}],
        [{"role": "user", "content": None}],
        [{"role": "user", "content": "hello", "tool_call_id": "a"}],
        [{"role": "tool", "content": "hello"}],
        [{"role": "tool", "content": "hello", "tool_call_id": ""}],
        [call("a"), result("a", None)],
        [call("a"), user(), result("a")],
        [dict(call("a"), role="user"), result("a")],
        [call("")],
        [call("  ")],
        [{"role": "assistant", "tool_calls": [{}]}],
        [user(), {"role": "system", "content": "late"}],
        [user(), {"role": "developer", "content": "late"}],
    ],
)
def test_structure_rejects_invalid_messages(messages):
    assert findings(messages, "structure")


def test_structure_rejects_unknown_call_type():
    messages = [call("a"), result("a")]
    messages[0]["tool_calls"][0]["type"] = "custom"
    assert findings(messages, "structure")


def test_structure_rejects_missing_function_name():
    messages = [call("a"), result("a")]
    messages[0]["tool_calls"][0]["function"]["name"] = ""
    assert findings(messages, "structure")


@pytest.mark.parametrize(
    "message",
    [
        {"role": "assistant", "content": "text"},
        {"role": "assistant", "content": None, "refusal": "I cannot help."},
        {"role": "assistant", "content": [{"type": "image_url", "image_url": {"url": "x"}}]},
        {"role": "assistant", "content": [{"type": "text", "text": "hello"}]},
    ],
)
def test_nonempty_assistant(message):
    assert validate([message]).passed


def test_empty_tool_result_is_valid():
    assert validate([call("a"), result("a", "")]).passed


def test_leading_instruction_block():
    assert validate(
        [
            {"role": "system", "content": "one"},
            {"role": "developer", "content": "two"},
            {"role": "system", "content": "three"},
            user(),
        ]
    ).passed


def test_system_placement_options():
    anywhere = Contract.model_validate({"checks": {"structure": {"system_messages": "anywhere"}}})
    forbidden = Contract.model_validate({"checks": {"structure": {"system_messages": "forbidden"}}})
    assert validate([user(), {"role": "system", "content": "late"}], anywhere).passed
    assert not validate([{"role": "system", "content": "x"}], forbidden).passed


def test_check_validates_after_not_before(pinned):
    assert check(
        ROOT / "fixtures/orphaned_result.json", ROOT / "fixtures/legitimate_compaction.json", pinned
    ).passed


def test_pins_and_legitimate_compaction(pinned):
    assert check(
        ROOT / "fixtures/clean_session.json", ROOT / "fixtures/legitimate_compaction.json", pinned
    ).passed


def test_dropped_constraint_reports_source_index(pinned):
    report = check(
        ROOT / "fixtures/clean_session.json", ROOT / "fixtures/dropped_constraint.json", pinned
    )
    assert [(v.check, v.message_index, v.snapshot, v.pin) for v in report.violations] == [
        ("pinned_content", 0, "before", "system-prompt"),
        ("pinned_content", 0, "before", "no-prod-writes"),
    ]


def test_role_pin_preserves_every_duplicate():
    config = Contract.model_validate({"pins": [{"name": "users", "role": "user"}]})
    assert not check([user(), user()], [user()], config).passed


def test_role_pin_checks_metadata_and_ignores_key_order():
    config = Contract.model_validate({"pins": [{"name": "users", "role": "user"}]})
    assert check(
        [{"role": "user", "content": "x", "name": "a"}],
        [{"name": "a", "content": "x", "role": "user"}],
        config,
    ).passed
    assert not check([{"role": "user", "content": "x", "name": "a"}], [user("x")], config).passed


def test_text_pins_only_enforce_if_present_before():
    config = Contract.model_validate({"pins": [{"name": "rule", "contains": "Never write"}]})
    assert check([user()], [], config).passed
    assert not check([user("Never write")], [], config).passed


def test_text_pin_can_move_roles():
    config = Contract.model_validate({"pins": [{"name": "rule", "contains": "Never write"}]})
    assert check(
        [user("Never write")], [{"role": "assistant", "content": "Never write"}], config
    ).passed


def test_text_pin_is_literal_case_sensitive_and_searches_text_parts():
    config = Contract.model_validate({"pins": [{"name": "rule", "contains": "Never write"}]})
    before = [user("Never write")]
    assert not check(before, [user("never write")], config).passed
    after = [user([{"type": "text", "text": "Never write to production"}])]
    assert check(before, after, config).passed
    after = [call("a"), result("a")]
    after[0]["tool_calls"][0]["function"]["arguments"] = '"Never write"'
    assert not check(before, after, config).passed


def test_each_check_can_be_disabled():
    config = Contract.model_validate(
        {
            "checks": {
                "tool_pairs": False,
                "unique_tool_ids": False,
                "structure": False,
                "pinned_content": False,
            },
            "pins": [{"name": "rule", "contains": "hello"}],
        }
    )
    assert validate([result("a"), result("a"), call("a", "a")], config).passed
    assert check([user()], [], config).passed


def test_warning_severity_does_not_fail():
    config = Contract.model_validate(
        {
            "checks": {
                "tool_pairs": {"severity": "warning"},
                "structure": {"severity": "warning"},
            }
        }
    )
    report = validate([result("a")], config)
    assert report.passed and report.warnings == 1 and report.errors == 0


def test_pin_severity_overrides_check_default():
    config = Contract.model_validate(
        {
            "pins": [
                {"name": "rule", "contains": "hello", "severity": "warning"},
            ]
        }
    )
    report = check([user()], [], config)
    assert report.passed and report.warnings == 1


def test_inputs_are_not_mutated(clean, pinned):
    original = deepcopy(clean)
    check(clean, clean, pinned)
    assert clean == original


def test_snapshot_is_detached_from_mutable_input(clean):
    snapshot = load_snapshot(clean)
    clean[0]["content"] = "changed"
    assert snapshot.messages[0].content != "changed"


def test_role_pins_protect_directly_constructed_neutral_messages():
    contract = Contract.model_validate({"pins": [{"name": "instructions", "role": "system"}]})
    before = Snapshot((Message("system", "keep this"),))
    after = Snapshot((Message("system", "changed"),))
    assert not check(before, after, contract).passed
    assert check(before, before, contract).passed


def test_whitespace_refusal_does_not_make_an_assistant_nonempty():
    assert not validate([{"role": "assistant", "content": None, "refusal": "  "}]).passed


def test_structure_leaves_never_called_results_to_pair_check():
    assert not findings([user(), result("a")], "structure")
    assert findings([user(), result("a")], "tool_pair_integrity")


def test_structure_still_detects_result_before_known_call():
    assert findings([result("a"), call("a")], "structure")


def test_orphan_with_null_content_has_separate_content_error():
    report = validate([result("a", None)])
    assert [v.check for v in report.violations] == ["tool_pair_integrity", "structure"]
    assert "content" in report.violations[1].message


def test_contains_pin_does_not_join_parts():
    contract = Contract.model_validate({"pins": [{"name": "rule", "contains": "Never write"}]})
    split = [user([{"type": "text", "text": "Never "}, {"type": "text", "text": "write"}])]
    assert not check([user("Never write")], split, contract).passed
    assert check(split, [], contract).passed
