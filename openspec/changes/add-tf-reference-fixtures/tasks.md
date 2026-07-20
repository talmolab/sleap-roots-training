# Tasks

## 1. Capture the canonical TF payloads (data, no assertions yet)

- [x] 1.1 Add `scripts/pull_tf_reference.py`: given the entity/project/run-ids, write each run's
      `config` and `summary` as pretty-printed, key-sorted JSON to `tests/fixtures/tf_reference/`.
      Write deterministically for byte-identical re-runs on every OS: open with
      `newline="\n"`, `json.dump(..., indent=2, sort_keys=True, ensure_ascii=True)`, and a single
      trailing newline. It SHALL rely on an existing `wandb login` / `WANDB_API_KEY` (never write
      credentials) and import `wandb` lazily (inside `main`/`__main__`) so it is never imported at
      module top level.
- [x] 1.2 Run the script and commit the 14 payload files
      (`tests/fixtures/tf_reference/<run_id>.config.json` + `.summary.json`).
- [x] 1.3 Add `tests/fixtures/tf_reference/README.md`: provenance manifest — entity, project, group,
      run-name suffix (`_training_v000`), the seven run ids with `max_stride`, `sleap_version`
      (`1.4.1a2` = TF `sleap-train` backend), the `wandb` client version used to capture, capture
      date, "config/summary only — no secrets", and how to refresh via the script.

## 2. Shared fixture layer (TDD)

- [x] 2.1 Write a failing test asserting the shared fixtures exist and behave: a `tiny_matrix`
      (valid YAML written to a temp path) fixture loads via `chooser.load_selection_matrix`; a
      `stub_models_root` fixture stages the expected model dirs; and `clean_wandb_env` clears the
      `WANDB_*` / `SLEAP_ROOTS_MODEL_*` vars inside a test and restores them after.
- [x] 2.2 Run it to confirm it fails (fixtures not defined yet).
- [x] 2.3 Create `tests/conftest.py` with the shared fixtures: `tf_fixtures_dir`, `tiny_matrix` and
      `stub_models_root` lifted verbatim from `tests/test_registry_cli.py`, `tf_config(run_id)` /
      `tf_summary(run_id)` loaders that read the committed JSON directly (no import of
      `scripts/pull_tf_reference.py`), and a `clean_wandb_env` fixture (mirrors
      `sleap-roots-predict`).
- [x] 2.4 Migrate `tests/test_registry_cli.py` to consume the shared `tiny_matrix` /
      `stub_models_root` fixtures and to use `clean_wandb_env` in place of its manual
      `monkeypatch.delenv("WANDB_API_KEY")`; delete the now-duplicated inline definitions. Do NOT
      touch any assertions. Leave intentionally-inline malformed-input tests (e.g. in
      `tests/test_registry_chooser.py`) as-is.
- [x] 2.5 Enforce setup-only: confirm `pytest --collect-only -q` reports the same test-node count
      before and after the migration, and that the migration diff changes no line inside any
      `assert`. Run the full suite to confirm it stays green.

## 3. Registry test against the committed payloads (TDD)

- [x] 3.1 Write a failing test in `tests/test_registry_lineage.py`, parametrized over all seven
      committed run `config` fixtures: flatten each config to its full nested keyset (dotted keys +
      nested-dict leaves), build `lineage.build_lineage(<matrix_hash>)`, and assert (a) the lineage
      keys are disjoint from that full keyset and (b) `json.loads(json.dumps({**config, **lineage}))`
      equals `{**config, **lineage}` (round-trip stable).
- [x] 3.2 Run it; it exercises existing `build_lineage` + the `tf_config` loader — confirm it passes
      (adjust only the fixture loader if needed).

## 4. Reference-lock + fixture-integrity tests (TDD)

