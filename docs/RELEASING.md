# Release handoff

Frayproof 0.1.0 is an unpublished release candidate. The user authorized private
GitHub CI in `ImadC9/frayproof`. Source is uploaded privately; no package, release
tag, public repository, or issue has been published. The CI workflow builds and
tests only; it has no publishing job. `docs/ISSUE_DRAFTS.md` contains five local issue drafts.
`docs/ANNOUNCEMENT_DRAFT.md` leads with the mutation coverage demo and remains a
local draft until publication is authorized.

The hosted Linux/Windows Python 3.12/3.13/3.14 matrix passed on 2026-10-09:
297 tests pass in each of the six combinations, and packaging passes.
[Hosted validation run](https://github.com/ImadC9/frayproof/actions/runs/37876640504)
is accessible to repository members. For any subsequent source changes, require
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
   public source repository. Making the private repository public needs authorization.
2. Add the real repository and issue URLs to project metadata; do not invent them.
3. Confirm the reviewed source and release artifacts correspond to the tested
   revision, and require the complete GitHub CI matrix and packaging to pass.
4. Rebuild and check wheel and source distribution, confirm version and hashes.
5. Upload those exact distributions using the maintainer's PyPI account or trusted
   publishing configuration. Configure credentials outside the source tree.
6. Create tag `v0.1.0` and a GitHub release using the changelog and verified demo.
7. Open the selected good first issue drafts.
8. Verify registry installation and the README demo in a fresh environment.

The candidate is not yet available through `pip install frayproof` from a public
registry. Hosted validation is complete; public visibility, tagging, registry
upload, release creation, and issue posting still require publication authorization.
