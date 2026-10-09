"""Command line with stable exit codes: 0 pass, 1 contract failure, 2 bad input."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from . import __version__
from .engine import check, validate
from .errors import InputError
from .mutate.target import mutate_target

app = typer.Typer(
    help="Check AI conversation context against deterministic contracts.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)


class OutputFormat(StrEnum):
    text = "text"
    json = "json"


def _version(value: bool) -> None:
    if value:
        typer.echo(f"Frayproof {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[bool, typer.Option("--version", callback=_version, is_eager=True)] = False,
) -> None:
    """Frayproof: deterministic context validation with no model or API key."""


def _emit(operation, output_format: OutputFormat) -> None:
    try:
        report = operation()
    except InputError as exc:
        if output_format == OutputFormat.json:
            typer.echo(json.dumps({"schema_version": 1, "error": str(exc)}, ensure_ascii=False))
        else:
            typer.echo(f"INPUT ERROR: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(report.to_json() if output_format == OutputFormat.json else report.to_text())
    raise typer.Exit(0 if report.passed else 1)


@app.command("validate")
def validate_command(
    snapshot: Annotated[Path, typer.Option("--snapshot", help="OpenAI message array JSON.")],
    contract: Annotated[
        Path | None, typer.Option("--contract", help="Optional YAML contract.")
    ] = None,
    output_format: Annotated[OutputFormat, typer.Option("--format")] = OutputFormat.text,
) -> None:
    """Validate one snapshot. Use check when your contract includes pins or retention."""
    _emit(lambda: validate(snapshot, contract), output_format)


@app.command("check")
def check_command(
    before: Annotated[Path, typer.Option("--before", help="Snapshot before transformation.")],
    after: Annotated[Path, typer.Option("--after", help="Snapshot after transformation.")],
    contract: Annotated[Path | None, typer.Option("--contract")] = None,
    output_format: Annotated[OutputFormat, typer.Option("--format")] = OutputFormat.text,
) -> None:
    """Validate after and enforce pins and retention against before."""
    _emit(lambda: check(before, after, contract), output_format)


@app.command("mutate")
def mutate_command(
    target: Annotated[
        str,
        typer.Option(
            "--target", help="Import and execute local path.py:function or module:function."
        ),
    ],
    input_path: Annotated[Path, typer.Option("--input", help="Input OpenAI message array JSON.")],
    contract: Annotated[Path | None, typer.Option("--contract")] = None,
    output_format: Annotated[OutputFormat, typer.Option("--format")] = OutputFormat.text,
) -> None:
    """Run local code once, then measure its contract with nine fault operators at every site."""
    _emit(lambda: mutate_target(target, input_path, contract), output_format)
