## Why

**Every label artifact in `wandb-registry-sleap-roots-labels` was produced by code that does not
exist in any `talmolab` repository.** `/build-labeling-package` and the four scripts it drives
(`select_samples.py`, `copy_selected_images.py`, `build_slp_project.py`, `generate_readme.py`) live
only in a personal vault — not here, not tested, not run in CI, not reviewable. Issue #10's `publish-labels` path is specified to wrap them, and
there is nothing public for it to wrap: anyone other than the original author is blocked from
building, reviewing, or maintaining the label-publishing pipeline (#26).

**The published artifacts also disagree with the code that supposedly made them.** All eight
collections in the registry are `.pkg.slp` — images embedded — while `build_slp_project.py` saves
with `embed=False`, producing a plain external-reference `.slp`. Six of the eight carry
`repaired_from: "v0"` / `embedded-images-repair` metadata: the external reference broke (a dead
Windows temp directory, or a `Z:` drive that resolves from nobody's machine) and someone hand-patched
the file into a package afterwards.

That repair is **one-way and lossy**. `sleap_io.save_slp`'s own documentation is explicit that
`embed=False` restores the original video only *if available*; when it is not — the norm here, since
the source paths are exactly what broke — you get the embedded subset re-saved, permanently capped at
whatever frames were embedded at repair time. A labels file that has been through that cycle can
never have its frame set widened again. Six of eight are already through it.

So the failure mode is not "a path went stale." It is: **the pipeline publishes an artifact that
depends on a filesystem nobody else can mount, and the standard fix silently truncates what the
labels can ever become.**

## What Changes

- Add a **`labeling-package`** capability: sample selection and `.slp` package building as
  first-class, tested modules under `src/sleap_roots_training/labeling/`, exposed through the
  existing `click` CLI the way `registry/publish.py` is.
- **Define the labeling-package directory as a contract** — the `.slp`, a `sample_manifest.csv` with
  one row per labeled frame, and the package metadata needed to build a `LabelCard`. This is the
  handoff #10's `publish-labels` consumes; naming it here is what lets that change be built against
  something real.
- **Embed deliberately, at build time.** The builder calls `save_slp(..., embed=True)` as an
  explicit, tested step, and the package is invalid if its `.slp` is not self-contained. An
  external-reference `.slp` is never produced for publication, so the break-then-hand-repair cycle
  that damaged six collections cannot start.
- **Port `/build-labeling-package` into `.claude/commands/`**, so the whole labeling path — doc and
  code — is public and reviewable in one place.
- **Document "continue labeling" as re-derive + republish**, not edit-in-place: re-fetch the raw scan
  (`bloomctl download --experiment-id <id>`), re-run selection with a wider frame set, publish a new
  version. Consistent with W&B artifact versions being immutable snapshots, and the only path that
  does not inherit the truncation above.
- Add **`sleap-io`** as a dependency (see design.md — it is not currently one, and this is the first
  code in the repo that reads or writes `.slp` files).
- **Parameterize the builder by crop** off a committed, provenance-stamped `skeletons.yaml`. The
  vault script hardcodes soybean's 6-node primary / 4-node lateral while the workflow doc advertises
  `--crop` and a five-crop table, so this is new code with no original to port (design.md Decision
  7). The table holds **native** skeletons — deliberately not Tier 2.7's unified node count.
- **Make a widened re-selection monotone.** The ported selection re-draws rather than extends, so a
  wider run is not a superset of a narrower one — which the re-derive-and-republish recovery path
  below depends on (design.md F3). A recorded deviation, sequenced after the characterization tests.

## What This Change Does *Not* Do

- **Publishing.** Building a `LabelCard`, validating it, and uploading the artifact is #10
  (`add-label-registry`). This change stops at a valid package directory on disk.
- **Backfilling or renaming the eight existing collections** (#11). Nothing here rewrites published
  artifacts; the six already-truncated ones stay as they are.
- **`LabelCard` itself**, which is `sleap-roots-contracts` (`0.1.0a6`).

## Sequencing — this change is deliberately unblocked

`add-label-registry` (#10) cannot start until `sleap-roots-contracts` `0.1.0a6` is on PyPI: this repo
pins `0.1.0a3`, and `LabelCard` does not exist in it. **This change has no such dependency** — it
imports no contract type, builds no card, and touches no registry. It is the half of the label
pipeline that can be built today, and #10's design improves for having a real package layout to
consume rather than a described one.

## Impact

- **Affected specs:** `labeling-package` (new capability).
- **Affected code:** `src/sleap_roots_training/labeling/` (new), `cli.py`, `pyproject.toml`
  (`sleap-io`), `.claude/commands/build-labeling-package.md` (new), `tests/`, `docs/`.
- **Affected issues:** closes #26; unblocks the `publish-labels` half of #10.
- **Source material — obtained in full; Task 0's source read is complete.** All four workflow
  scripts are in hand (`select_samples.py` and `build_slp_project.py` 2026-07-29;
  `copy_selected_images.py` and `generate_readme.py` 2026-08-03) and have been read end to end.
  Every step now has an original to characterize against, so no part of this change is new code
  standing in for a script that could not be recovered. Task 0's remaining items are confirmations
  from eberrigan — the Decision 2 placement and the Decision 4 dependency call — not missing
  material.
