"""Session-independent retention, including duplicate turns and opaque content."""

import asyncio
import json
from copy import deepcopy

import pytest
from hypothesis import given
from hypothesis import strategies as st
from typer.testing import CliRunner

from frayproof import Contract, ContractViolation, InputError, check, guard, load_contract, validate
from frayproof.cli import app
from frayproof.mutate import run_mutations

from .conftest import ROOT, call, result, user


def policy(**rules):
    return Contract.model_validate({"retain": rules})


def history():
    return [
        user("Old request"),
        call("old"),
        result("old", "Old result"),
        user("Recent one"),
        call("one"),
        result("one", "First result"),
        user("Recent two"),
        call("two"),
        result("two", "Second result"),
        user("Latest request"),
    ]


def retention_findings(before, after, contract):
    return [v for v in check(before, after, contract).violations if v.check == "retention"]


@pytest.mark.parametrize(
    "rules",
    [
        {"latest_user_message": "exact"},
        {"recent_exchanges": 2},
        {"tool_results": "complete"},
    ],
)
def test_active_retention_requires_before(rules):
    with pytest.raises(InputError, match="before snapshot"):
        validate([], policy(**rules))
    disabled = Contract.model_validate({"retain": rules, "checks": {"retention": False}})
    assert validate([], disabled).passed


def test_empty_and_inactive_rules_preserve_defaults():
    assert validate([], policy()).passed
    assert validate(
        [], policy(recent_exchanges=0, latest_user_message=None, tool_results=None)
    ).passed
    assert not Contract().retain.active
    assert check(
        [], [], policy(latest_user_message="exact", recent_exchanges=2, tool_results="complete")
    ).passed


@pytest.mark.parametrize(
    "rules",
    [
        {"latest_user_message": True},
        {"latest_user_message": "contains"},
        {"recent_exchanges": True},
        {"recent_exchanges": -1},
        {"recent_exchanges": 1.5},
        {"recent_exchanges": "2"},
        {"recent_exchanges": None},
        {"tool_results": True},
        {"tool_results": "shortened"},
        {"unknown": "exact"},
    ],
)
def test_invalid_retention_yaml_is_input_error(tmp_path, rules):
    path = tmp_path / "contract.yaml"
    path.write_text(json.dumps({"retain": rules}), encoding="utf-8")
    with pytest.raises(InputError):
        load_contract(path)


def test_duplicate_retention_yaml_keys_are_rejected(tmp_path):
    path = tmp_path / "contract.yaml"
    path.write_text("retain:\n  recent_exchanges: 1\n  recent_exchanges: 2\n", encoding="utf-8")
    with pytest.raises(InputError, match="Duplicate"):
        load_contract(path)


def test_latest_user_is_resolved_from_before_and_remains_latest():
    before = [user("Old"), user("Keep me"), {"role": "assistant", "content": "Reply"}]
    config = policy(latest_user_message="exact")
    assert check(before, before[1:], config).passed
    assert check(before, before + [{"role": "assistant", "content": "More"}], config).passed
    for after in [before[:1], [], before + [user("New request")], [user("Keep me"), user("Old")]]:
        findings = retention_findings(before, after, config)
        assert len(findings) == 1 and findings[0].message_index == 1
        assert findings[0].snapshot == "before" and findings[0].rule == "latest_user_message"


def test_latest_exact_preserves_content_parts_and_metadata():
    before = [
        dict(
            user(
                [
                    {"type": "text", "text": "Question"},
                    {"type": "image_url", "image_url": {"url": "image"}},
                ]
            ),
            name="human",
            metadata={"id": 5},
        )
    ]
    config = policy(latest_user_message="exact")
    assert check(before, [dict(reversed(list(before[0].items())))], config).passed
    for edit in [lambda m: m.update(metadata={"id": 6}), lambda m: m["content"].reverse()]:
        after = deepcopy(before)
        edit(after[0])
        assert not check(before, after, config).passed


def test_recent_window_allows_older_compaction_and_keeps_two_closed_exchanges():
    before = history()
    config = policy(recent_exchanges=2)
    assert check(before, before[3:], config).passed
    assert check(before, before[3:-1], config).passed  # latest has a separate selector
    for after in [before[6:], before[3:6] + before[9:], before[6:9] + before[3:6] + before[9:]]:
        findings = retention_findings(before, after, config)
        assert findings and all(v.rule == "recent_exchanges" for v in findings)
    findings = retention_findings(before, [], config)
    assert [v.message_index for v in findings] == [3, 6]


