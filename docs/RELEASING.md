# Release handoff

Source: `ImadC9/frayproof`. The CI workflow builds and tests only. The separate
`release.yml` workflow publishes only when manually dispatched on `main` with
the successful CI run ID for that exact revision. It checks all six matrix jobs
and packaging, downloads their artifacts without rebuilding, publishes to PyPI
with a Trusted Publisher, then creates the matching GitHub tag and release.
`docs/ISSUE_DRAFTS.md` and `docs/ANNOUNCEMENT_DRAFT.md` remain drafts unless
separately selected for posting.

The hosted Linux/Windows Python 3.12/3.13/3.14 matrix passed on 2026-10-09:
297 tests pass in each of the six combinations, and packaging passes.
[Hosted validation run](https://github.com/ImadC9/frayproof/actions/runs/37876640504)
records the initial release gate. For any subsequent source changes, require
all six combinations and packaging to pass again before release. Local tests
alone do not establish the supported matrix. The reported review defects are
covered by [regressions and installed-wheel probes](REVIEW_FIXES.md).

## Review the local release

The source repository, README demos, Apache-2.0 license, test suite, and examples
are included in the source distribution. The wheel contains the Python package,
typed marker, license, and CLI entry point. A separate source ZIP supports local
review without unpacking a Python distribution.

Run the validation commands from CONTRIBUTING.md. Install the built wheel into a
fresh environment and rerun the README demos from outside the source directory.
This checks that imports work without an editable-install path or a working-tree
`PYTHONPATH`. Rebuild from the source distribution as well as from the checkout.
Verify the weak mutation example exits `1` with 12/20 caught and the stronger
contract exits `0` with 20/20 caught using the reusable retention contract.
Refresh transcripts with `python examples/capture_demos.py` and run the README
drift tests.
Run `python examples/verify_review_fixes.py` with the installed wheel from outside
the checkout to verify the review defects and SDK-null behavior independently.

## Publication requires the maintainer's instruction

After the user explicitly requests publication:

1. Recheck `frayproof` availability on PyPI and confirm `ImadC9/frayproof` as the
   public source repository.
2. Confirm source, issue, and changelog URLs in project metadata.
3. Confirm the reviewed source and release artifacts correspond to the tested
   revision, and require the complete GitHub CI matrix and packaging to pass.
4. Rebuild and check wheel and source distribution, confirm version and hashes.
5. Configure the PyPI Trusted Publisher for owner `ImadC9`, repository `frayproof`,
   workflow `release.yml`, environment `pypi`. For the first upload, register it
   under account Publishing as a pending publisher for project `frayproof`.
6. Dispatch `Publish 0.1.0` on `main` with its successful CI run ID. The workflow
   publishes the verified distributions, creates tag `v0.1.0`, and publishes the
   GitHub release from `docs/RELEASE_NOTES_0.1.0.md` with the same files attached.
7. Open good first issue drafts only if selected for posting.
8. Verify registry installation and the README demo in a fresh environment.

Publication is complete only after the registry has version `0.1.0`, registry
hashes match the verified artifacts, the GitHub release targets the tested
revision, and fresh registry installation plus the demo pass.
