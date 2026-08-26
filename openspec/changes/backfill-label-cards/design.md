## Context

The `wandb-registry-sleap-roots-labels` registry holds 8 label collections published before the
`LabelCard` contract existed. Their metadata is ad hoc: boolean keys, free-text descriptions,
`data_path` fields pointing at deleted temp directories or a single-machine drive letter. The
`LabelCard` contract (`sleap-roots-contracts#24`, shipped via #10) gives labels the same structured
metadata models already have via `ModelCard` — but the existing 8 collections must be retrofitted
onto it.

This document is written against the **post-#50 world**. #50 collapsed the root-type vocabulary into
the contract-owned `sleap_roots_contracts.RootType`: `ROOT_TYPE_VOCAB` no longer exists as a
hand-written set in `labeling/metadata.py` or `config.py`, and is instead a single object derived
from the contract in `registry/chooser.py` and imported by all three consumers. An earlier draft of
this design targeted the pre-#50 layout and proposed editing a symbol that will not exist; D3 and D5
below are written against what `main` will actually hold.

### The 8 collections

| collection | species | mode | root_type | versions | data_path status |
|---|---|---|---|---|---|
| `soybean_lateral_4nodes_v007_labels` | soybean | cylinder | lateral | 1 | `Z:` drive |
| `soybean_primary_6nodes_v004_labels` | soybean | cylinder | primary | 1 | `Z:` drive |
| `plate_medicago_14DAG_primary_8nodes_labels` | medicago¹ | plate | primary | 2 | deleted temp |
| `plate_arabidopsis_2-7DAG_primary_8nodes_labels` | arabidopsis | plate | primary | 2 | deleted temp |
| `cyl_arabidopsis_7-11DAG_primary_6nodes_labels` | arabidopsis | cylinder | primary | 2 | deleted temp |
| `rice_3DAG_crown_6nodes_labels` | rice | cylinder | crown | 2 | deleted temp |
| `wheat_5-14DAG_seminal_6nodes_labels` | wheat | cylinder | seminal² | 2 | deleted temp |
| `sorghum_5-12DAG_primary_6nodes_labels` | sorghum | cylinder | primary | 2 | deleted temp |

¹ `medicago` is not in `SPECIES_VOCAB`. See D5 — it is added to a *label-side* vocabulary, not to
the model-side one.

² `seminal` is not in the contract's `RootType`, on the pin or at contracts HEAD. See D3 — an
earlier draft of this document asserted it was, which was wrong and is what forced D3's rewrite.

**Six of the eight names carry an age** (`14DAG`, `2-7DAG`, `7-11DAG`, `3DAG`, `5-14DAG`,
`5-12DAG`). The two that do not are the two soybean collections — which are also the two whose
`data_path` is the `Z:` drive. So the two least-recoverable collections are exactly the two with no
age in the name, which is what makes D7 load-bearing rather than a formality.

## Goals / Non-Goals

**Goals:**
- Stamp every collection with a valid `LabelCard` via normalized metadata
- Normalize collection names to match the model registry pattern (`species-mode-root_type`)
- Preserve existing artifact versions (link, don't re-publish)
- Give the label side a root-type vocabulary that admits `seminal`, without widening the model side
- Verify single-species content per collection
- Mark unrecoverable provenance fields as `null`

**Non-Goals:**
- Recovering the deleted `data_path` files (the images live in the artifact blob)
- Building a `publish-labels` CLI for *new* packages (that is #10/#26 scope)
- Multi-species `LabelCard` support (decision: stays single-species)
- Changing the `ModelCard` side of the registry, its `_ROOT_SLOTS`, or `SPECIES_VOCAB`
- Making `wheat` / `sorghum` / `medicago` / `seminal` valid in a *training config* (see D5)

## Upstream dependency

D3 and D7 both require a `sleap-roots-contracts` release. They are folded into **one** bump rather
than two, since they land in the same file and the second is conditional on §2's findings:

| upstream change | source | conditional? |
|---|---|---|
| add `LabelRootType` (superset of `RootType`, adds `seminal`) | D3 | no |
| relax `age_min`/`age_max`/`n_plants`/`n_scans` to `Optional` | D7 | yes — only if §2 cannot recover them |

Contracts is at `0.1.0a8`; this repo pins `0.1.0a6`. So the bump is **two-part**: catch up to the
current release *and* carry the new work, landing as `0.1.0a9`. The `a3 → a6` bump went through its
own change directory (`archive/2026-08-05-update-contracts-pin-0-1-0a6`) with a full `a3 → a6` delta
review, and this one should follow that precedent rather than being folded in here silently — see
task 1.1.

## Decisions

### D1: Null for unrecoverable provenance, no `provenance: "reconstructed"` marker

`LabelCard` provenance fields that cannot be recovered from the artifact description or Bloom are
set to `null`. A separate marker type adds schema complexity without information — `null` already
communicates "not recorded" and is what `sleap-roots-predict`'s parity harness already uses for its
interim `LabelCard` records.

This decision covers **exactly the seven fields the contract makes `Optional`**:

```
source_experiment  bloom_experiment_id  accessions  labeler  box_link  source_sha256
sleap_io_version
```

It does **not** cover the other fifteen, which are required and non-nullable. The contract drew that
line deliberately and with this change in view — the comment above the provenance block reads
"optional so #11's as-is backfill isn't gated on metadata unrecoverable for the eight legacy
collections". D7 handles the fields on the other side of that line; the proposal's "unrecoverable
fields are `null`" promise is scoped to this list and nowhere else.

### D2: New correctly-named collections, link existing versions

W&B collections cannot be renamed. Create new collections following the model registry's naming
convention (`species-mode-root_type`, e.g. `soybean-cylinder-lateral`), then link the existing
artifact versions into them. The old collections remain resolvable (nothing orphaned) but do not
carry the `production` alias — only the new ones do.

**Why link, not re-publish:** re-publishing creates new artifact digests, breaking any
`weights_checksum`-style references in downstream consumers. Linking preserves the original
artifact identity.

### D3: A separate contract-owned `LabelRootType`, not a widened `RootType`

The wheat collection uses root type `seminal`. **The contract does not accept it today.** Verified
on the pinned `0.1.0a6` and again at contracts HEAD (`0.1.0a8`, two releases ahead of our pin),
where `src/sleap_roots_contracts/models.py:266` still reads:

```python
RootType = Literal["primary", "lateral", "crown"]
```

The string `seminal` does not appear anywhere in that source tree. So
`LabelCard(root_type="seminal", ...)` raises a pydantic `ValidationError`, and the wheat collection
— 1 of the 8 this change exists to backfill — cannot be stamped at all. An earlier draft of this
document claimed the opposite and marked it "(confirmed)"; it was not confirmed, and correcting it
is what turns this from a version bump into a design fork.

**Decision: add a new `LabelRootType` to the contract, a superset of `RootType` including
`seminal`. `RootType` itself is untouched.** `LabelCard.root_type` is re-annotated to
`LabelRootType`; `ModelCard.root_type` stays `RootType`.

**Why not widen `RootType`** — the obvious move, and the one that quietly breaks two things:

1. **It forces `seminal` into the model side.** After #50, `tests/test_registry_cards.py` asserts
   `frozenset(cards._ROOT_SLOTS) == chooser.ROOT_TYPE_VOCAB`, with a comment saying a fourth root
   type upstream that is not added as a slot means every card for it is silently never emitted.
   Widening `RootType` therefore turns that test red until `_ROOT_SLOTS` grows a `seminal` entry —
   directly contradicting this change's own requirement that `_ROOT_SLOTS` SHALL NOT be modified.
2. **It makes `seminal` a legal `experiment.root_type`.** After #50, `ROOT_TYPE_VOCAB` is a *single
   shared object* backing three surfaces: `config.py:210` (a hand-written training config),
   `metadata.py:120` (a labeling package's `root_types`), and `skeletons.py:144` (the skeleton
   table). Widening it does not add a label-only value — it silently authorizes training a model for
   a root type no model exists for, which is the opposite of what this change wants.

**Why not exclude wheat.** It backfills 7 of 8 and returns the same decision later with the same
options, having meanwhile published a registry that is normalized except for one collection.

**Why this is not undoing #50.** #50's principle is *the contract owns membership, this package does
not restate it* — not *there is exactly one root-type vocabulary*. Both vocabularies here are
derived from the contract via `typing.get_args`, neither is hand-written, and both carry #50's
import guard against a `Literal` that stops being a plain `Literal`. What #50 retired was three
hand-maintained copies of the same set; this adds one contract-derived set with a different
membership and a stated reason for differing.

The two vocabularies split across the existing consumers as follows:

| consumer | today (post-#50) | after this change |
|---|---|---|
| `config.py:210` — `experiment.root_type` | `ROOT_TYPE_VOCAB` | `ROOT_TYPE_VOCAB` (unchanged) |
| `registry/cards.py` — `_ROOT_SLOTS` | pinned to `ROOT_TYPE_VOCAB` | unchanged |
| `metadata.py:120` — package `root_types` | `ROOT_TYPE_VOCAB` | `LABEL_ROOT_TYPE_VOCAB` |
| `skeletons.py:144` — skeleton table | `ROOT_TYPE_VOCAB` | `LABEL_ROOT_TYPE_VOCAB` |

### D4: Collection naming convention

Normalized names follow: `{species}-{mode}-{root_type}` with hyphens, matching the model
registry's convention. Age is omitted from label collection names — unlike models, which are
trained for specific age windows, a label set covers whatever ages were annotated and the age
range is metadata on the card, not part of the collection identity.

Examples:
- `soybean-cylinder-lateral` (was `soybean_lateral_4nodes_v007_labels`)
- `arabidopsis-cylinder-primary` (was `cyl_arabidopsis_7-11DAG_primary_6nodes_labels`)
- `wheat-cylinder-seminal` (was `wheat_5-14DAG_seminal_6nodes_labels`)

### D5: A label-side species vocabulary, not a widened `SPECIES_VOCAB`

`wheat`, `sorghum`, and `medicago` all have published label data and none has a trained model. An
earlier draft added all three to `SPECIES_VOCAB`. **That vocabulary is not label-side**, and
widening it reaches further than intended:

| site | what it validates | side |
|---|---|---|
| `chooser.py:207` | the **model selection matrix** | model |
| `config.py:208` | `experiment.species` in a **training config** | model |
| `metadata.py:96` | a labeling package's `species` | label |
| `skeletons.py:139` | the **skeleton table** rows | label |

So "add three species with published labels" would also make `species: wheat` a legal training
config and a legal selection-matrix row, for a species with no model, no matrix row, and no verified
skeleton entry.

**Decision: introduce `LABEL_SPECIES_VOCAB`, a package-owned superset of `SPECIES_VOCAB` adding
`wheat`, `sorghum`, and `medicago`. `SPECIES_VOCAB` is unchanged.** The two label-side sites above
move to the new vocabulary; the two model-side sites keep the old one. Both stay package-owned —
`LabelCard.species` and `ModelCard.species` are free `str` on the contract, so unlike root type
there is no contract vocabulary to defer to and no upstream change involved.

**This also keeps a live spec statement true rather than requiring a delta to falsify it.**
`openspec/specs/model-registry/spec.md:16-17` says the `species` vocabulary is "currently
{`soybean`, `canola`, `pennycress`, `arabidopsis`, `rice`}" — which is exactly today's
`SPECIES_VOCAB`, so widening it would have needed a `## MODIFIED Requirements` block on
**Production Model Selection Matrix** carrying all five of its scenarios. Splitting means the
model-side sentence stays accurate and this change ships only its own `## ADDED` delta.

**Relationship to the skeleton table.** `skeletons.yaml`'s header already anticipates this change:
"the verification test against the eight published collections in
`wandb-registry-sleap-roots-labels` is what flips the remaining rows to `verified: true`." §2.4's
node-count archaeology is that verification, so the skeleton table needs to *accept* `wheat` /
`sorghum` / `medicago` rows before it can gain them. That is the label-side use, and it is the
concrete reason the split falls where it does.

### D6: Canary-first migration, matching `seed-registry --only` precedent

Migrate one collection first as a canary (verify the consumer can read the new-shape collection),
then migrate the rest. Same pattern `seed-registry --only` established for models.

The canary is **`arabidopsis-cylinder-primary`** (was
`cyl_arabidopsis_7-11DAG_primary_6nodes_labels`): it is a species already in both vocabularies, a
root type already in `RootType`, and an age already in its name — so it exercises the link-and-alias
path without also depending on D3's or D7's outcome. A canary that needed the contract bump would
conflate two failures.

### D7: The required-field gate — archaeology decides, with a stated fallback

`LabelCard` has **15 required, non-nullable fields**, not just the provenance block D1 covers:

```
species  mode  root_type  age_min  age_max  skeleton_name  node_count  node_names
n_frames  n_instances  n_plants  n_scans  images_embedded   (+ registry_id, version)
```

Most are fine. `n_frames`, `n_instances`, `node_count`, `node_names`, `skeleton_name` and
`images_embedded` are all derivable from the artifact blob, which §2.4 already plans to read. Four
are not:

- **`age_min` / `age_max`** — required `int`s. Six collection names carry an age; the two soybean
  collections do not, and they are the two whose `data_path` is the `Z:` drive.
- **`n_plants` / `n_scans`** — required `int`s, and experiment-design facts rather than properties
  of a `.slp`. Nothing in the blob yields them.

Fabricating them is forbidden by D1's own promise, so the honest options are to recover them or to
relax them upstream.

**Decision: §2 archaeology runs first and decides, per field, with relaxing upstream as the stated
fallback.** Concretely:

1. §2 attempts recovery for all four fields on all eight collections — artifact `description` free
   text, the lab share, and Bloom (task 2.1), recorded per collection with a confidence level
   (task 2.2).
2. **If every collection yields all four**, no further contract change is needed and D3's
   `LabelRootType` is the whole of the bump.
3. **If any collection does not**, the four fields are relaxed to `Optional` in the *same* contracts
   release as `LabelRootType`, and the unrecoverable ones are set to `null` under D1's rule.

**Why gate rather than relax now.** Relaxing re-litigates a line the contract drew deliberately and
with this change named in the comment. Six of eight collections have an age in the name, so the
question is genuinely open for two collections and four fields — small enough that guessing wrong in
either direction is worse than looking. Relaxing pre-emptively would loosen the contract for every
future consumer on the strength of a gap we had not yet confirmed existed.

**Why not exclude the two soybean collections instead.** They are the two with the `Z:`-drive
`data_path` — the least discoverable label sets in the registry, and the ones whose provenance most
needs recording before the drive letter stops resolving anywhere at all. Backfilling six of eight
and leaving the hardest two is the outcome this change exists to prevent.

**Why this is a decision and not a deferral.** It names which fields are at issue, what evidence
settles them, which release absorbs the fallback, and what happens in each branch. What it does not
do is assert an answer to a question no one has looked at yet — §3 cannot start until §2 reports,
and the task list now enforces that ordering.

## Risks / Trade-offs

- **Provenance gaps are real.** 6 of 8 collections have broken `data_path`. Free-text
  `description` may not contain enough to reconstruct `bloom_experiment_id` or accession IDs for
  all collections. These seven fields are `Optional` on the contract, so they will be `null` and
  flagged.
- **Four required fields may not survive archaeology.** `age_min`, `age_max`, `n_plants`, `n_scans`
  are required `int`s, so "null and flagged" is *not* available for them without the upstream
  relaxation D7 describes. This is the risk that can extend the change's scope into a second
  contracts release; it is the reason §2 gates §3.
- **This change is blocked on a contracts release.** D3 is unconditional, so `0.1.0a9` must ship
  before §3 can construct a wheat card. The pin bump also carries `a7`/`a8`, which this repo has
  not yet absorbed.
- **Two vocabularies where #50 left one.** `ROOT_TYPE_VOCAB` and `LABEL_ROOT_TYPE_VOCAB` will
  co-exist, and a reader who remembers #50 may read that as regression. Both are contract-derived
  and guarded, and the split is asserted by test at each consumer — but the *naming* is the
  mitigation that matters, and `LABEL_`-prefixing both new vocabularies is deliberate.
- **Old collection names remain.** They are not deleted, only de-aliased. Consumers using the old
  names directly (not via `production` alias) will still resolve, but won't get `LabelCard`
  metadata.

## Migration Plan

This change writes to a live wandb registry, creates collections that **cannot be renamed or
deleted**, and re-points `production` aliases. The forward order is D6's; what follows is the
rollback story for each step, since a failed `--execute` partway through the eight is the realistic
bad case.

**Forward:**

1. Contracts `0.1.0a9` ships (D3, plus D7's relaxation if §2 requires it); this repo's pin bumps.
2. Dry run (`seed-label-registry`, no `--execute`) — prints all eight planned collections and their
   card metadata, contacting nothing. Reviewed by hand against §2's recorded findings.
3. Canary: `--execute --only arabidopsis-cylinder-primary`. Verify the downstream consumer reads the
   new-shape collection before anything else moves.
4. Remaining seven: `--execute`. Idempotent, so the canary is skipped rather than re-linked.
5. `--verify` — read back every expected collection's `production` alias, non-zero exit if any is
   missing.

**Rollback:**

- **Partway through step 4.** No rollback is needed and none should be attempted. Linking is
  additive and idempotent: the original artifact versions are untouched (D2), the old collections
  stay resolvable, and a re-run skips what already carries the `production` alias. The correct
  response to a failure at collection five of eight is to fix the cause and re-run, not to undo.
- **A collection created with a wrong name.** Not recoverable — W&B collections cannot be renamed or
  deleted, which is why step 2's dry-run review is a gate and not a formality. The residue is an
  empty or mis-named collection that never receives the `production` alias. Step 3's canary exists
  to make this cost one collection rather than eight.
- **A wrongly-stamped `LabelCard`.** Re-runnable via `--force`, which re-links and re-points the
  alias (see the Idempotent Label Registry Migration requirement). Metadata is correctable in place;
  only names are not.
- **Full abandonment.** The old collections retain their artifacts and remain resolvable throughout
  — that is D2's link-don't-republish property doing double duty as the rollback story. Consumers
  pinned to old names never break; consumers reading `production` see the pre-migration state until
  the alias moves, and the alias moves last.

## Open Questions

- ~~**Q1a:** Does the `LabelCard` contract in `sleap-roots-contracts` 0.1.0a6 allow `null` for
  `bloom_experiment_id`, `accessions`, and the other provenance fields?~~
  **Resolved:** yes. All seven provenance fields are `Optional`, confirmed against the pin. See D1.
- ~~**Q1b:** Does it allow `null` for the node-count and content-count fields?~~
  **Resolved:** no — and this half of Q1 was previously closed without being answered. 15 fields are
  required and non-nullable, including `age_min`, `age_max`, `n_plants`, and `n_scans`. See D7 for
  how that is handled; the answer is not "they will be `null` and flagged", which is not available
  for a required field.
- ~~**Q2:** The medicago plate collection — is `medicago` a species this project will support
  long-term, or should it be excluded from the backfill and tracked separately?~~
  **Resolved:** `medicago` is in scope, added to `LABEL_SPECIES_VOCAB` (not `SPECIES_VOCAB`) along
  with `wheat` and `sorghum`. See D5.
- ~~**Q3:** Does the contract's `RootType` accept `seminal`?~~
  **Resolved:** no, on the pin and at HEAD. See D3.
- **Q4 (open, settled by §2):** Are `age_min`/`age_max` recoverable for the two soybean collections,
  and are `n_plants`/`n_scans` recoverable for any of the eight? This is D7's gate. It is listed as
  open deliberately — §2 exists to answer it, and §3 cannot begin until it does.