def test_one_recent_exchange_does_not_protect_an_older_one():
    before = history()
    assert check(before, before[6:], policy(recent_exchanges=1)).passed
    assert not check(before, before[6:], policy(recent_exchanges=20)).passed
    assert check(before, before, policy(recent_exchanges=20)).passed


def test_recent_exchange_is_contiguous_and_preserves_all_source_fields():
    before = history()
    config = policy(recent_exchanges=1)
    after = deepcopy(before[6:])
    after.insert(1, {"role": "assistant", "content": "Injected summary"})
    assert retention_findings(before, after, config)
    after = deepcopy(before[6:])
    after[1]["tool_calls"][0]["function"]["arguments"] = '{"changed":true}'
    assert retention_findings(before, after, config)
    assert check(
        before, [{"role": "assistant", "content": "Older summary"}] + before[6:], config
    ).passed


def test_repeated_identical_exchanges_cannot_share_one_match():
    exchange = [user("Same"), {"role": "assistant", "content": "Same reply"}]
    before = exchange * 2 + [user("End")]
    config = policy(recent_exchanges=2)
    assert check(before, before, config).passed
    findings = retention_findings(before, exchange + [user("End")], config)
    assert len(findings) == 1 and findings[0].message_index == 2


def test_empty_user_turns_and_open_final_exchange_do_not_shift_closed_window():
    before = [
        user("Keep"),
        {"role": "assistant", "content": "Answer"},
        user("Empty"),
        user("Latest"),
        {"role": "assistant", "content": "Open answer"},
    ]
    config = policy(recent_exchanges=1)
    assert not check(before, before[2:], config).passed
    assert check(before, before[:2], config).passed
    assert check([user("Only"), {"role": "assistant", "content": "Reply"}], [], config).passed


@pytest.mark.parametrize("replacement", ["First", "Altered result", "First result plus more", ""])
def test_complete_result_requires_exact_content_not_just_length(replacement):
    before = history()
    after = deepcopy(before[3:])
    after[2]["content"] = replacement
    findings = retention_findings(before, after, policy(tool_results="complete"))
    assert len(findings) == 1
    assert findings[0].message_index == 2 and findings[0].snapshot == "after"
    assert findings[0].tool_call_id == "one" and findings[0].rule == "tool_results"


def test_complete_results_allow_dropped_exchanges_and_new_tool_results():
    before = history()
    after = before[6:] + [call("new"), result("new", "New output")]
    assert check(before, after, policy(tool_results="complete")).passed
    assert check(before, [], policy(tool_results="complete")).passed
    after = deepcopy(before)
    after[5]["extra_metadata"] = "changed"
    assert check(before, after, policy(tool_results="complete")).passed


def test_complete_result_blocks_are_compared_as_whole_content():
    before = [
        call("a"),
        result(
            "a",
            [
                {"type": "text", "text": "abc"},
                {"type": "image_url", "image_url": {"url": "opaque"}},
            ],
        ),
    ]
    config = policy(tool_results="complete")
    assert check(before, deepcopy(before), config).passed
    after = deepcopy(before)
    after[1]["content"][1]["image_url"]["url"] = "changed"
    assert retention_findings(before, after, config)


def test_retention_can_warn_or_be_disabled_without_disabling_pins():
    before = [user("Latest")]
    config = Contract.model_validate(
        {
            "retain": {"latest_user_message": "exact"},
            "checks": {"retention": {"severity": "warning"}},
        }
    )
    report = check(before, [], config)
    assert report.passed and report.warnings == 1
    assert 'rule="latest_user_message"' in report.to_text()
    assert report.to_dict()["violations"][0]["rule"] == "latest_user_message"
    disabled = Contract.model_validate(
        {
            "retain": {"latest_user_message": "exact"},
            "checks": {"retention": False},
            "pins": [{"name": "users", "role": "user"}],
        }
    )
    assert [v.check for v in check(before, [], disabled).violations] == ["pinned_content"]


