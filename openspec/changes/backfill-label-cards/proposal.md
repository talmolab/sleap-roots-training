## Why

The 8 existing label collections in `wandb-registry-sleap-roots-labels` cannot be joined to the
models trained on them. Six collections point at deleted temp directories; two at a `Z:` drive that
resolves on one machine. Collection names use `cyl` where models use `cylinder`, and naming
conventions differ (`mode_species_age_root` vs `species-mode-root-age`). Without `LabelCard`
metadata, no downstream consumer — training parity (Tier 2.2), generalist sweeps (Tier 3), or
skeleton unification (Tier 2.7) — can programmatically discover what a label set contains.

#10 shipped the `LabelCard` contract (`sleap-roots-contracts#24`). This change backfills the 8
existing collections onto that contract: reconstruct provenance, normalize naming, and verify
single-species content — so labels become queryable and joinable to models.

## What Changes

- **New `label-registry` spec capability** defining the `LabelCard` backfill contract: how
  existing collections are mapped onto `LabelCard`, what fields are nullable for legacy data, and
  how normalized collection names are derived.
- **No root-type vocabulary change, on either side.** The wheat collection is *named* `seminal`;
  its card records `root_type: crown`. At the age wheat is studied here the roots are technically
  seminal but are morphologically indistinguishable from crown roots, and this project already
  labels them as crown — the wheat and rice data were trained together as one "seminal root
  generalist" family, with rice registered as `crown`. An earlier draft asserted the contract's
  `RootType` already accepted `seminal` (it does not) and then proposed adding it; both were wrong.
  See design.md D3. A real nickname/alias concept is tracked upstream as
  `sleap-roots-contracts#34` — low priority, and not a dependency of this change.
- **New label-side species vocabulary** (`LABEL_SPECIES_VOCAB`), a package-owned superset of
  `SPECIES_VOCAB` adding `wheat`, `sorghum`, and `medicago`. `SPECIES_VOCAB` is unchanged, so the
  model selection matrix and `experiment.species` in a training config keep accepting exactly what
  they accept today (D5).
- **New normalized collection names** following the model registry's `species-mode-root_type`
  pattern. Existing artifact versions are linked into the new collections (not re-published), so
  nothing already consumed by a training run is orphaned.
- **Provenance reconstruction** from artifact `description` free text, the lab share, and Bloom.
  Unrecoverable fields among the contract's seven `Optional` provenance fields are `null` — no
  values are fabricated. Four *required* fields (`age_min`, `age_max`, `n_plants`, `n_scans`) have
  no `null` available and are gated on archaeology; see D7.
- **Single-species verification** for each collection before stamping it with a `LabelCard`.

## Impact

- **New spec:** `specs/label-registry/spec.md`
- **Upstream:** *conditional, and possibly none.* A contracts release is needed only if §2's
  archaeology cannot recover `age_min`/`age_max`/`n_plants`/`n_scans`, in which case those fields
  relax to `Optional` (D7). Separately and regardless, the pin has `a7`/`a8` to absorb (this repo is
  on `0.1.0a6`, contracts is at `0.1.0a8`); that catch-up follows the
  `archive/2026-08-05-update-contracts-pin-0-1-0a6` precedent.
- **Affected code:**
  - `src/sleap_roots_training/registry/chooser.py` — new `LABEL_SPECIES_VOCAB`, defined as
    `SPECIES_VOCAB | {...}` so the superset relation cannot drift. **No** new root-type vocabulary
  - `src/sleap_roots_training/labeling/metadata.py` — `PackageMetadata` validates `species` against
    `LABEL_SPECIES_VOCAB`; its `root_types` keeps using `ROOT_TYPE_VOCAB` unchanged
  - `src/sleap_roots_training/labeling/skeletons.py` — skeleton-table rows validate `species`
    against `LABEL_SPECIES_VOCAB`; `root_type` unchanged
  - New `src/sleap_roots_training/registry/label_cards.py` — `LabelCard` backfill logic
    (provenance mapping, collection naming, metadata construction)
  - New `src/sleap_roots_training/registry/label_publish.py` — publish/link backfilled cards to
    the labels registry
  - `src/sleap_roots_training/cli.py` — new `seed-label-registry` subcommand
  - **Not touched:** `registry/cards.py`'s `_ROOT_SLOTS`, `chooser.SPECIES_VOCAB`,
    `chooser.ROOT_TYPE_VOCAB` (unchanged on *both* sides — see D3), `sleap-roots-contracts`'
    `RootType`/`LabelCard.root_type`, and `config.py`'s `experiment` validation
- **Affected tests:** new `tests/test_registry_label_cards.py`,
  `tests/test_registry_label_publish.py`; updates to `tests/test_labeling_metadata.py` and
  `tests/test_labeling_skeletons.py` for the vocabulary split
- **External:** reads from `wandb-registry-sleap-roots-labels` (existing); writes normalized
  collections back to the same registry. `sleap-roots-predict`'s parity harness is a downstream
  consumer.
- **Blocked by:** #10 (`LabelCard` contract — shipped); #50 (root-type vocabulary collapse — D5 and
  the §3 tasks are written against the post-#50 layout, and §3 edits files #50 touches). A contracts
  release is **not** a blocker unless §2's report triggers D7.
- **Ships in two PRs:** this one is §0–§6 (code, offline tests, recorded archaeology). §7 — the live
  production migration against `wandb-registry-sleap-roots-labels` — is a separate, manually run PR
  with explicit sign-off, following `update-model-card-selectors`' gating precedent.
- **Blocks:** Tier 2.2 (per-model parity), Tier 2.7 (skeleton unification), Tier 3 (generalist
  sweeps)
