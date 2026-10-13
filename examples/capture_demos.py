"""Refresh README transcripts from actual commands. Run from an installed checkout."""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMOS = [
    ("clean", ["validate", "--snapshot", "fixtures/clean_session.json"], 0),
    ("orphan", ["validate", "--snapshot", "fixtures/orphaned_result.json"], 1),
    (
        "compaction",
        [
            "check",
            "--before",
            "fixtures/clean_session.json",
            "--after",
            "fixtures/legitimate_compaction.json",
            "--contract",
            "examples/contract.yaml",
        ],
        0,
    ),
    (
        "constraint",
        [
            "check",
            "--before",
            "fixtures/clean_session.json",
            "--after",
            "fixtures/dropped_constraint.json",
            "--contract",
            "examples/contract.yaml",
        ],
        1,
    ),
    (
        "mutation-weak",
        [
            "mutate",
            "--target",
            "examples/mutation_compactor.py:compact",
            "--input",
            "fixtures/mutation_session.json",
            "--contract",
            "examples/weak_contract.yaml",
        ],
        1,
    ),
    (
        "mutation-strong",
        [
            "mutate",
            "--target",
            "examples/mutation_compactor.py:compact",
            "--input",
            "fixtures/mutation_session.json",
            "--contract",
            "examples/mutation_contract.yaml",
        ],
        0,
    ),
    (
        "warning",
        [
            "validate",
            "--snapshot",
            "fixtures/pending_batch.json",
            "--contract",
            "examples/warning_contract.yaml",
        ],
        0,
    ),
    (
        "severity-override",
        [
            "check",
            "--before",
            "fixtures/clean_session.json",
            "--after",
            "fixtures/dropped_constraint.json",
            "--contract",
            "examples/severity_override_contract.yaml",
        ],
        0,
    ),
    (
        "input-error-json",
        [
            "validate",
            "--snapshot",
            "fixtures/malformed_content.json",
            "--format",
            "json",
        ],
        2,
    ),
]


def main():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    captures = []
    for name, arguments, expected in DEMOS + [("toy", [], 0)]:
        command = (
            [sys.executable, "-m", "frayproof", *arguments]
            if name != "toy"
            else [
                sys.executable,
                "examples/toy_agent.py",
            ]
        )
        outcome = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
        )
        if outcome.returncode != expected:
            raise RuntimeError(f"{name}: {outcome.stderr}")
        pattern = rf"(<!-- demo:{name} -->\s*```text\n).*?(\n```)"
        readme, count = re.subn(
            pattern,
            lambda match, result=outcome: match[1] + result.stdout.rstrip("\n") + match[2],
            readme,
            flags=re.DOTALL,
        )
        if count != 1:
            raise RuntimeError(f"Expected one README block for {name}, found {count}")
        captures.append(
            {
                "command": "frayproof " + " ".join(arguments)
                if name != "toy"
                else "python examples/toy_agent.py",
                "exit_code": expected,
                "stdout": outcome.stdout,
                "stderr": outcome.stderr,
            }
        )
    (ROOT / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    (ROOT / "docs/DEMO_TRANSCRIPT.json").write_text(
        json.dumps(captures, indent=2), encoding="utf-8", newline="\n"
    )
    print("Captured six checker/mutation demos and the guarded toy agent.")


if __name__ == "__main__":
    main()