def test_guard_and_cli_enforce_dynamic_retention(tmp_path):
    config = policy(latest_user_message="exact")

    @guard(config)
    async def compact(messages):
        messages[-1]["content"] = "Changed"
        return messages

    with pytest.raises(ContractViolation, match="retention"):
        asyncio.run(compact([user("Original")]))
    before, after, path = (
        tmp_path / name for name in ["before.json", "after.json", "contract.yaml"]
    )
    before.write_text(json.dumps([user("Original")]), encoding="utf-8")
    after.write_text("[]", encoding="utf-8")
    path.write_text("retain:\n  latest_user_message: exact\n", encoding="utf-8")
    outcome = CliRunner().invoke(
        app,
        [
            "check",
            "--before",
            str(before),
            "--after",
            str(after),
            "--contract",
            str(path),
            "--format",
            "json",
        ],
    )
    assert outcome.exit_code == 1
    assert json.loads(outcome.stdout)["violations"][0]["rule"] == "latest_user_message"


@given(st.lists(st.text(min_size=2, max_size=40), min_size=3, max_size=3))
def test_reusable_contract_catches_losses_with_unpredictable_session_content(texts):
    # No literal pins: exactly these rules work for arbitrary request/result text.
    before = [user(texts[0]), call("a"), result("a", texts[1]), user(texts[2])]
    config = policy(latest_user_message="exact", recent_exchanges=1, tool_results="complete")
    report = run_mutations(before, lambda raw: raw, config)
    for name in ["drop_latest_user", "truncate_tool_result", "drop_recent_exchange"]:
        assert report.operators[name] == {"caught": 1, "survived": 0, "skipped": 0}


def test_demo_contract_has_no_fixture_text_and_all_losses_are_caught():
    from examples.mutation_compactor import compact

    config = load_contract(ROOT / "examples/mutation_contract.yaml")
    assert len(config.pins) == 1 and config.pins[0].role == "system"
    assert all(pin.contains is None for pin in config.pins)
    report = run_mutations(ROOT / "fixtures/mutation_session.json", compact, config)
    assert report.passed and report.caught == report.applicable == 20


def test_latest_occurrence_cannot_be_borrowed_from_a_retained_exchange():
    before = [user("Continue"), {"role": "assistant", "content": "Response"}, user("Continue")]
    config = policy(latest_user_message="exact", recent_exchanges=1)
    report = check(before, before[:-1], config)
    assert [v.rule for v in report.violations] == ["latest_user_message"]


def test_recent_selection_cannot_be_shifted_by_new_output_exchanges():
    before = history()
    after = before[6:] + [call("new"), result("new"), user("New latest")]
    findings = retention_findings(before, after, policy(recent_exchanges=2))
    assert len(findings) == 1 and findings[0].message_index == 3


def test_identical_latest_messages_without_other_anchors_are_indistinguishable():
    # Explicit limit: exact JSON equality cannot establish an occurrence's origin.
    before = [user("Continue"), {"role": "assistant", "content": "Response"}, user("Continue")]
    assert check(before, before[:-1], policy(latest_user_message="exact")).passed


@pytest.mark.parametrize("mode", [False, {"severity": "warning"}])
def test_mutation_score_respects_retention_switch_and_severity(mode):
    config = Contract.model_validate(
        {
            "retain": {
                "latest_user_message": "exact",
                "recent_exchanges": 3,
                "tool_results": "complete",
            },
            "checks": {"retention": mode},
        }
    )
    report = run_mutations(history(), lambda raw: raw, config)
    for name in ["drop_latest_user", "truncate_tool_result", "drop_recent_exchange"]:
        assert report.operators[name]["caught"] == 0
        assert report.operators[name]["survived"] > 0


@pytest.mark.parametrize("loss", ["latest", "result", "exchange"])
def test_real_retention_loss_fails_baseline_before_mutants(loss):
    def broken(raw):
        if loss == "latest":
            return raw[:-1]
        if loss == "exchange":
            return raw[6:]
        raw[5]["content"] = "Shortened"
        return raw

    config = policy(latest_user_message="exact", recent_exchanges=2, tool_results="complete")
    report = run_mutations(history(), broken, config)
    assert not report.baseline.passed and report.mutants == ()
    assert {v.check for v in report.baseline.violations} == {"retention"}


def test_retention_with_partial_parallel_pending_batch():
    before = [
        user("Closed"),
        call("old"),
        result("old"),
        user("Latest"),
        call("a", "b"),
        result("a"),
    ]
    config = Contract.model_validate(
        {
            "retain": {
                "latest_user_message": "exact",
                "recent_exchanges": 1,
                "tool_results": "complete",
            },
            "checks": {"tool_pairs": {"allow_trailing_pending_call": True}},
        }
    )
    assert check(before, deepcopy(before), config).passed
    after = deepcopy(before)
    after[-1]["content"] = "o"
    assert [v.rule for v in check(before, after, config).violations] == ["tool_results"]
