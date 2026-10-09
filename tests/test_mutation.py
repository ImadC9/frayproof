import asyncio
import json
import sys
from copy import deepcopy

import pytest
from hypothesis import given
from hypothesis import strategies as st
from typer.testing import CliRunner

from frayproof import Contract, InputError, load_snapshot, validate
from frayproof.cli import app
from frayproof.mutate import run_mutations, run_mutations_async
from frayproof.mutate.mutators import generate_mutations
from frayproof.mutate.target import mutate_target

from .conftest import ROOT, call, result, user


def session():
    return [
        {"role": "system", "content": "Never write to production"},
        user(),
        call("a"),
        result("a"),
        user("Continue"),
    ]


def strong():
    return Contract.model_validate(
        {
            "pins": [
                {"name": "system", "role": "system"},
                {"name": "rule", "contains": "Never write to production"},
                {"name": "users", "role": "user"},
                {"name": "results", "role": "tool"},
            ]
        }
    )


def weak():
    return Contract.model_validate({"checks": {"structure": {"system_messages": "anywhere"}}})


def test_weak_contract_reveals_five_gaps():
    report = run_mutations(session(), lambda messages: messages, weak())
    assert report.baseline.passed
    assert not report.passed
    assert (report.caught, report.survived, report.skipped, report.applicable) == (4, 5, 0, 9)
    assert report.score == 44.44
    assert {m.name for m in report.mutants if m.status == "survived"} == {
        "remove_pinned_text",
        "move_instruction",
        "drop_latest_user",
        "truncate_tool_result",
        "drop_recent_exchange",
    }
    assert "pins" in report.mutants[3].reason
    assert "4/9 caught (44.44%)" in report.to_text()


def test_strong_contract_catches_all_sites():
    report = run_mutations(session(), lambda messages: messages, strong())
    assert report.passed and report.caught == 12 and report.score == 100
    assert all(m.report is not None and not m.report.passed for m in report.mutants)


def test_transform_runs_once_and_in_place_input_cannot_erase_baseline():
    original = session()
    saved = deepcopy(original)
    calls = []

    def transform(messages):
        calls.append(1)
        messages[0]["content"] = "changed"
        return messages

    report = run_mutations(original, transform, strong())
    assert calls == [1] and original == saved
    assert not report.baseline.passed and report.mutants == ()
    assert "BASELINE FAIL" in report.to_text()


def test_each_mutant_starts_from_real_output():
    report = run_mutations(session(), lambda messages: messages, strong())
    duplicate = next(m for m in report.mutants if m.name == "duplicate_tool_id")
    assert {v.check for v in duplicate.report.violations} == {"unique_tool_ids"}
    move = next(m for m in report.mutants if m.name == "move_instruction")
    assert {v.check for v in move.report.violations} == {"structure"}


def test_warning_only_detection_is_a_survivor():
    config = Contract.model_validate(
        {
            "checks": {
                "tool_pairs": {"severity": "warning"},
                "unique_tool_ids": {"severity": "warning"},
                "structure": {"severity": "warning", "system_messages": "anywhere"},
            }
        }
    )
    report = run_mutations(session(), lambda messages: messages, config)
    assert report.caught == 0 and report.survived == 9
    assert report.mutants[0].report.warnings == 1


def test_disabled_pair_check_is_measured_without_empty_assistant_false_positive():
    config = Contract.model_validate({"checks": {"tool_pairs": False}})
    report = run_mutations(session(), lambda messages: messages, config)
    drop = next(m for m in report.mutants if m.name == "drop_tool_call")
    assert drop.status == "survived" and drop.report.violations == ()


def test_pending_policy_can_explain_surviving_result_drop():
    config = Contract.model_validate(
        {
            "checks": {
                "tool_pairs": {
                    "allow_trailing_pending_call": True,
                }
            }
        }
    )
    report = run_mutations([call("a"), result("a")], lambda messages: messages, config)
    assert next(m for m in report.mutants if m.name == "drop_tool_result").status == "survived"


