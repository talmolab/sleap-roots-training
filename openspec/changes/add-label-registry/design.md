## Context

`registry/publish.py` is the shape to mirror. `publish_card(run, card, model_dir, cfg)` is "the thin
network layer": it builds a `wandb.Artifact`, `add_dir`s the payload, logs it, and links it to the
registry target under an alias, with `wandb` imported lazily so the pure-logic path stays importable
without it. `resolve_all(...)` "runs no network — safe to call before `wandb.init`" — the repo already
separates resolution/validation from upload. The label path adopts both properties.

The card itself (`LabelCard`, `Mode`) lands in `sleap-roots-contracts` under the sibling change
`add-label-selection-contract`; this change consumes it.

## Goals / Non-Goals

- **Goals:** a label artifact that can be traced to its experiment, plants, and accessions without a
  working `Z:` mount; publish failures surface before upload; one owner for the mode vocabulary.
- **Non-Goals:** backfilling/renaming the eight legacy collections (#11); changing the embedding
  behaviour of `build_slp_project.py`; porting the whole `/build-labeling-package` workflow into this
  repo.

## Decisions

**Decision: the publish input is a labeling-package directory.**
`/build-labeling-package` already emits a self-consistent directory — the `.slp`, the
`sample_manifest.csv`, and the metadata needed for the card. Taking the directory (rather than a
pre-built card, or loose arguments) means the manifest is present by construction, `n_frames` can be
cross-checked against it, and `add_dir` publishes the package as a unit — mirroring how
`publish_card` takes a `model_dir`. It also keeps the fix aimed at the actual failure: the metadata
existed all along and was dropped at this exact boundary.
*Alternative considered:* accept a `LabelCard` and a `.slp` path, leaving manifest assembly to the
caller — rejected, because it reintroduces the seam where provenance gets dropped.

**Decision: `sample_manifest.csv` is attached inside the artifact, not flattened into card metadata.**
It is one row per labeled frame (hundreds — e.g. 482 for `soybean_lateral_4nodes_v007`) with eleven
columns. That is a table, not metadata; wandb metadata is for the queryable summary (the `LabelCard`),
while the manifest is payload. Attaching it inside the artifact means it is versioned with the labels
it describes and travels with them.

**Decision: `n_frames == manifest row count` is enforced here, not in the contract.**
This is the one invariant of the three that a `LabelCard` model validator cannot express: it compares
a card field against a file's contents, and `sleap-roots-contracts` takes no filesystem I/O by
design. The publish path already holds the labeling-package directory, so it is the natural — and
only — home. It runs in the pure, pre-network stage alongside card construction, so a mismatch fails
before upload. The two card-intrinsic invariants (`age_min <= age_max`,
`node_count == len(node_names)`) are enforced by the contract at construction and are not re-checked
here.

**Decision: `label-registry` as a new sibling capability, not ADDED requirements on
`model-registry`.**
Same reasoning as the contracts side, and the repo's convention: one capability per surface.
`model-registry` is scoped to the production model selection matrix, card expansion, and model
publishing; label publishing is an orthogonal surface that happens to reuse the mechanics.
*(Signed off by Elizabeth on #10.)* Note this change *does* still carry one `model-registry` delta —
but only for the vocabulary ownership move, which genuinely alters a shipped requirement rather than
adding a new concern.

**Decision: `MODE_VOCAB` is replaced by `get_args(Mode)`, and this is a MODIFIED requirement.**
`model-registry`'s *Production Model Selection Matrix* requirement currently says the accepted
vocabulary "lives in one place in code and is reconciled with the consumer at acceptance". Today that
place is `chooser.py:23`. After this change it is the contract. The values are identical and no
row-validation behaviour changes, but the requirement's text names where the vocabulary lives, so it
is edited rather than left to drift. `SPECIES_VOCAB` stays in `chooser.py` — out of scope.

## Risks / Trade-offs

- **Cross-repo sequencing.** This change cannot merge before contracts releases `0.1.0a6` (not
  `0.1.0a5` — that version was taken concurrently by the prediction-manifest contract and carries no
  `LabelCard`). → The contracts PR goes first; tasks below gate on the pin bump.
- **Artifact size.** Six legacy collections are 170 MB – 1.2 GB because images were embedded to work
  around missing provenance. This change does not alter `embed=False`, so newly published packages
  keep images external and `images_embedded` records which regime a card describes. The underlying
  "the `.slp` can't find its images" problem is addressed by the manifest carrying real source paths,
  not by embedding. → Out of scope but worth revisiting once the manifest is proven.
- **Registry type name.** Publishing labels as `type="dataset"` while models use `type="model"` is
  assumed; if the existing eight collections use a different type string, the verify path must match
  it or the read-back will silently find nothing. → Confirm against the live registry during 1.1.
- **`cyl` naming stays broken.** The *field* is fixed by `Mode`; the eight collection *names* still
  use `cyl_...`, so the two registries remain unjoinable by name until #11. Accepted and explicitly
  deferred.

## Open Questions

- Does the existing `sleap-roots-labels` registry use `type="dataset"`? (Blocks the verify path.)
- Should `publish-labels` refuse to publish when the package's `.slp` has embedded images, or merely
  record `images_embedded=True`? Proposed: record, don't refuse.
