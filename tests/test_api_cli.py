import asyncio
import json
import logging
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from frayproof import Contract, ContractViolation, ContractWarning, check, guard
from frayproof.cli import app
from frayproof.testing import assert_contract

from .conftest import ROOT, call, result, user

runner = CliRunner()


def test_report_deterministic_json_and_text():
    report = check([], [result("a")])
    assert report.to_json() == check([], [result("a")]).to_json()
    data = json.loads(report.to_json())
    assert data["schema_version"] == 1
    assert not data["passed"] and data["errors"] == 1
    assert data["violations"][0]["message_index"] == 0
    assert data["violations"][0]["snapshot"] == "after"
    assert 'tool_call_id="a"' in report.to_text()


def test_report_pin_name_and_pass_text():
    config = Contract.model_validate({"pins": [{"name": "hello", "contains": "hello"}]})
    assert 'pin="hello"' in check([user()], [], config).to_text()
    assert check([], []).to_text() == "PASS: 0 error(s), 0 warning(s)"


def test_guard_raises_on_orphan():
    @guard()
    def compact(messages):
        return messages[1:]

    with pytest.raises(ContractViolation) as exc:
        compact([call("a"), result("a")])
    assert exc.value.report.errors == 1


def test_guard_captures_before_in_place_and_keyword_args(pinned, clean):
    @guard(pinned)
    def compact(messages, *, keep_last=2):
        messages[0]["content"] = "changed"
        return messages

    with pytest.raises(ContractViolation):
        compact(messages=clean, keep_last=1)


def test_guard_preserves_name_and_output_identity(clean):
    @guard()
    def compact(messages):
        """Keep all messages."""
        return messages

    assert compact(clean) is clean
    assert compact.__name__ == "compact" and compact.__doc__ == "Keep all messages."


def test_guard_warns_and_returns():
    @guard(on_violation="warn")
    def compact(messages):
        return messages[1:]

    with pytest.warns(ContractWarning, match="FAIL"):
        assert compact([call("a"), result("a")]) == [result("a")]


def test_guard_logs(caplog):
    @guard(on_violation="log")
    def compact(messages):
        return messages[1:]

    with caplog.at_level(logging.ERROR, logger="frayproof"):
        compact([call("a"), result("a")])
    assert "tool_pair_integrity" in caplog.text


def test_warning_only_guard_does_not_raise():
    config = Contract.model_validate(
        {"checks": {"tool_pairs": False, "structure": {"severity": "warning"}}}
    )

    @guard(config)
    def compact(messages):
        return messages

    assert compact([result("a")]) == [result("a")]


def test_async_guard_checks_after_await(pinned, clean):
    @guard(pinned)
    async def compact(messages):
        await asyncio.sleep(0)
        messages[0]["content"] = "changed"
        return messages

    with pytest.raises(ContractViolation):
        asyncio.run(compact(clean))


def test_async_guard_success():
    @guard()
    async def compact(messages):
        return messages

    assert asyncio.run(compact([user()])) == [user()]


def test_guard_configuration_errors():
    with pytest.raises(ValueError, match="on_violation"):
        guard(on_violation="ignore")
    with pytest.raises(TypeError, match="first parameter"):
        guard()(lambda: [])


def test_assert_contract_passes_and_fails():
    assert_contract([], [user()])
    with pytest.raises(AssertionError, match="after\\[0\\]"):
        assert_contract([], [result("a")])


@pytest.mark.parametrize("fixture,exit_code", [("clean_session", 0), ("orphaned_result", 1)])
def test_cli_validate(fixture, exit_code):
    outcome = runner.invoke(app, ["validate", "--snapshot", str(ROOT / f"fixtures/{fixture}.json")])
    assert outcome.exit_code == exit_code, outcome.output
    assert ("PASS" if exit_code == 0 else "FAIL") in outcome.stdout


def test_cli_check_json():
    outcome = runner.invoke(
        app,
        [
            "check",
            "--before",
            str(ROOT / "fixtures/clean_session.json"),
            "--after",
            str(ROOT / "fixtures/dropped_constraint.json"),
            "--contract",
            str(ROOT / "examples/contract.yaml"),
            "--format",
            "json",
        ],
    )
    assert outcome.exit_code == 1, outcome.output
    assert json.loads(outcome.stdout)["violations"][0]["pin"] == "system-prompt"


def test_cli_legitimate_compaction():
    outcome = runner.invoke(
        app,
        [
            "check",
            "--before",
            str(ROOT / "fixtures/clean_session.json"),
            "--after",
            str(ROOT / "fixtures/legitimate_compaction.json"),
            "--contract",
            str(ROOT / "examples/contract.yaml"),
        ],
    )
    assert outcome.exit_code == 0, outcome.output


@pytest.mark.parametrize("format_", ["text", "json"])
def test_cli_bad_input(format_, tmp_path):
    outcome = runner.invoke(
        app, ["validate", "--snapshot", str(tmp_path / "missing.json"), "--format", format_]
    )
    assert outcome.exit_code == 2
    if format_ == "json":
        assert "error" in json.loads(outcome.stdout)
    else:
        assert "INPUT ERROR" in outcome.stderr
        assert outcome.stdout == ""


def test_cli_bad_contract(tmp_path):
    path = tmp_path / "contract.yaml"
    path.write_text("version: 2", encoding="utf-8")
    outcome = runner.invoke(
        app,
        [
            "validate",
            "--snapshot",
            str(ROOT / "fixtures/clean_session.json"),
            "--contract",
            str(path),
        ],
    )
    assert outcome.exit_code == 2


def test_cli_warning_exit_zero(tmp_path):
    path = tmp_path / "contract.yaml"
    path.write_text("checks:\n  tool_pairs:\n    severity: warning\n", encoding="utf-8")
    outcome = runner.invoke(
        app,
        [
            "validate",
            "--snapshot",
            str(ROOT / "fixtures/pending_batch.json"),
            "--contract",
            str(path),
        ],
    )
    assert outcome.exit_code == 0, outcome.output
    assert "1 warning(s)" in outcome.stdout


def test_cli_help_version_and_usage_errors():
    assert runner.invoke(app, ["--version"]).stdout.strip() == "Frayproof 0.1.0"
    assert runner.invoke(app, ["--help"]).exit_code == 0
    assert runner.invoke(app, ["validate"]).exit_code == 2
    assert runner.invoke(app, ["validate", "--snapshot", "x", "--format", "xml"]).exit_code == 2


def test_python_module_entrypoint():
    outcome = subprocess.run(
        [sys.executable, "-m", "frayproof", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert outcome.stdout.strip() == "Frayproof 0.1.0"


def test_toy_agent_runs():
    outcome = subprocess.run(
        [sys.executable, str(ROOT / "examples/toy_agent.py")],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Safe compaction: 6 -> 3 messages" in outcome.stdout
    assert "Broken compaction blocked" in outcome.stdout
