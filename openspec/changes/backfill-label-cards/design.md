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
| `wheat_5-14DAG_seminal_6nodes_labels` | wheat | cylinder | crown² | 2 | deleted temp |
| `sorghum_5-12DAG_primary_6nodes_labels` | sorghum | cylinder | primary | 2 | deleted temp |

¹ `medicago` is not in `SPECIES_VOCAB`. See D5 — it is added to a *label-side* vocabulary, not to
the model-side one.

² The collection is *named* `seminal`, and the root type recorded on its card is `crown`. At the
age wheat is studied here the roots are technically seminal, but they are morphologically
indistinguishable from crown roots and this project labels them as crown. See D3 — an earlier draft
of this document asserted the contract's `RootType` already accepted `seminal` (it does not, on the
pin or at HEAD) and proposed adding it; both the claim and the remedy were wrong.

**Six of the eight names carry an age** (`14DAG`, `2-7DAG`, `7-11DAG`, `3DAG`, `5-14DAG`,
`5-12DAG`). The two that do not are the two soybean collections — which are also the two whose
`data_path` is the `Z:` drive. So the two least-recoverable collections are exactly the two with no
age in the name, which is what makes D7 load-bearing rather than a formality.

## Goals / Non-Goals

**Goals:**
- Stamp every collection with a valid `LabelCard` via normalized metadata
- Normalize collection names to match the model registry pattern (`species-mode-root_type`)
- Preserve existing artifact versions (link, don't re-publish)
- Record wheat's root type as `crown`, the value this project already labels it with, so no
  root-type vocabulary changes on either side
- Verify single-species content per collection
- Mark unrecoverable provenance fields as `null`

**Non-Goals:**
- Recovering the deleted `data_path` files (the images live in the artifact blob)
- Building a `publish-labels` CLI for *new* packages (that is #10/#26 scope)
- Multi-species `LabelCard` support (decision: stays single-species)
- Changing the `ModelCard` side of the registry, its `_ROOT_SLOTS`, or `SPECIES_VOCAB`
- Making `wheat` / `sorghum` / `medicago` valid in a *training config* (see D5)
- Introducing a label-side root-type vocabulary, or any root-type nickname/alias mechanism
  (`sleap-roots-contracts#34` tracks the latter; it is low priority and not a dependency here)

## Upstream dependency

**Conditional, and possibly none.** An earlier draft made a contracts release unconditional, on the
strength of D3's since-corrected `seminal` claim. With wheat's root type recorded as `crown`, the
only thing that could still require an upstream change is D7's field relaxation, and that is
decided by §2's findings rather than up front:

| upstream change | source | conditional? |
|---|---|---|
| relax `age_min`/`age_max`/`n_plants`/`n_scans` to `Optional` | D7 | yes — only if §2 cannot recover them |

If §2 recovers all four fields on all eight collections, **this change ships against a contracts
release that already exists** and §1 collapses to the pin catch-up alone.

Separately from this change's needs, contracts is at `0.1.0a8` while this repo pins `0.1.0a6`, so
the pin has `a7`/`a8` to absorb regardless. The `a3 → a6` bump went through its own change directory
(`archive/2026-08-05-update-contracts-pin-0-1-0a6`) with a full delta review, and that catch-up
should follow the same precedent rather than being folded in here silently — see task 1.1.

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

### D3: Wheat's root type is `crown`. No new vocabulary, on either side.

The wheat collection is *named* `wheat_5-14DAG_seminal_6nodes_labels`, and an earlier draft of this
document read that name as a root type the contract must learn. Two things were wrong with that.

**The factual claim was false.** The draft asserted the contract's `RootType` "already includes
`seminal` (confirmed)". It does not, on the pinned `0.1.0a6` or at contracts HEAD (`0.1.0a8`, two
releases ahead of our pin), where `models.py` reads:

```python
RootType = Literal["primary", "lateral", "crown"]
```

The string `seminal` does not appear anywhere in that source tree. So `LabelCard(root_type=
"seminal", ...)` raises a pydantic `ValidationError` today, and the "(confirmed)" was not confirmed.

**And the remedy was wrong too.** Correcting the fact, the draft proposed a new contract-owned
`LabelRootType` superset. That treats a naming difference as an ontological one.

**Decision: the card records `root_type: crown`. Nothing upstream changes, and no label-side
root-type vocabulary is introduced.**

At the age wheat is studied here the roots are technically seminal, but they are morphologically
indistinguishable from crown roots, and this project labels them as crown. That is not a new call
made for this change — it is a decision the project already made and has been operating on:

- The wheat collection was produced under `D:/SLEAP/20250529_seminal_root_generalist/wheat/`. The
  **same** `seminal_root_generalist` project also holds `older_rice/` and `younger_rice/` — and rice
  is registered with `root_type: crown` in `model_selection.yaml` (both
  `rice/older/crown/221208_113552` and `rice/younger/crown/220821_163331`). Wheat "seminal" and rice
  "crown" were deliberately trained as one generalist family precisely because they are the same
  thing to a model.
- `skeletons.yaml` already carries `root_type: crown` rows, so a wheat row needs no new value.

So `seminal` is a **nickname** for a root type the vocabulary already has, not a member missing from
it. A real nickname/alias concept — one place that records "wheat calls crown roots seminal", so
each repo stops reinventing a display-time remap — is filed upstream as
`sleap-roots-contracts#34`. It is **low priority and explicitly not a dependency of this change**;
this change stores the canonical value and leaves presentation to whatever lands there.

**What this decision costs.** The collection's original name is the only place the word `seminal`
survives, and the normalized name (D4) drops it. Anyone searching the new registry for "seminal"
finds nothing. That is why §2's archaeology records the original collection name on every card as
recovered provenance, and why this footnote exists in the collections table above: the mapping from
the old name to `crown` must be discoverable by someone who only knows the wheat data by its
seminal name.

**Why not add `seminal` to the contract anyway, label-side only.** It would encode a
species-specific nickname as a distinct anatomical category in the shared contract, and then every
consumer joining labels to models has to know that label `seminal` and model `crown` describe the
same roots. The generalist model above is exactly that join, and it would have to special-case it.
The naming problem is real; a vocabulary member is the wrong shape for it, which is what #34 is for.

**What this removes from the change.** No `LabelRootType`, no `LABEL_ROOT_TYPE_VOCAB`, no
`Label Root-Type Vocabulary` requirement, no unconditional contracts release, and no second
root-type vocabulary co-existing with the one #50 just consolidated. `metadata.py` and
`skeletons.py` keep using `ROOT_TYPE_VOCAB` exactly as #50 leaves them; only the *species*
vocabulary splits (D5).

### D4: Collection naming convention

Normalized names follow `{species}-{mode}-{root_type}` with hyphens. This matches the model
registry's convention **except for age, which is deliberately dropped** — the model side's
`collection_id()` carries an age suffix, and this one does not. Unlike a model, which is trained and
validated for a specific age window, a label set covers whatever ages were annotated; the range is
metadata on the card (`age_min`/`age_max`), not part of the collection's identity. Claiming full
parity would be wrong, and the difference is the one thing a reader comparing the two registries
will notice first.

Examples:
- `soybean-cylinder-lateral` (was `soybean_lateral_4nodes_v007_labels`)
- `arabidopsis-cylinder-primary` (was `cyl_arabidopsis_7-11DAG_primary_6nodes_labels`)
- `wheat-cylinder-crown` (was `wheat_5-14DAG_seminal_6nodes_labels` — see D3 on the name change)

Dropping age from the name is what makes the uniqueness guard load-bearing rather than incidental:
two label collections for the same species/mode/root type at different ages would collide where the
model side would not. Nothing in the current eight collides, which is exactly why the guard needs a
synthetic fixture rather than the real data to be exercised (task 4.6).

### D5: A label-side species vocabulary, not a widened `SPECIES_VOCAB`

`wheat`, `sorghum`, and `medicago` all have published label data and none has a model **in
`wandb-registry-sleap-roots-models`**. That is not the same as never having been modelled — the
`seminal_root_generalist` work in D3 trained on wheat — so the criterion here is registry presence
and a `model_selection.yaml` row, not the absence of any model anywhere. An
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
`cyl_arabidopsis_7-11DAG_primary_6nodes_labels`): a species already in `SPECIES_VOCAB`, a root type
already in `RootType`, and an age already in its name — so it exercises the link-and-alias path
without also depending on D5's vocabulary split or D7's outcome. A canary that needed either would
conflate two failures. (Since D3 no longer changes any vocabulary, it is no longer a source of
canary risk at all.)

