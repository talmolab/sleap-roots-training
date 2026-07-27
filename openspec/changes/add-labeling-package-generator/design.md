# Design — labeling-package generator

## Context

The code being ported has produced every artifact in `wandb-registry-sleap-roots-labels`, but has
never been read by anyone but its author. Two consequences shape this design: the port must be
**faithful before it is improved**, and the one behavior we already know is wrong (`embed=False`)
must be changed **on purpose, with a test**, not quietly during translation.

## Decision 1: Port first, change second — characterization tests before behavior changes

Sequence: bring each script in with its behavior preserved, pin that behavior in tests, *then* make
the embed change as its own visible commit.

The alternative — port and fix in one pass — makes every later "did the port break something?"
question unanswerable, because there is no commit where the ported code demonstrably matched the
original. That matters more than usual here: the originals are the only executable description of
how eight published artifacts came to exist, and the sample-selection logic in particular
(`select_samples.py` — which frames, in which order, per scan) has downstream consequences nobody has
written down.

**Any deviation forced during the port gets recorded in tasks.md**, not silently absorbed. If a
script reaches something unavailable here (a Windows path convention, an interactive prompt, an
unpinned import), the deviation is a task with a stated reason.

## Decision 2: Embed in the *builder*, not in `publish-labels`

Issue #26 proposes calling `save_slp(..., embed=True)` "as an explicit, tested step of the publish
pipeline." **This design puts it one layer earlier** — in the package builder — and makes
`publish-labels` *verify* embeddedness rather than perform it.

Reasoning:

- **The package directory is the handoff.** If the `.slp` inside it is only embedded once
  `publish-labels` runs, then the on-disk package is not a complete artifact: it is a thing that
  looks publishable but references a filesystem. Anyone who builds a package and inspects it before
  publishing gets the broken-reference behavior we are trying to abolish.
- **It keeps this change unblocked.** `publish-labels` belongs to #10, which cannot start until
  contracts `0.1.0a6` releases. Embedding in the builder means the fix ships with the port instead of
  waiting behind a dependency it has nothing to do with.
- **Verification is cheap and belongs at the boundary anyway.** #10's publish path should fail fast
  on a non-self-contained `.slp` regardless of who embedded it — that check is what makes the
  guarantee hold against a package built by an older tool or by hand.

Net effect is what #26 asks for — no external-reference `.slp` is ever published — reached at a layer
that does not depend on a blocked change. **Flagged for eberrigan's confirmation on #26**, since it
departs from the issue's stated placement.

## Decision 3: The package directory is a named contract, not an implementation detail

A labeling package is a directory containing the embedded `.slp`, `sample_manifest.csv`, and the
package metadata. Written as a spec requirement here rather than left implicit, because two separate
changes read it: this one writes it, #10's `publish-labels` consumes it and builds a `LabelCard` from
it. An implicit layout would make that seam the place they disagree.

`sample_manifest.csv` carries one row per labeled frame with the columns #10's audit enumerated —
`scan_id`, `plant_qr_code`, `plant_age_days`, `accession_id`, `accession_name`, `wave_number`,
`view_index`, `frame_index`, `source_scan_path`, `source_image`, `output_filename`. That row-level
provenance travelling *inside* the artifact is the whole point: it is what lets a consumer recover
the exact scans, plants, and accessions without a working `Z:` mount — the failure this pipeline has
already suffered once.

## Decision 4: `sleap-io` becomes a runtime dependency

This is the first code in the repo that reads or writes `.slp` files; `sleap-io` is not currently a
dependency and there are no optional-dependency extras to slot it into.

**Recommendation: add it to core `dependencies`, not an extra.** Building labeling packages is
first-class repo functionality reachable from the CLI, and the project's stated convention is that
`sleap-io` is consumed as a library pinned to a release. An extra would mean the CLI has a subcommand
that fails on import for a default install — the kind of surprise that argues for extras only when
the dependency is heavy (`sleap-nn`, torch) rather than merely new.

**Open, for confirmation:** whether the in-flight `feat/add-train-backend-extra` work establishes an
extras convention this should follow instead. If it does, `labeling` becomes an extra and the CLI
gains an import-time guard with a clear install hint.

## Decision 5: Selection is deterministic and recorded

Whatever selection strategy the ported script uses, the same inputs must yield the same frames, and
the chosen frames must be recoverable from `sample_manifest.csv` alone. Without determinism, the
"re-derive + republish" recovery path in Decision 6 is not a recovery path — re-running produces a
different label set, and the new version is not a superset of the old one.

If the original relies on unseeded randomness or filesystem iteration order, making it deterministic
is an explicit, recorded deviation (Decision 1), not an incidental cleanup.

## Decision 6: Continue-labeling is re-derive + republish

Adding frames to an existing labeled scan is: re-fetch the raw scan via `bloomctl download
--experiment-id <id>`, re-run selection with a wider frame set, build, publish a new version.

Not edit-in-place, for two reasons that compound. `LabelCard`'s Bloom-trace fields tie a package to
the experiment it came from, so re-deriving from that experiment is the path that keeps the card
truthful. And de-embedding an existing `.pkg.slp` to widen it does not work — see the `save_slp`
truncation in proposal.md. W&B artifact versions being immutable snapshots makes this the natural
grain anyway.

This is documentation, not code: the design records it, the workflow doc states it, and no
implementation tries to prevent the alternative.

## Risks

- **The port's source is a Box copy, not the vault repo's history.** Authorship and commit context do
  not survive; the ported commit should say where the code came from and when it was copied.
- **Unknown external couplings.** `select_samples.py` presumably reaches Bloom for scan metadata; the
  extent of that coupling is not knowable until the scripts are read. Task 0 explicitly re-scopes the
  change if the coupling is larger than "read a manifest, pick frames."
- **The eight existing collections stay broken.** Nothing here repairs them, and six cannot be fully
  repaired. #11 owns that; this change only ensures the ninth is not produced the same way.
