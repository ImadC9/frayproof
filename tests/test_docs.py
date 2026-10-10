"""The README's command transcripts must match executed fixture output."""

import re
import subprocess
import sys

from typer.testing import CliRunner

from frayproof.cli import app

from .conftest import ROOT


def test_readme_transcripts(monkeypatch):
    monkeypatch.chdir(ROOT)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    runner = CliRunner()
    demos = [
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
    ]
    demos.extend(
        [
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
    )
    for name, arguments, exit_code in demos:
        match = re.search(rf"<!-- demo:{name} -->\s*```text\n(.*?)\n```", readme, flags=re.DOTALL)
        assert match is not None, f"README demo missing: {name}"
        outcome = runner.invoke(app, arguments)
        assert outcome.exit_code == exit_code
        assert match.group(1) == outcome.stdout.rstrip("\n")


def test_readme_python_snippets_execute():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    snippets = re.findall(r"```python\n(.*?)\n```", readme, flags=re.DOTALL)
    assert len(snippets) == 3
    for snippet in snippets:
        if "def test_compaction" in snippet:
            snippet += "\ntest_compaction()\n"
        outcome = subprocess.run(
            [sys.executable, "-c", snippet], cwd=ROOT, capture_output=True, text=True
        )
        assert outcome.returncode == 0, outcome.stderr
