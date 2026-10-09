"""Verify review defects and SDK nulls against the installed package, outside the checkout."""

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from frayproof import Contract, ContractViolation, InputError, check, guard, load_snapshot, validate
from frayproof.model import Snapshot
from frayproof.mutate import run_mutations

ROOT = Path(__file__).resolve().parents[1]


def main():
    before = load_snapshot(
        [
            {"role": "user", "content": "Original", "provider": {"important": True}},
            {"role": "assistant", "content": "Original reply"},
            {"role": "user", "content": "Latest"},
        ]
    )
    after = Snapshot(tuple(replace(m, content="Changed") for m in before.messages))
    for policy in [
        {"pins": [{"name": "users", "role": "user"}]},
        {"retain": {"latest_user_message": "exact"}},
        {"retain": {"recent_exchanges": 1}},
    ]:
        config = Contract.model_validate(policy)
        assert check(before, before, config).passed
        assert not check(before, after, config).passed
    assert json.loads(after.messages[0].identity)["provider"] == {"important": True}

    @guard(Contract.model_validate({"retain": {"latest_user_message": "exact"}}))
    def change(snapshot):
        return Snapshot(tuple(replace(m, content="Changed") for m in snapshot.messages))

    try:
        change(before)
    except ContractViolation:
        pass
    else:
        raise AssertionError("Guard accepted changed protected content")

    for discriminator in [[], {}]:
        try:
            validate([{"role": "assistant", "content": [{"type": discriminator}]}])
        except InputError:
            pass
        else:
            raise AssertionError("Malformed block was accepted")
    outcome = subprocess.run(
        [
            sys.executable,
            "-m",
            "frayproof",
            "validate",
            "--snapshot",
            str(ROOT / "fixtures/malformed_content.json"),
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert outcome.returncode == 2 and not outcome.stderr
    assert "error" in json.loads(outcome.stdout)

    config = Contract.model_validate({"pins": [{"name": "keep", "contains": "aba"}]})
    report = run_mutations([{"role": "system", "content": "aababa"}], lambda raw: raw, config)
    assert report.passed and report.caught == 1 and report.survived == 0

    dumped = ROOT / "fixtures/sdk_dump_session.json"
    assert validate(dumped).passed
    sparse = [
        {"role": "user", "content": "Request"},
        {"role": "assistant", "content": "Answer"},
        {"role": "user", "content": "Latest"},
    ]
    config = Contract.model_validate(
        {
            "pins": [{"name": "assistant", "role": "assistant"}],
            "retain": {"latest_user_message": "exact", "recent_exchanges": 1},
        }
    )
    assert check(sparse, dumped, config).passed and check(dumped, sparse, config).passed
    outcome = subprocess.run(
        [
            sys.executable,
            "-m",
            "frayproof",
            "validate",
            "--snapshot",
            str(dumped),
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert outcome.returncode == 0 and json.loads(outcome.stdout)["passed"]
    wire = [
        {"role": "user", "content": "Request"},
        {"role": "assistant", "content": "Answer", "tool_calls": [], "refusal": None},
        {"role": "user", "content": "Latest"},
    ]

    def requires_fields(raw):
        assert raw == wire and raw[1]["tool_calls"] == [] and raw[1]["refusal"] is None
        return raw

    assert run_mutations(wire, requires_fields, config).passed

    def rejects_real_input(raw):
        if "tool_calls" in raw[1]:
            raise RuntimeError("Cannot process explicit calls")
        return raw

    try:
        run_mutations(wire, rejects_real_input, config)
    except InputError:
        pass
    else:
        raise AssertionError("Mutation runner hid a real transformation failure")
    print(
        json.dumps(
            {
                "F1": "fixed",
                "F2": "fixed",
                "F3": "fixed",
                "sdk_nulls": "accepted",
                "optional_null_equality": "verified",
                "mutation_input_fields": "verified",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