- [x] 4.1 Write `tests/test_tf_reference.py`. From the committed fixtures only: derive each run's
      `max_stride` from `config["model.backbone.unet.max_stride"]` (and assert it agrees with the
      nested `config["model"]["backbone"]["unet"]["max_stride"]`); assert the stride multiset is
      `{8: 1, 16: 2, 32: 2, 64: 2}`; assert `ijn85j6w` and `26ryyfu2` summaries carry no metrics
      (only `_wandb`); assert every summarized run's `oks_map` is below the broken ceiling (use
      `oks_map < 0.05`); group summarized runs by stride and assert the stride16 and stride32
      `dist_avg` [min, max] match the documented ranges with `pytest.approx(..., abs=1e-3)` (the doc
      rounds to 3 decimals; fixtures store full precision, e.g. stride16 max is 1.7104). Do NOT
      hard-code run-id→stride membership beyond the per-run `max_stride` assertion.
- [x] 4.2 In the same file, add a doc-lock test that reads `docs/tf-reference.md` and asserts it
      contains the sweep framing, the two same-stride range strings (`0.989`/`1.710` and
      `1.383`/`2.078`), the `oks_map` exclusion, and both missing-summary run ids — so the doc, not
      just test constants, is under lock.
- [x] 4.3 Add `test_tf_reference_fixtures_have_no_secrets`: scan every file under
      `tests/fixtures/tf_reference/` for credential markers (`WANDB_API_KEY`, a 40-hex key regex,
      `password`, `netrc`, non-empty `api_key`/`token`/`secret`) and assert none match, naming any
      offender.
- [x] 4.4 Add a presence check: exactly the 14 payload files (`<id>.config.json` + `.summary.json`
      for all seven ids), plus `README.md`, exist under `tests/fixtures/tf_reference/`, and
      `scripts/pull_tf_reference.py` exists.
- [x] 4.5 Confirm the lock actually binds: temporarily perturb one expected constant (or a copied
      fixture) to watch a test fail, then revert.

## 5. Documentation

- [x] 5.1 Write `docs/tf-reference.md`: the per-stride table, the "sweep of seven runs (one at
      stride8), not replicates" framing, the two same-stride ranges (~1.73× / ~1.50×), `oks_map`
      excluded with a reason, both missing-summary runs noted (stride8 has no usable result), and the
      observability gap tied to #1 + pointer to the Tier-1 per-epoch requirement in
      `add-config-schema`. Cross-reference `docs/roadmap.md` Tier 0 / Tier 1 rather than restating
      its guidance, to avoid drift.
- [x] 5.2 Reconcile `docs/roadmap.md` Tier 1: its "~1.5–1.7×" figure excludes the true stride16
      ~1.73×; update it to "~1.5–1.73×" (or have it cross-reference `docs/tf-reference.md` as the
      numeric source).
- [x] 5.3 Add a one-line pointer to `docs/tf-reference.md` from `README.md`.
- [x] 5.4 Add a `docs/CHANGELOG.md` entry under `[Unreleased]`.

## 6. Coordinate the per-epoch requirement into `add-config-schema` (isolated commit)

- [x] 6.1 Add an ADDED requirement (per-epoch W&B logging in the training-config schema) to
      `openspec/changes/add-config-schema/specs/training-config/spec.md`, with scenarios.
- [x] 6.2 Add a TDD task for it to `openspec/changes/add-config-schema/tasks.md` and note it in that
      change's `proposal.md` What Changes / Impact.
- [x] 6.3 Keep this as its own commit (bends "one change per PR"; call it out prominently in the PR
      description). `openspec validate add-config-schema --strict`.

## 7. Test-collection hardening + verification

- [x] 7.1 Add `[tool.pytest.ini_options] testpaths = ["tests"]` (and preserve the `integration`
      marker) to `pyproject.toml`, so the default run never recurses into `scripts/`.
- [x] 7.2 `uv run pytest` (existing 69 + new tests green; no network).
- [x] 7.3 `uv run black --check src/sleap_roots_training tests` and
      `uv run ruff check src/sleap_roots_training`.
- [x] 7.4 `openspec validate add-tf-reference-fixtures --strict`.
