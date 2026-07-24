## Why

The `sleap-roots-labels` registry cannot be joined to the models registry, and its label sets cannot
be traced to the experiment that produced them. Issue #10's audit of all eight collections found
provenance stored as boolean-key soup (`{"soybean": true, "4nodes": true}` — keys with the value
`true`, so nothing is queryable), `data_path` pointing at a Windows temp directory or an unreachable
`Z:` drive in **all eight** cases, and frame count and source experiment surviving only as prose in
the free-text description.

The `/build-labeling-package` workflow already computes every missing piece — `sample_manifest.csv`
(one row per labeled frame, with `scan_id`, `plant_qr_code`, `plant_age_days`, `accession_id`,
`accession_name`, `wave_number`, `view_index`, `frame_index`, `source_scan_path`, `source_image`,
`output_filename`), the Bloom `experiment_id`, accession names, and the canonical skeleton — and
throws it away at publish time. This change gives it somewhere to land.

This repo already has the publishing surface to mirror: `registry/publish.py` publishes a validated
`ModelCard` as an artifact and links it under an alias. Labels get the same treatment.

Blocks Tier 2's `run→artifact` lineage oracle and Tier 2.7 (node counts are today recoverable only by
parsing free-text descriptions).

## What Changes

- Add a **`label-registry`** capability: a `publish-labels` path mirroring `registry/publish.py` that
  takes a **labeling-package directory**, builds a `LabelCard`, validates it, and publishes the
  package as a `type="dataset"` artifact linked into `sleap-roots-labels`.
- **`sample_manifest.csv` is attached inside the artifact**, so row-level provenance travels with the
  labels — any consumer recovers the exact scans, plants, accessions, and source image paths without
  a working `Z:` mount.
- **Fail fast, before any network call**, on a missing or malformed required field, and on
  `n_frames` disagreeing with the manifest's row count.
- **Source the mode vocabulary from the contract.** `chooser.py`'s local `MODE_VOCAB` frozenset is
  replaced by `sleap_roots_contracts.Mode`, checked via `get_args(Mode)`. Values are unchanged; the
  owner moves. **This modifies the existing `model-registry` spec**, which requires the accepted
  vocabulary to live in one place in code.
- Bump the `sleap-roots-contracts` pin to **`0.1.0a6`** (the release carrying `LabelCard` and `Mode`;
  issue #10's "0.1.0a4" is stale — that version already shipped `resolve_params`, and `0.1.0a5` was
  taken concurrently by the prediction-manifest contract while the `LabelCard` PR was open).

Not in scope: backfilling or renaming the eight existing collections (#11); changing `embed=False` in
`build_slp_project.py`; retyping `ModelCard.mode`.

## Impact

- Affected specs: `label-registry` (new capability); `model-registry` (**MODIFIED** — mode vocabulary
  now sourced from the contract).
- Affected code: `src/sleap_roots_training/registry/publish.py` (or a sibling `publish_labels.py`),
  `registry/cards.py`, `registry/chooser.py` (`MODE_VOCAB` at `chooser.py:23` removed),
  `pyproject.toml` (pin), CLI, `tests/`.
- **Sequencing: depends on `talmolab/sleap-roots-contracts` shipping `add-label-selection-contract`
  as `0.1.0a6`.** This repo cannot pin it until it exists, so the contracts PR
  ([#24](https://github.com/talmolab/sleap-roots-contracts/pull/24)) merges and releases first.