def test_no_applicable_mutants_is_not_perfect_coverage():
    report = run_mutations([], lambda messages: messages)
    assert not report.passed and report.score is None
    assert report.applicable == 0 and report.skipped == 9
    assert all(m.reason for m in report.mutants)
    assert "no contract coverage" in report.to_text()


def test_mutators_do_not_crash_when_structure_is_explicitly_disabled():
    contract = Contract.model_validate({"checks": {"structure": False}})
    report = run_mutations([{"content": "No role"}], lambda raw: raw, contract)
    assert report.baseline.passed and report.skipped == 9


def test_skips_do_not_inflate_denominator():
    report = run_mutations([call("a"), result("a"), user()], lambda messages: messages)
    assert report.applicable == 6 and report.skipped == 3 and report.score == 66.67
    assert not report.passed


def test_json_is_deterministic_and_source_locations_are_available():
    first = run_mutations(session(), lambda messages: messages, weak())
    second = run_mutations(session(), lambda messages: messages, weak())
    assert first.to_json() == second.to_json()
    data = json.loads(first.to_json())
    assert data["kind"] == "mutation" and data["schema_version"] == 1
    assert data["mutants"][0]["message_index"] == 2
    assert data["mutants"][0]["report"]["violations"][0]["message_index"] == 2


@pytest.mark.parametrize(
    "contract",
    [
        {"pins": [{"name": "rule", "contains": "Never write to production"}]},
        {"pins": [{"name": "system", "role": "system"}]},
        {"checks": {"pinned_content": False}, "pins": [{"name": "system", "role": "system"}]},
    ],
)
def test_text_mutation_uses_declared_selectors_even_when_disabled(contract):
    report = run_mutations(session(), lambda messages: messages, Contract.model_validate(contract))
    mutation = next(m for m in report.mutants if m.name == "remove_pinned_text")
    assert "pin '" in mutation.description
    expected = "survived" if contract.get("checks") else "caught"
    assert mutation.status == expected


def test_removing_all_text_copies_really_breaks_presence_pin():
    messages = session() + [user("Never write to production")]
    report = run_mutations(messages, lambda raw: raw, strong())
    assert next(m for m in report.mutants if m.name == "remove_pinned_text").status == "caught"


def test_text_blocks_are_mutated_and_multimodal_metadata_is_retained():
    messages = session()
    messages[0]["content"] = [
        {"type": "text", "text": "Never write to production"},
        {"type": "image_url", "image_url": {"url": "https://example.invalid/image"}},
    ]
    report = run_mutations(messages, lambda raw: raw, strong())
    assert report.caught == 12


def test_absent_before_pin_is_not_mutation_coverage():
    config = Contract.model_validate({"pins": [{"name": "missing", "contains": "absent"}]})
    report = run_mutations([user()], lambda raw: raw, config)
    assert next(m for m in report.mutants if m.name == "remove_pinned_text").status == "skipped"


def test_role_pin_without_text_is_explicit_skip():
    config = Contract.model_validate({"pins": [{"name": "calls", "role": "assistant"}]})
    report = run_mutations([call("a"), result("a"), user()], lambda raw: raw, config)
    assert next(m for m in report.mutants if m.name == "remove_pinned_text").status == "skipped"


def test_role_text_operator_selects_preserved_message_rather_than_new_message():
    config = Contract.model_validate({"pins": [{"name": "original", "role": "system"}]})
    before = session()
    output = [{"role": "system", "content": "New instruction."}] + deepcopy(before)
    report = run_mutations(before, lambda raw: output, config)
    mutant = next(m for m in report.mutants if m.name == "remove_pinned_text")
    assert mutant.status == "caught" and mutant.message_index == 1


def test_drop_call_preserves_an_assistants_existing_text():
    messages = [dict(call("a"), content="Read it"), result("a"), user()]
    report = run_mutations(messages, lambda raw: raw)
    drop = report.mutants[0]
    assert drop.report.violations[0].message_index == 1
    assert [v.check for v in drop.report.violations] == ["tool_pair_integrity"]


def test_parallel_call_and_result_mutations():
    messages = [call("a", "b"), result("b"), result("a"), user()]
    report = run_mutations(messages, lambda raw: raw)
    assert not report.passed and report.caught == 8
    assert report.applicable == 11


