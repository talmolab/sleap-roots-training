# Tasks

TDD throughout: within each task the loop is **write failing test → confirm red → implement →
confirm green → `black --check` + `ruff check`**. That red→green loop is *local*; the **committed**
unit is always green (test + implementation land together, per the Tier 0.5 precedent — never push a
red commit). See the Commit Plan at the bottom.

Conventions that keep the base matrix green:
- Tasks are base-install-safe unless marked **[integration]** (needs the `train` extra;
  `@pytest.mark.integration` + `pytest.importorskip("sleap_nn")` **in the test body**, deselected by
  CI's `-m "not integration"`). `tests/test_config.py` holds both base-safe and the one integration
  test, so it MUST have **no module-top `sleap_nn` / `torch` import**.
- Test fixtures are **self-contained** — build config YAML in `tmp_path` (the
  `tests/conftest.py::tiny_matrix` pattern). Tests MUST NOT read `examples/…` (it lands in group 5).
- Define **one canonical fully-valid fixture** (seeded; `use_wandb` absent or fully paired) in
  `tests/conftest.py` and reuse it from group 2 onward, so adding the seed (3.x) and W&B (4.x)
  checks does not turn an earlier group's "good.yaml" red.

## 1. Experiment-metadata schema + composition (TDD)

- [ ] 1.1 Write the failing **oracle** test (`tests/test_config.py`): a minimal valid config — a
      well-formed `experiment` block plus a `sleap-nn` config naming one backbone + one head — loads
      via `load_config`, with defaults applied for omitted `experiment` fields.
- [ ] 1.2 Write the failing tests for `experiment`-metadata rejection: `experiment.species`,
      `experiment.mode`, or `experiment.root_type` outside its vocab raises a clear error naming the
      field; a config **missing** the `experiment` block (or a required field like `species`) is
      rejected; a config with an **unknown top-level key** (typo) is rejected naming the key, not
      silently dropped.
- [ ] 1.3 Confirm the tests fail (module not implemented yet).
- [ ] 1.4 Implement `sleap_roots_training/config.py`: `ExperimentConfig` (OmegaConf structured,
      reusing `SPECIES_VOCAB` / `MODE_VOCAB` from `registry/chooser.py` and a root vocab mirroring
      `registry/cards.py`'s `primary` / `lateral` / `crown`), `load_config(path)` (OmegaConf load;
      split the `experiment` block from the recognized `sleap-nn` keys, rejecting unknown top-level
      keys), a base-safe `_strip_experiment(cfg)` helper (pure OmegaConf, no `sleap_nn`), and the
      `experiment`-metadata checks in `validate_config(cfg)`. **No top-level `import sleap_nn`.**
- [ ] 1.5 Confirm green; add the lazy-import lock test: after `import sleap_roots_training.config`
      and a base-safe `validate_config(<good>)`, assert `"sleap_nn" not in sys.modules`.
      `black --check` and `ruff check` clean.

## 2. CLI `validate` subcommand (TDD)

- [ ] 2.1 Write the failing tests: `validate <good.yaml>` exits 0 with a success message (Click
      `CliRunner`); `validate <bad.yaml>` exits non-zero with the field-named error; `validate
      <malformed.yaml>` exits non-zero with a clean parse message (mapped to `ClickException`), not a
      traceback; `validate <missing-path.yaml>` exits non-zero (Click `exists=True`).
- [ ] 2.2 Confirm the tests fail.
- [ ] 2.3 Implement the `validate` subcommand in `cli.py` (`@main.command(name="validate")`,
      `@click.argument("config_path", type=click.Path(exists=True, path_type=Path))`), importing the
      new module under an alias (e.g. `from sleap_roots_training import config as training_config`)
      so it does not shadow the existing `registry.config` binding; map a validation failure and a
      YAML parse error to `click.ClickException` (non-zero exit).
- [ ] 2.4 Confirm green; run the full suite + lint.

## 3. Reproducibility + backend-safety (TDD)

- [ ] 3.1 Write the failing tests: a config that omits `trainer_config.seed`, sets it to `null`, or
      sets it to a non-integer is rejected naming `trainer_config.seed`; a config with an integer
      seed passes. (Base-safe — reads via `OmegaConf.select(..., default=...)`, not attribute access.)
- [ ] 3.2 Implement the seed check in `validate_config`; confirm green.
- [ ] 3.3 Write the failing **base-safe** skip-note test: with deep validation forced unavailable
      (see the seam in 3.4), `validate <seeded-good.yaml>` still runs the metadata + seed + W&B
      checks, prints a clear "deep `sleap-nn` validation skipped — install `[train]`" note, and exits
      0; and `validate <bad-seed.yaml>` still exits non-zero (the skip does not swallow a real
      base-safe failure).
- [ ] 3.4 Implement `to_sleap_nn_config(cfg)` (`_strip_experiment` then merge the rest onto
      `OmegaConf.structured(TrainingJobConfig())` and resolve) and the lazy-`import sleap_nn`
      deep-validation branch in `validate_config`, routed through a **monkeypatchable seam** (e.g.
      `config._deep_validation_available()` / `_import_sleap_nn()`) so 3.3 can force the absent
      branch deterministically even on a box where `[train]` is installed. Confirm 3.3 green.
- [ ] 3.5 **[integration]** Write + implement the deep-path test: `to_sleap_nn_config` on a config
      omitting `data_config.preprocessing` returns a **resolved** config containing a populated
      `preprocessing` block; and `validate_config`'s deep path delegates to `verify_training_cfg`
      (a config with no backbone/head fails via `sleap-nn`'s own `check_must_be_set`). Confirm it
      passes where `[train]` is installed and the base `-m "not integration"` suite still deselects it.

## 4. Per-epoch W&B logging (TDD + empirical verification)

- [ ] 4.1 Write the failing tests: `trainer_config.use_wandb = true` without `wandb.entity` or
      `wandb.project` is rejected naming the missing field; `use_wandb = false` **and**
      `use_wandb` **absent entirely** each require no target and pass (absent-as-false via
      `OmegaConf.select`).
- [ ] 4.2 Implement the W&B-enablement pairing check in `validate_config`; confirm green.
- [ ] 4.3 **Manual (observable, not CI):** run a short `use_wandb = true` job (fly sample or CPU/MPS —
      no real root data or GPU needed) and confirm `run.scan_history()` returns per-epoch rows
      (train/val loss + epoch). Record the exact check and its observed result in the training guide;
      do **not** fake an observable-only result as a passing CI test (Tier 0.5 precedent).

## 5. Example config + training guide + docs

- [ ] 5.1 Add `examples/arabidopsis_primary_cylinder.yaml`: a seeded, fully-resolved example whose
      `experiment` maps the filename correctly — `species: arabidopsis`, `root_type: primary`,
      `mode: cylinder` (NOT `mode: primary_cylinder`; `MODE_VOCAB` has no such value) — plus
      `data_config` incl. `preprocessing`, `model_config`, and `trainer_config.seed`.
- [ ] 5.2 Add a base-safe test asserting every `examples/*.yaml` passes the metadata + seed + W&B
      checks (guards the shipped example against rot; lives in `tests/`, inside the CI paths filter).
- [ ] 5.3 Add `docs/training.md` (config authoring → `validate` → the single `sleap-nn train
      --config <resolved>.yaml` hand-off → read `metrics.*.npz` → confirm per-epoch W&B via
      `scan_history()`). Enforce the DRY boundary with `docs/training-backend.md` (D6 pattern): the
      guide opens by pointing to the runbook for install / sample-data / GPU / `sleap-nn track`, and
      owns **only** `experiment`-authoring + `validate` + reading `metrics.*.npz` +
      `scan_history()`; add a reciprocal pointer from the runbook. Reference
      `examples/arabidopsis_primary_cylinder.yaml` rather than re-inlining a full config. For the TF
      baseline, **point to `docs/tf-reference.md`** and frame the numbers "as a range, context only"
      **without re-quoting the digits** and **without `oks_map`** (broken, #17) — avoiding a second,
      unlocked copy that would drift. Reserve the PyTorch-baseline section with an explicit marker
      that contains neither `TODO` nor `TBD`, e.g. `> Reserved — PyTorch baseline numbers are
      established by the follow-up baseline PR (roadmap Tier 1).`
- [ ] 5.4 Add the doc-contract test (`tests/test_training_docs.py`, mirroring
      `tests/test_backend_docs.py` incl. its `utf-8` + `\r\n`-normalization reads and fenced-block
      scoping): assert the fenced `validate` block, the fenced `sleap-nn train --config` block, the
      `scan_history()` verification token, the pointer to `docs/training-backend.md`, and the exact
      reserved-baseline marker string are all **present**, and that no `TODO` / `TBD` appears
      anywhere (so the reservation is locked in, yet a bare placeholder still fails).
- [ ] 5.5 Add `docs/**` and `examples/**` to the `pull_request` **and** `push` `paths` lists in
      `.github/workflows/ci.yml`, so the doc-contract + example tests actually run on docs-only PRs
      (incl. the follow-up baseline PR) instead of the lock being bypassable.
- [ ] 5.6 Update `openspec/project.md` Architecture Patterns (one line) from the day-0 bespoke-schema
      framing to the composition framing (a thin `experiment` block composed over `sleap-nn`'s
      `TrainingJobConfig`, validation delegated; the `validate` CLI checks configs). Add a **firm**
      one-line README pointer to `docs/training.md` next to the existing runbook pointer
      (pointer-only, do not restate).
- [ ] 5.7 Add a `docs/CHANGELOG.md` entry under the **existing** `[Unreleased] ### Added` (no second
      `### Added`, no `YYYY-MM-DD`): the `sleap-roots-training validate` CLI + composed config schema
      (the user-facing headline), the example config, and the training guide + doc-contract test.
- [ ] 5.8 **Manual ([train] box):** run `pytest -m integration tests/test_config.py` where `[train]`
      is installed and record in the PR body that the deep-delegation + preprocessing-materialization
      tests (3.5) pass — the only place the anti-crash guarantee is actually exercised.
- [ ] 5.9 Full suite (`pytest -m "not integration"` in an env **without** `[train]`, so the
      lazy-import safety is really proven) + `black --check src tests` + `ruff check src` green (match
      CI's scoping); `conda run -n talmo-sleap openspec validate add-config-schema --strict` clean.

## Commit Plan (green per slice; one PR; archive is a separate follow-up chore PR)

1. `docs(openspec): revise add-config-schema to compose around sleap-nn` — the 4 revised
   `openspec/changes/add-config-schema/*` files (no CI; `openspec/**` outside paths).
2. `feat(config): add experiment-metadata schema + load_config/validate_config` — `config.py` +
   group-1 tests (incl. the `sys.modules` lock).
3. `feat(cli): add validate subcommand` — `cli.py` + group-2 CLI tests.
4. `feat(config): require an explicit integer trainer_config.seed` — seed check + group-3.1 tests.
5. `feat(config): emit resolved sleap-nn config + gate/delegate deep validation` — `to_sleap_nn_config`
   + the seam + skip-note test (3.3/3.4) + the `[integration]` deep test (3.5).
6. `feat(config): require wandb.entity+project when use_wandb is true` — W&B pairing + group-4.1 tests.
7. `docs(training): add example config, training guide, doc-contract test + CI paths` — group 5
   (example, `example-validates` test, guide, doc-lock test, `ci.yml` paths, `project.md`, README,
   CHANGELOG).
8. `docs(training): record per-epoch W&B scan_history() + integration-run verification` — backfill
   the empirical results (4.3 / 5.8) into the guide/PR body after the manual runs.

Each commit is green (integration tests self-deselect in CI). Every push within the PR runs the full
matrix against HEAD, so docs-only commits 7–8 are still CI-checked.
