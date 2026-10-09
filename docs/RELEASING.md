# Release handoff

Frayproof 0.1.0 is a local release candidate. Nothing has been pushed, uploaded, published,
or posted as an issue. The CI workflow builds and tests only; it has no publishing
job. `docs/ISSUE_DRAFTS.md` contains five local issue drafts.
`docs/ANNOUNCEMENT_DRAFT.md` leads with the mutation coverage demo and remains a
local draft until publication is authorized.

The hosted Linux/Windows Python 3.12/3.13/3.14 matrix remains unrun. Passing local
tests and rebuilt-wheel probes does not establish the whole supported matrix.
Keep the release on hold until that validation is completed. The reported review
defects are covered by [regressions and installed-wheel probes](REVIEW_FIXES.md).

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

1. Recheck `frayproof` availability on PyPI and choose the GitHub owner/repository.
2. Add the real repository and issue URLs to project metadata; do not invent them.
3. Push the reviewed local repository and run the complete GitHub CI matrix.
4. Rebuild and check wheel and source distribution, confirm version and hashes.
5. Upload those exact distributions using the maintainer's PyPI account or trusted
   publishing configuration. Configure credentials outside the source tree.
6. Create tag `v0.1.0` and a GitHub release using the changelog and verified demo.
7. Open the selected good first issue drafts.
8. Verify registry installation and the README demo in a fresh environment.

The candidate still needs hosted validation; it is not yet available
through `pip install frayproof` from a public registry. No release tag or external
repository is fabricated during local preparation.
