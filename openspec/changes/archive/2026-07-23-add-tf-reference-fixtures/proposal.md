# Proposal: Test-fixture layer + committed TensorFlow reference baseline

## Why

The repo has no shared test-fixture layer — all nine test modules hand-roll YAML into `tmp_path`,
re-inventing the same setup — and the program roadmap's Tier-0 TensorFlow reference
(`docs/roadmap.md`) exists only as W&B run summaries that anyone can overwrite or delete. Committing
the canonical TF run payloads as fixtures both writes the reference down durably and lets the
registry code be exercised against realistic W&B payload shapes without network access.

## What Changes

- Add a shared **`tests/conftest.py`** + **`tests/fixtures/`** layer, factoring the repeated
  `tmp_path` YAML setup out of the existing tests into named fixtures (setup only — existing
  assertions are unchanged).
- Commit the **`config` + `summary` JSON** of the seven canonical runs from the
  `20250625_cyl_arabidopsis_primary_receptive_field` group under `tests/fixtures/tf_reference/`,
  plus a reproducible capture script and a provenance manifest.
- Make **at least one registry test** run against a committed real payload instead of a hand-rolled
  dict.
- Add **`docs/tf-reference.md`** documenting the baseline correctly: this group is a
  `model.backbone.unet.max_stride` **sweep (strides 8/16/32/64; two runs each at 16/32/64, one at
  stride8 — seven runs total), not replicates**, so metrics MUST NOT be pooled or ranged across
  strides; same-config spread is reported as a range from the two genuine same-stride pairs (stride16
  `dist_avg` 0.989–1.710; stride32 1.383–2.078); `oks_map` is excluded as broken (below ~0.05
  everywhere) with a stated reason; and the two runs with no summary metrics (`ijn85j6w` stride8,
  `26ryyfu2` stride64) are noted rather than dropped — including that stride8 has no usable result at
  all. The doc cross-references `docs/roadmap.md` rather than restating its guidance.
- Record the **observability gap** (`scan_history()` returns zero rows — only final eval metrics
  were logged) as a forward requirement on the training-config schema: the **per-epoch W&B logging**
  requirement is added to (and owned solely by) the in-flight `add-config-schema` change, per issue
  #8. This change only motivates it.

## Impact

- **Affected specs:** `test-fixtures` (ADDED), `tf-reference` (ADDED); `training-config` (ADDED
  requirement — recorded in the in-flight `add-config-schema` change, not here, per issue #8 and
  `docs/roadmap.md` Tier 1).
- **Affected code:** `tests/conftest.py` (new); `tests/fixtures/tf_reference/*.json` (new,
  committed payloads) + `tests/fixtures/tf_reference/README.md`; `scripts/pull_tf_reference.py`
  (new capture script); `tests/test_tf_reference.py` (new reference-lock + integrity tests);
  `tests/test_registry_lineage.py` (a test made to consume the committed payloads);
  `tests/test_registry_cli.py` (repeated `tiny_matrix` / `stub_models_root` / wandb-env setup lifted
  into `conftest.py`); `pyproject.toml` (`testpaths`); `docs/tf-reference.md` (new); `docs/roadmap.md`
  (reconcile the Tier-1 spread figure to ~1.5–1.73×); `README.md` (pointer); `docs/CHANGELOG.md`.
- **Coordination:** `openspec/changes/add-config-schema/` gains one ADDED requirement + task for
  per-epoch W&B logging (owned by that change; committed in isolation). It is unimplemented (0/13
  tasks), so this is additive, not a clobber.
- **Breaking changes:** none.
- **No secrets committed:** only `config`/`summary` JSON (verified free of API keys/tokens); never
  the W&B API key or netrc.
