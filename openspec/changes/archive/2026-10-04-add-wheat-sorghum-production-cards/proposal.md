# Proposal: Register the wheat and sorghum models as candidate (not production) cards

## Why

Neither wheat nor sorghum has a model card, so every wheat and sorghum scan fails at predict with
`no models resolved`. bloom#993 counts 7,232 sorghum and 372 wheat scans among 10,524 staging scans
with no card. This change is **step 1** of talmolab/sleap-roots-pipeline#118: add the selection
rows, record their provenance truthfully, and publish the three models **under `candidate` only**.
talmolab/sleap-roots-training#72 is the authoritative spec. The change id keeps #72's
"production-cards" name for traceability.

## Owner decisions (2026-10-02 / 2026-10-03)

| species | mode | ages | root type | model (`source_model_id`) |
|---|---|---|---|---|
| wheat | cylinder | 5–14 | crown | `20250401_wheat_models/250328_095645.multi_instance.n=1658` |
| sorghum | cylinder | 3–14 | primary | `20250204_sorghum_experimental/sorghum_soybean_primary_6nodes/250203_181521.multi_instance.n=1689` |
| sorghum | cylinder | 3–14 | lateral | `20250204_sorghum_experimental/sorghum_soybean_lateral_4nodes/250203_214033.multi_instance.n=590` |

- Wheat seminal maps to `crown`.
- These are the exact models past production runs used. The registry's existing `sorghum-*`
  collections are different models.
- Provenance is recorded **per row and per model**, with **run-relative** locations (this is a
  public repo).
- The shared `SPECIES_VOCAB` is **widened**.
- **Two CLI guards** (decided after review):
  1. `--execute` under a non-default alias requires `--only`.
  2. Under the default alias, `--execute` refuses to link `production` to a collection for the first
     time unless `--promote` is passed.

## What changes

1. **Matrix:** 2 rows and 3 SHA256 checksums, taking it to 9 rows over 11 physical models. The
   checksums were recomputed on hpi_dev on 2026-10-03 and match #72 exactly.
2. **`SPECIES_VOCAB`** gains `wheat` and `sorghum`. This also widens training-config and
   labeling-metadata validation. `labeling build --species wheat` still fails loudly at the skeleton
   lookup, before anything is staged.
3. **Provenance — BREAKING for custom `--selection-matrix` files.**
   - Every row requires `source`.
   - A top-level `origins` map must cover exactly the referenced models, each with `snapshot`,
     `location` and `pinned_by`.
   - The yaml header stops claiming the xlsx as its single source of truth. Neither new row is in
     the snapshot's `model_chooser_table.xlsx`, and the wheat zip is not in the snapshot at all
     (design Context).
4. **Lineage — BREAKING for importers of `registry.lineage`** (there are no external importers).
   - The constants `SELECTION_MATRIX_SOURCE`, `SELECTION_MATRIX_DATE` and `MODELS_SNAPSHOT` are
     removed.
   - The seed run config records `row_sources` and `model_origins` for the in-scope cards, read from
     the matrix.
   - `build_lineage` takes the cards and the matrix.
5. **CLI safety — BREAKING for a first-time default-alias seed (now needs `--only … --promote`) and
   for a set-but-blank `SLEAP_ROOTS_MODEL_ALIAS` (now an error for `seed-registry`, not an empty alias):**
   - the two guards above;
   - the alias is stripped; `seed-registry` rejects a blank one, and other callers are unaffected;
   - every `seed-registry` invocation prints the target entity, registry, alias, where the alias came
     from, and the seed project, including under `--yes`, in a dry run and under `--verify`.
6. **Docs:**
   - the README seeding section is corrected (it wrongly says predict hardcodes `production`) and
     made canonical for the non-default-alias runbook;
   - stale "production alias" / "snapshot" docstrings are fixed;
   - CHANGELOG.
7. **Operator publish, after merge** (design D7): from a clean worktree at the squash SHA, publish
   the 3 cards under `candidate`, verify, and record them on #72 and #118. Each W&B and GitHub write
   needs the owner's go-ahead.

## Impact

- **Specs:** `model-registry`.
  - MODIFIED:
    - *Production Model Selection Matrix*;
    - *Seed Run Lineage*;
    - *Registry Seeding CLI with Confirmed Execution*;
    - *Collection Identifier Scheme* (made count-free);
    - *Environment-Driven Registry Configuration* (alias normalization);
    - *Legacy Model Directory Resolution* (checksum-pinned, not snapshot-pinned).
  - ADDED: *Selection Matrix Provenance*, *First-Time Production Link Requires Promotion*, and
    *Committed Wheat and Sorghum Rows*.
  - The `training-config` spec validates against `SPECIES_VOCAB` by name, so it needs no delta.
- **Code changed:**
  - `registry/chooser.py`, `registry/lineage.py`, `registry/config.py`, `registry/publish.py`
    (the promotion pre-pass), `cli.py`, and `registry/data/model_selection.yaml`;
  - docstrings and the pin message in `registry/__init__.py` and `registry/models.py`;
  - `scripts/regen_model_checksums.py` (docstring);
  - the header of `labeling/data/skeletons.yaml`.
- **Behaviour widened, code untouched:** `sleap_roots_training/config.py` (training `validate`),
  `labeling/metadata.py` and `labeling/skeletons.py`. `inventory/verify.py` is deliberately
  unaffected by the blank-alias rule (design D6).
- **Tests:**
  - registry and labeling suites, `tests/test_config.py` and `tests/conftest.py`;
  - `tests/test_scripts.py:403`;
  - shared publish fakes move to `tests/registry_fakes.py`.
- **Docs:** `README.md`, `docs/CHANGELOG.md` and `docs/roadmap.md`.
- **Live registry:** three new collections under `candidate`, and 3 source artifacts in seed
  project `sleap-roots-training`. **`production` is untouched.**
- **Consumers:** none until step 6. Predict reads `SRP_WANDB_MODEL_ALIAS`, default `production`, and
  no deployment template sets it. So `candidate` cards are invisible to production predict. Parity
  (predict#51) and the trait check (pipeline#120) read them by setting it to `candidate`.

## Out of scope

- Linking `production` (#118 step 6), and its acceptance checks.
- Wheat lateral traits.
- Requiring a checksum per referenced model at load time. Resolve already fails on that before any
  publish.
- Checking that predict's windows agree with traits' windows.