### D7: The required-field gate — archaeology decides, with a stated fallback

`LabelCard` has **15 required, non-nullable fields**, not just the provenance block D1 covers:

```
species  mode  root_type  age_min  age_max  skeleton_name  node_count  node_names
n_frames  n_instances  n_plants  n_scans  images_embedded   (+ registry_id, version)
```

Most are fine. `n_frames`, `n_instances`, `node_count`, `node_names`, `skeleton_name` and
`images_embedded` are all derivable from the artifact blob, which §2.1 and §2.4 already plan to read. Four
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
2. **If every collection yields all four**, no contract change is needed at all — D3 no longer
   requires one, so this branch means the change ships against an existing release and §1 reduces
   to the `a7`/`a8` pin catch-up.
3. **If any collection does not**, those fields — and only those — are relaxed to `Optional` in a
   contracts release, and the unrecoverable ones are set to `null` under D1's rule. This is now the
   *only* thing that could make a release necessary, so §2's report decides whether §1 has a
   contracts change in it at all.

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
- **A contracts release may still be needed, but only D7 can require it.** If §2 recovers all four
  gated fields, none is needed. The pin still has `a7`/`a8` to absorb either way, independently of
  this change.
- **One vocabulary splits where #50 consolidated.** `SPECIES_VOCAB` and `LABEL_SPECIES_VOCAB` will
  co-exist, and a reader who remembers #50 may read that as regression. It is not the same case:
  #50 retired three hand-maintained copies of *one* set, while this defines a second set with a
  different membership and a stated reason for differing, derived from the first
  (`SPECIES_VOCAB | {...}`) so the relation cannot drift. Root type does **not** split — D3 is what
  keeps that side at exactly one vocabulary.
