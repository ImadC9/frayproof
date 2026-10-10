# Release guide

The [CI workflow](../.github/workflows/ci.yml) builds and tests source changes.
The separate [release workflow](../.github/workflows/release.yml) publishes
only when a maintainer manually dispatches it on `main` with a successful CI
run ID for that exact revision. It downloads the tested distributions without
rebuilding, publishes to PyPI through a Trusted Publisher, and creates the
matching GitHub tag and release.

This workflow currently targets version `0.1.0`. For a later version, update
the version, expected filenames, tag, and release-note path in the workflow
before running its CI gate.

## Prepare and review

1. Confirm the version, license, project metadata URLs, changelog, and
   [release notes](RELEASE_NOTES_0.1.0.md).
2. Run the validation commands in [CONTRIBUTING.md](../CONTRIBUTING.md).
   Build a wheel and source distribution for local review, check their metadata,
   and confirm the source distribution can rebuild successfully.
3. Install the wheel into a fresh environment and run the README demos from
   outside the checkout, without a working-tree `PYTHONPATH`. The weak mutation
   example should exit `1` with 12/20 caught; the stronger retention contract
   should exit `0` with 20/20 caught.
4. Run `python examples/verify_review_fixes.py` against the installed wheel from
   outside the checkout. See the [regression coverage](RELEASE_NOTES_0.1.0.md#regression-coverage)
   for the identity, input, and mutation cases it exercises.
5. Refresh transcripts with `python examples/capture_demos.py`, run
   `python -m pytest tests/test_docs.py -q`, and commit any intended changes.

## Select the tested artifacts

Push the reviewed source to `main` and wait for its complete CI run. Require
all six Linux/Windows jobs on Python 3.12, 3.13, and 3.14, plus the
`distributions` job, to succeed. Local checks alone do not establish the
supported platform matrix.

Record that run's ID and commit SHA for this release. Download its
`frayproof-distributions` artifact, confirm its version and filenames, and
record SHA-256 hashes of the wheel and source distribution. Review these exact
artifacts and repeat the fresh-install probes against the CI wheel. Local
review builds are useful evidence; the release workflow publishes the CI files.

If `main` changes, select a new successful CI run for the new head. The release
workflow rejects a run from another revision, branch, event, or workflow, and
requires the expected six test jobs plus packaging. Historical validation
evidence belongs in the version's release notes, not in this procedure.

## Publish

A package release is a separate maintainer decision from merging source or
publishing contributor issues.

1. Confirm ownership/availability of the PyPI project and that the target
   version has not already been published.
2. Configure the PyPI Trusted Publisher for owner `ImadC9`, repository
   `frayproof`, workflow `release.yml`, and environment `pypi`. For the first
   upload, use a pending publisher for project `frayproof`.
3. Dispatch the workflow named `Publish 0.1.0` on `main` and supply
   `ci_run_id` from the successful run for that exact head.
4. Check the verification, PyPI, and GitHub-release jobs. The workflow publishes
   the verified distributions, creates `v0.1.0` at the tested revision, and uses
   `docs/RELEASE_NOTES_0.1.0.md` for the GitHub release with the same files attached.

## Verify completion

Confirm PyPI has the intended version and that its distribution hashes match
the selected CI artifacts. Confirm the GitHub release tag targets the tested
commit and its attached files match those artifacts. Finally, install the
version from PyPI into a fresh environment and run the README demo.

A release is complete when all of these checks pass. If a job fails, inspect
the registry and tag state before retrying; PyPI versions cannot be overwritten.
