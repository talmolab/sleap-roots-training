# Proposal: Register the arabidopsis plate models as candidate cards

## Why

The arabidopsis `plate` row was deferred when the registry was first seeded (#3) because its models
could not be located. They are now identified. Benfica (Bloom) needs them in the wandb registry to try
the full-plate models on GraviScan plate sections. She needs them **there**, not in production.

## Owner decisions (2026-10-22)

| species | mode | ages | root type | model (`source_model_id`) | nodes |
|---|---|---|---|---|---|
| arabidopsis | plate | 2–7 | primary | `arabidopsis_plates/primary/230804_133809.multi_instance.n=606` | 8 |
| arabidopsis | plate | 2–7 | lateral | `arabidopsis_plates/lateral/231130_135922.multi_instance.n=38` | 3 |

- **Source:** the owner's curated copy, `SLEAP_arabidopsis_plates/PLATE_arabidopsis/PLATE_arabidopsis/`,
  dated 2025-07-09. It is byte-identical to the original training runs. The 2023 Box models Benfica
  found are older IAA runs, with n≤25.
- **Window: 2–7.** The primary model's labels span 2–7 DAG, so 7–14 (the models-downloader chooser
  table) is not used. The lateral model is one 7-DAG session, and shares the row.
- **Status:** `candidate` only. The row carries `status: candidate`, so the default `--verify` keeps
  meaning "exit 1 = real production drift".
- **Issue #3** is closed after the publish, with a pointer to a new promotion-tracking issue that holds
  the gates. The PR says `Refs #3`.

Metrics, frame counts and caveats live in `docs/arabidopsis-plate-models.md`.

## What changes

1. **Per-row `status`** (`production` default | `candidate`). It is matrix-local and never published.
   Mixed status for one model is rejected.
2. **Candidate rows are never linked to `production`.**
   - Under the default alias, an unscoped `--execute` skips them, printing
     `skipped (status: candidate)`.
   - Naming one with `--only` is refused before any wandb call, even with `--promote` or `--force`.
     See design D3.
3. **Status-aware `--verify`.** The expected set is the cards whose status equals the alias. Two new
   failures:
   - a candidate collection linked to production, which is checked fail-closed;
   - an alias no row carries.

   Orphan exclusion covers every collection the matrix produces. See design D2.
4. **`scripts/build_model_zip.py`** builds byte-reproducible `<model_id>.zip` archives, so a committed
   SHA256 can be re-derived from the curated copy. See design D4.
5. **Matrix:** 1 row (`status: candidate`), 2 checksums and 2 `origins` with `snapshot: null`, for a
   total of 10 rows, 13 checksums and 13 cards.
6. **Docs:**
   - `docs/arabidopsis-plate-models.md`: the consumer page.
   - The README runbook: status, the refusal, `--verify` and promotion mechanics. It also fixes
     already-stale lines.
   - CHANGELOG and roadmap.
7. **After merge, run by the owner:**
   - a local predict load smoke test;
   - the `candidate` publish;
   - verify;
   - a publish record;
   - the promotion issue;
   - the Slack handoff to Benfica.

## Production safety

Each item was verified in code on 2026-10-22:

- **Predict** lists only `production` artifacts (`sleap_roots_predict/model_registry.py`). The predictor
  template sets no `SRP_WANDB_MODEL_ALIAS`.
- **Bloom's `/model-cards` reader** (`services/workflows/model_cards.py`) only reads `production`
  memberships.
- **No plate scan reaches predict:** bloomctl writes `mode=cylinder` for every scan, and contracts'
  `_mode_for_scan` always returns `"cylinder"`.
- **No selector ambiguity:** `plate` is a valid `Mode` (contracts 0.1.0a9), and plate selectors cannot
  match a cylinder scan.
- **No hardcoded card counts** in any consumer.
- **No other alias reads:** no consumer reads `latest` or unaliased versions.
- **Existing cards are not re-published:** the publish is `--only` the two new ids, so no
  `weights_checksum` or Bloom idempotency key changes.

## Impact

- **Spec `model-registry`:**
  - ADDED: Per-Row Publication Status; Candidate Rows Are Never Linked to Production; Reproducible Model
    Archive Build; Committed Matrix Totals; Committed Arabidopsis Plate Row.
  - MODIFIED: Registry Verification Command; Orphaned Collection Reporting; Registry Seeding CLI with
    Confirmed Execution; First-Time Production Link Requires Promotion; Committed Wheat and Sorghum
    Rows.
  - The spec's Purpose line is amended at archive time.
- **Code:**
  - `registry/chooser.py`, `registry/cards.py`, `registry/publish.py`, `cli.py`
  - `registry/data/model_selection.yaml`
  - `scripts/build_model_zip.py` (new)
- **Tests:**
  - `test_registry_chooser.py`, `test_registry_cards.py`, `test_registry_publish.py`,
    `test_registry_cli.py`, `test_scripts.py`, `test_labeling_skeletons.py`
  - `tests/registry_fakes.py`, which gains a per-collection read-failure knob
- **Docs:**
  - `README.md`, `docs/arabidopsis-plate-models.md`, `docs/CHANGELOG.md`, `docs/roadmap.md`
  - the comments in `labeling/data/skeletons.yaml`
  - after merge: `docs/migration/2026-10-22-arabidopsis-plate-candidate-publish-record.json`
- **Compatibility:** no API, schema or published-metadata break. Custom matrices without `status` load
  unchanged.
  - **Changed behaviour:** under the default alias, an unscoped `--execute` skips candidate rows, and a
    `candidate`-alias `--verify` without `--only` now checks only candidate rows. That was a mode that
    previously always failed.
- **Out of scope:**
  - any `production` link, and the parity and trait checks;
  - plate dispatch in Bloom or the pipeline;
  - the chooser table's 7–14 row;
  - a plate lateral skeleton row;
  - retraining for sections.