@pytest.mark.parametrize("output", [None, "not messages", {}, ["not a message"]])
def test_invalid_target_output_is_input_error(output):
    with pytest.raises(InputError):
        run_mutations([user()], lambda raw: output)


def test_runtime_failure_is_input_error():
    def broken(raw):
        raise RuntimeError("planted failure")

    with pytest.raises(InputError, match="Transformation failed: RuntimeError"):
        run_mutations([user()], broken)


def test_async_compactor_runs_once():
    calls = []

    async def compact(raw):
        await asyncio.sleep(0)
        calls.append(1)
        return raw

    report = asyncio.run(run_mutations_async(session(), compact, strong()))
    assert report.passed and calls == [1]
    with pytest.raises(InputError, match="run_mutations_async"):
        run_mutations(session(), compact, strong())


def test_async_api_can_wrap_sync_transforms():
    assert asyncio.run(run_mutations_async(session(), lambda raw: raw, strong())).passed


def test_async_runtime_failure():
    async def broken(raw):
        raise RuntimeError("planted failure")

    with pytest.raises(InputError, match="Transformation failed"):
        asyncio.run(run_mutations_async([user()], broken))


def test_target_file_supports_sibling_imports_and_restores_path(tmp_path):
    target = tmp_path / "compactor.py"
    (tmp_path / "frayproof_test_sibling.py").write_text("VALUE = 1\n", encoding="utf-8")
    target.write_text(
        "from frayproof_test_sibling import VALUE\ndef compact(messages):\n"
        "    assert VALUE == 1\n    return messages\n",
        encoding="utf-8",
    )
    previous = sys.path[:]
    report = mutate_target(f"{target}:compact", session(), strong())
    assert report.passed and sys.path == previous
    sys.modules.pop("frayproof_test_sibling", None)