- **The word `seminal` disappears from the registry.** D3 records wheat's root type as `crown` and
  D4's normalized name drops the nickname, so someone who knows this data only as "the wheat seminal
  labels" cannot find it by that name. Mitigated by recording the original collection name on every
  card (§2) rather than by keeping the nickname in a vocabulary.
- **Old collection names remain.** They are not deleted, only de-aliased. Consumers using the old
  names directly (not via `production` alias) will still resolve, but won't get `LabelCard`
  metadata.

## Migration Plan

This change writes to a live wandb registry, creates collections that **cannot be renamed or
deleted**, and re-points `production` aliases. The forward order is D6's; what follows is the
rollback story for each step, since a failed `--execute` partway through the eight is the realistic
bad case.

**The live steps do not ship in this PR.** They run against production wandb after the code lands,
as their own PR with no CI, run by hand with a resolvable credential and explicit sign-off. That is
the precedent `update-model-card-selectors` set — its `## 6. Migration` is headed "gated, and a
separate PR after this change archives", and it carries a `6.0` rollback-prep task that snapshots
the current collection → aliased-version mapping *and rehearses the rollback on the canary* before
anything is touched. §7 here mirrors both: 7.0 is the snapshot and rehearsal, and §7 is the
follow-up PR's scope. This PR is §0–§6: code, offline tests, and the recorded archaeology.

**Forward:**

1. **Only if §2's report requires it** (D7): a contracts release relaxing the unrecovered fields.
   Otherwise this step is the `a7`/`a8` pin catch-up alone, which is not gated on anything here.
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
  **Resolved:** no, on the pin and at HEAD — and the question turned out to be the wrong one. Wheat's
  roots at this age are labeled `crown` in this project, so no vocabulary needs `seminal`. The
  nickname problem is real and tracked upstream as `sleap-roots-contracts#34`, low priority and not
  a dependency. See D3.
- **Q4 (open, settled by §2):** Are `age_min`/`age_max` recoverable for the two soybean collections,
  and are `n_plants`/`n_scans` recoverable for any of the eight? This is D7's gate. It is listed as
  open deliberately — §2 exists to answer it, and §3 cannot begin until it does.