def test_target_module_import(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    report = mutate_target(
        "examples.mutation_compactor:compact",
        ROOT / "fixtures/mutation_session.json",
        ROOT / "examples/mutation_contract.yaml",
    )
    assert report.passed


@pytest.mark.parametrize(
    "target",
    [
        "missing",
        ":compact",
        "module:",
        "module:not.valid",
        "missing.py:compact",
        "does_not_exist:compact",
    ],
)
def test_bad_target_specs(target):
    with pytest.raises(InputError):
        mutate_target(target, session())


def test_noncallable_and_missing_attribute(tmp_path):
    path = tmp_path / "target.py"
    path.write_text("compact = 3\n", encoding="utf-8")
    with pytest.raises(InputError, match="not callable"):
        mutate_target(f"{path}:compact", session())
    with pytest.raises(InputError, match="Cannot import target"):
        mutate_target(f"{path}:missing", session())


def test_cli_async_file(tmp_path):
    path = tmp_path / "target.py"
    path.write_text("async def compact(messages):\n    return messages\n", encoding="utf-8")
    source = tmp_path / "input.json"
    source.write_text(json.dumps(session()), encoding="utf-8")
    config = tmp_path / "contract.yaml"
    config.write_text(strong().model_dump_json(), encoding="utf-8")
    outcome = CliRunner().invoke(
        app,
        [
            "mutate",
            "--target",
            f"{path}:compact",
            "--input",
            str(source),
            "--contract",
            str(config),
        ],
    )
    assert outcome.exit_code == 0, outcome.output


@pytest.mark.parametrize("contract,expected", [("weak_contract", 1), ("mutation_contract", 0)])
def test_cli_mutation_examples(monkeypatch, contract, expected):
    monkeypatch.chdir(ROOT)
    outcome = CliRunner().invoke(
        app,
        [
            "mutate",
            "--target",
            "examples/mutation_compactor.py:compact",
            "--input",
            "fixtures/mutation_session.json",
            "--contract",
            f"examples/{contract}.yaml",
            "--format",
            "json",
        ],
    )
    assert outcome.exit_code == expected, outcome.output
    data = json.loads(outcome.stdout)
    assert data["caught"] == (12 if expected else 20)
    assert data["applicable"] == 20 and data["skipped"] == 0


def test_cli_baseline_failure(tmp_path):
    target = tmp_path / "identity.py"
    target.write_text("def compact(messages):\n    return messages\n", encoding="utf-8")
    outcome = CliRunner().invoke(
        app,
        [
            "mutate",
            "--target",
            f"{target}:compact",
            "--input",
            str(ROOT / "fixtures/orphaned_result.json"),
            "--format",
            "json",
        ],
    )
    assert outcome.exit_code == 1
    data = json.loads(outcome.stdout)
    assert not data["baseline"]["passed"] and data["mutants"] == []


def test_dropping_an_unanswered_call_is_not_an_applicable_orphan_mutant():
    config = Contract.model_validate(
        {
            "checks": {
                "tool_pairs": {
                    "allow_trailing_pending_call": True,
                }
            }
        }
    )
    report = run_mutations([call("pending")], lambda raw: raw, config)
    assert report.mutants[0].status == "skipped"
    assert "answered" in report.mutants[0].reason


def test_deleting_a_repeated_call_would_not_create_an_orphan():
    config = Contract.model_validate({"checks": {"unique_tool_ids": False}})
    report = run_mutations([call("a", "a"), result("a"), user()], lambda raw: raw, config)
    assert report.baseline.passed and report.mutants[0].status == "skipped"


def test_deleting_one_of_two_results_would_not_leave_a_call_unanswered():
    config = Contract.model_validate({"checks": {"unique_tool_ids": False}})
    report = run_mutations([call("a"), result("a"), result("a"), user()], lambda raw: raw, config)
    assert report.baseline.passed and report.mutants[1].status == "skipped"


def test_cli_bad_target_json_is_input_error():
    outcome = CliRunner().invoke(
        app,
        [
            "mutate",
            "--target",
            "missing.py:compact",
            "--input",
            str(ROOT / "fixtures/clean_session.json"),
            "--format",
            "json",
        ],
    )
    assert outcome.exit_code == 2 and "error" in json.loads(outcome.stdout)


@given(st.integers(min_value=1, max_value=8), st.booleans())
def test_generated_parallel_batches_have_stable_coverage(size, reverse):
    ids = [f"call_{i}" for i in range(size)]
    order = list(reversed(ids)) if reverse else ids
    messages = [session()[0], user(), call(*ids), *[result(i) for i in order], user()]
    assert run_mutations(messages, lambda raw: raw, strong()).caught == 6 * size + 6


def test_every_sequential_and_parallel_call_is_challenged():
    messages = [
        user(),
        call("a"),
        result("a"),
        user("Next"),
        call("b", "c"),
        result("c"),
        result("b"),
        user("Finish"),
    ]
    report = run_mutations(messages, lambda raw: raw)
    for name in ["drop_tool_call", "drop_tool_result", "duplicate_tool_id", "swap_call_result"]:
        mutants = [m for m in report.mutants if m.name == name]
        assert len(mutants) == 3 and all(m.status == "caught" for m in mutants)
    assert {m.sites[0] for m in report.mutants if m.name == "drop_tool_call"} == {
        "after[1].tool_calls[0]",
        "after[4].tool_calls[0]",
        "after[4].tool_calls[1]",
    }
    assert report.operators["truncate_tool_result"] == {"caught": 0, "survived": 3, "skipped": 0}


def test_each_contains_pin_and_exact_role_occurrence_has_a_site():
    messages = [user("Keep Alpha."), user("Keep Beta.")]
    config = Contract.model_validate(
        {
            "pins": [
                {"name": "alpha", "contains": "Alpha"},
                {"name": "beta", "contains": "Beta"},
                {"name": "users", "role": "user"},
            ]
        }
    )
    report = run_mutations(messages, lambda raw: raw, config)
    mutants = [m for m in report.mutants if m.name == "remove_pinned_text"]
    assert len(mutants) == 4 and all(m.status == "caught" for m in mutants)
    assert {site for m in mutants for site in m.sites} == {
        "pin:alpha",
        "pin:beta",
        "pin:users@after[0]",
        "pin:users@after[1]",
    }


def test_identical_pin_corruptions_count_once_with_all_sites():
    messages = [user("Alpha"), user("Alpha")]
    config = Contract.model_validate(
        {
            "pins": [
                {"name": "first", "contains": "Alpha"},
                {"name": "second", "contains": "Alpha"},
                {"name": "users", "role": "user"},
            ]
        }
    )
    report = run_mutations(messages, lambda raw: raw, config)
    mutants = [m for m in report.mutants if m.name == "remove_pinned_text"]
    assert len(mutants) == 3
    assert mutants[0].sites == ("pin:first", "pin:second")
    assert all(m.status == "caught" for m in mutants)


def test_new_loss_operators_pass_default_checks_and_are_independent():
    messages = [
        user("Earlier"),
        call("a", "b"),
        result("a"),
        result("b"),
        user("Latest"),
        {"role": "assistant", "content": "Working"},
    ]
    before = load_snapshot(messages)
    saved = deepcopy(messages)
    mutants = generate_mutations(messages, before, before, Contract())
    losses = [
        m
        for m in mutants
        if m.name in {"drop_latest_user", "truncate_tool_result", "drop_recent_exchange"}
    ]
    assert len(losses) == 4
    assert all(validate(m.messages).passed for m in losses)
    assert messages == saved
    latest = next(m for m in losses if m.name == "drop_latest_user")
    assert latest.messages == saved[:4] + saved[5:]
    exchange = next(m for m in losses if m.name == "drop_recent_exchange")
    assert exchange.messages == saved[4:]
    for mutant in (m for m in losses if m.name == "truncate_tool_result"):
        assert mutant.messages[mutant.message_index]["content"] == "o"
        assert (
            mutant.messages[mutant.message_index]["tool_call_id"]
            == saved[mutant.message_index]["tool_call_id"]
        )


def test_result_truncation_preserves_blocks_and_opaque_metadata():
    messages = [
        call("a"),
        {
            "role": "tool",
            "tool_call_id": "a",
            "content": [
                {"type": "text", "text": "abcdef"},
                {"type": "text", "text": "x"},
                {"type": "image_url", "image_url": {"url": "https://example.invalid/image"}},
            ],
            "custom": {"keep": True},
        },
    ]
    snapshot = load_snapshot(messages)
    truncated = next(
        m
        for m in generate_mutations(messages, snapshot, snapshot, Contract())
        if m.name == "truncate_tool_result"
    )
    assert truncated.messages[1]["content"][0]["text"] == "abc"
    assert truncated.messages[1]["content"][1:] == messages[1]["content"][1:]
    assert truncated.messages[1]["custom"] == messages[1]["custom"]
    messages[1]["content"] = "x"
    report = run_mutations(messages, lambda raw: raw)
    assert report.operators["truncate_tool_result"]["skipped"] == 1


def test_all_instruction_sites_and_closed_exchanges_are_generated():
    messages = [
        session()[0],
        {"role": "developer", "content": "Keep the tests"},
        user("First"),
        {"role": "assistant", "content": "Answer one"},
        user("Second"),
        {"role": "assistant", "content": "Answer two"},
        user("Latest"),
    ]
    report = run_mutations(messages, lambda raw: raw, weak())
    assert report.operators["remove_pinned_text"]["survived"] == 2
    assert report.operators["move_instruction"]["survived"] == 2
    exchanges = [m for m in report.mutants if m.name == "drop_recent_exchange"]
    assert [m.sites for m in exchanges] == [("after[2:4]",), ("after[4:6]",)]


def test_exchange_loss_keeps_instructions_and_does_not_drop_open_turns():
    messages = [
        user("First"),
        {"role": "developer", "content": "Rule"},
        {"role": "assistant", "content": "Reply"},
        user("Second"),
        user("Latest"),
    ]
    snapshot = load_snapshot(messages)
    mutants = generate_mutations(messages, snapshot, snapshot, weak())
    exchanges = [m for m in mutants if m.name == "drop_recent_exchange"]
    assert len(exchanges) == 1 and exchanges[0].messages == messages[1:2] + messages[3:]


def test_instruction_only_output_has_no_latest_user_site():
    report = run_mutations([session()[0]], lambda raw: raw)
    assert report.operators["drop_latest_user"]["skipped"] == 1
