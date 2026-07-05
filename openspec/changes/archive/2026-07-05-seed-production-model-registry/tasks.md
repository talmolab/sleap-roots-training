# Tasks

TDD throughout: for each group write the failing test(s) **first**, run to confirm they fail,
implement, then confirm green + `black --check` / `ruff check` clean. Commit the failing test + its
implementation **together** (never commit a red test as its own commit — CI must be green after every
commit). Groups 1–7 run with **no network**; the wandb calls in group 6 are exercised with a minimal
mock / fake `wandb.Api`; the real network behavior is verified only by the producer-side read-back +
the consumer's gated test (group 9).

**Commit plan (one PR, groups 0–8; group 9 is post-merge acceptance):** filing the plate issue (0.1)
is pre-work, not a commit; `ci: enforce --locked` (0.3) is its own commit and lands first;
`build(deps): add wandb + contracts` (0.2, pyproject **+** uv.lock **+** smoke test together) next;
then one `feat`/`docs` commit per group 1–8 — **except** the committed `model_selection.yaml` (with its
per-model SHA256 reproducibility anchor) lands as its **own** `data(registry): …` commit, split out of
group 1 for isolated PR review and clean `git blame` on the anchor. (Optional: split group 6 into
`lineage` + `publish/verify` commits — `lineage.py` has no dependency on `publish.py`.)

## 0. Dependencies, lock hygiene, and the deferred-plate issue

- [x] 0.1 **(pre-work, no commit)** File the follow-up GitHub issue for the deferred arabidopsis
      **plate** models (`arabidopsis_plates/primary` + `/lateral`, absent from the local snapshot /
      reference run) so its number is available to stamp into the YAML (task 1.1). If `gh`/remote is
      unavailable, record a tracked TODO and backfill.
- [x] 0.2 `uv add "wandb>=0.28.0,<0.29.0" "sleap-roots-contracts==0.1.0a3"` (runtime deps); **commit
      `pyproject.toml` + the regenerated `uv.lock` together**. Add a smoke test importing `wandb` and
      `from sleap_roots_contracts import ModelCard`; run it to confirm the environment resolves.
      (Verified: the alpha resolves under `uv` with no `--prerelease` flag; both have wheels for all
      six CI legs.)
- [x] 0.3 **(own commit, lands first)** Add `--locked` to **both** `uv sync` steps in
      `.github/workflows/ci.yml` (lint job + test job) and add `uv.lock` to the workflow `paths`
      filter, so lock/pyproject drift fails a PR (not just release). Confirm the current lock passes
      `uv sync --locked --dry-run`.

## 1. Selection matrix + age parsing + vocabulary (`registry/chooser.py`)

- [x] 1.1 Commit `registry/data/model_selection.yaml`: exported from the current
      `model_chooser_table.xlsx` (20250204); `#`-header stamping the source **URL + verification
      date**; **a per-model `sha256` field** recording the checksum of each source `<model_id>.zip`
      (pins the snapshot so the published `weights_checksum` is deterministic — resolution verifies
      against it); `age` kept as the native comma-list string; absent root types as `null`; plate row
      omitted with a comment referencing the issue from 0.1.
- [x] 1.2 **Write failing tests:** `load_selection_matrix()` (via `importlib.resources.as_file`)
      yields the expected **7 rows** (the plate row is omitted; 7 selection rows over 8 distinct model
      ids → 13 cards) with the right model ids; `parse_age_window("2, 3, 4, 5, 6, 7, 8")` → `(2, 8)`;
      `parse_age_window("5")` → `(5, 5)`; a gapped list (`"2, 3, 5"`) raises naming the row/gap; an
      unknown `species`/`mode` value raises naming the row + value.
- [x] 1.3 Run → confirm fail; implement `load_selection_matrix(path=<packaged default>)`,
      `parse_age_window(age_str)`, and the single-source vocabulary check; run → green; lint clean.

## 2. Card expansion (`registry/cards.py::expand_rows_to_cards`)

- [x] 2.1 **Write failing tests** covering every root-slot shape in the real matrix:
      primary + lateral + `null` crown → 2 cards (`primary`,`lateral`, no crown);
      primary + crown + `null` lateral (rice 2–5) → 2 cards (`primary`,`crown`, no lateral);
      **crown-only** (`null` primary + `null` lateral, rice 6–10) → exactly 1 `crown` card;
      the shared **primary** model (`canola_pennycress_arabidopsis/primary/…`) expands to **four**
      `primary` cards (canola 2–13, pennycress 2–14, arabidopsis multiplant-cylinder 2–14, arabidopsis
      cylinder 2–14) that **all share the same `source_model_id`** but **differ** in `species`, `age_max`
      (13 vs 14), and `mode` (multiplant cylinder vs cylinder);
      the shared **lateral** models likewise: `canola/lateral/…` → 2 cards (canola, pennycress) and
      `arabidopsis/lateral/…` → 2 cards (arabidopsis cylinder + multiplant) — each pair shares
      `source_model_id`, distinct `(species, mode)`. Assert the shared-`source_model_id` +
      distinct-`(species,mode,age_max)` property using **set/`Counter` comparison** (not list index),
      NOT metadata equality. (This must agree with the enumerated matrix-lock in 3.2.)
- [x] 2.2 Run → confirm fail; implement `expand_rows_to_cards(rows)` (one card per non-null root
      model); run → green; lint clean.

## 3. ModelCard metadata + collection ids + matrix lock (`registry/cards.py`)

- [x] 3.1 **Write failing tests:** `card_to_metadata(card)` returns **exactly**
      `{species, mode, age_min, age_max, root_type, source_model_id}` (assert the exact key set),
      omits `registry_id`/`version`/`weights_checksum`, and includes no `sleap_nn_version` key;
      **assert the raw `mode` value is preserved** — for the arabidopsis multiplant card
      `metadata["mode"] == "multiplant cylinder"` (space, NOT the hyphen slug) — this closes the exact
      silent-break where a slug leaking into metadata would still pass a key-set-only check yet break
      the consumer's `mode==` filter; the mapping validates against the **real**
      `from sleap_roots_contracts import ModelCard` when combined with placeholder
      `registry_id`/`version`/`weights_checksum` (success **despite** the extra `source_model_id` —
      `extra="ignore"`) and the resulting `ModelCard.sleap_nn_version is None`; a metadata case with
      `age_min == age_max` validates; `collection_id(card)` →
      `"{species}-{mode_slug}-{root_type}-age{min}-{max}"` with `mode_slug` replacing spaces with
      hyphens (`"multiplant cylinder"` → `arabidopsis-multiplant-cylinder-lateral-age2-14`).
- [x] 3.2 **Write a failing offline matrix-lock test:** loading the committed `model_selection.yaml`
      and expanding produces **exactly 13 cards**, all 13 `collection_id`s unique, and the
      `{collection_id → source_model_id}` mapping **equals this hand-transcribed literal** (RHS
      hard-coded from the xlsx, **not** derived from the YAML under test — else it's a tautology; over
      **8 distinct** model ids so a wrong re-point fails CI, no network, no models-root):
      - `soybean-cylinder-primary-age2-8` → `soybean/primary/221003_111420.multi_instance.n=1389`
      - `soybean-cylinder-lateral-age2-8` → `soybean/lateral/lateral_root_221006_172103.multi_instance.n=482`
      - `canola-cylinder-primary-age2-13`, `pennycress-cylinder-primary-age2-14`,
        `arabidopsis-multiplant-cylinder-primary-age2-14`, `arabidopsis-cylinder-primary-age2-14`
        → `canola_pennycress_arabidopsis/primary/240611_102513.multi_instance.n=743` (×4)
      - `canola-cylinder-lateral-age2-13`, `pennycress-cylinder-lateral-age2-14`
        → `canola/lateral/240611_083419.multi_instance.n=631` (×2)
      - `arabidopsis-multiplant-cylinder-lateral-age2-14`, `arabidopsis-cylinder-lateral-age2-14`
        → `arabidopsis/lateral/240130_140452.multi_instance.n=337` (×2)
      - `rice-cylinder-primary-age2-5` → `rice/younger/primary/230104_182346.multi_instance.n=720`
      - `rice-cylinder-crown-age2-5` → `rice/younger/crown/220821_163331.multi_instance.n=867`
      - `rice-cylinder-crown-age6-10` → `rice/older/crown/221208_113552.multi_instance.n=574`

      Also assert `len(set(source_model_ids)) == 8`, and a **shape check** that every `sha256` in the
      committed matrix matches `^[0-9a-f]{64}$` (catches a typo'd/missing checksum in CI without needing
      the model bytes; byte-correctness is the pre-merge dry run, task 8.1).
- [x] 3.3 Run → confirm fail; implement `card_to_metadata` + `collection_id`; run → green; lint clean.

## 4. Model directory resolution (`registry/models.py::resolve_model_dir`)

- [x] 4.1 Build tiny fixtures with **`zipfile` (stdlib)**, computing each fixture zip's SHA256 **at
      build time** from the just-built bytes (zip bytes aren't reproducible across builds — never
      hard-code a sha): a `<model_id>.zip` (stub `best_model.h5` + `training_config.json`, **plus a
      `.DS_Store`/`__MACOSX/` junk member** to exercise the filter); a `.zip` whose recorded sha is
      wrong (mismatch); a `.zip` that unzips to a dir **missing `best_model.h5`** (post-unzip check);
      and an already-unzipped `<model_id>/` dir.
- [x] 4.2 **Write failing tests:** resolving the archive form **verifies the SHA256, extracts to a
      fresh temp dir (not in-place), omits the junk members**, returns the dir (compare **`Path`**),
      and confirms both essential files; a checksum mismatch / missing dir-and-zip / post-unzip
      missing essential file each raises naming the model id + specific failure; the already-unzipped
      dir form returns as-is (dev convenience) and is flagged **not-pin-enforced**;
      **determinism:** `junk_filter` is order-independent and drops only the junk names, and extracting
      the same zip bytes to two roots yields the **same relative-path set + same per-file content
      hashes** (the offline half of the deterministic-`weights_checksum` claim).
- [x] 4.3 Run → confirm fail; implement `resolve_model_dir(model_id, models_root, matrix)` (archive
      form: SHA256-verify → `zipfile.extractall(members=<non-junk>)` into a `tempfile`/`platformdirs`
      cache dir, canonical layout, Zip-Slip-safe; dir form: return as-is, mark unpinned); run → green.

## 5. Environment-driven config (`registry/config.py`)

- [x] 5.1 **Write failing tests** (monkeypatch env): defaults when unset (entity/registry/alias);
      overrides honored; `require_api_key()` raises a clear error when `WANDB_API_KEY` is unset and
      passes when set.
- [x] 5.2 Run → confirm fail; implement `resolve_registry_config()` (`WANDB_ENTITY`,
      `SLEAP_ROOTS_MODEL_REGISTRY`, `SLEAP_ROOTS_MODEL_ALIAS` with defaults) + `require_api_key()`;
      run → green.

## 6. Lineage + wandb publish/link/seed driver (`registry/lineage.py`, `registry/publish.py`)

- [x] 6.1 Document (design note, not implementation) the target wandb-0.28 call sequence:
      lazy-import `wandb` inside the function; `wandb.Artifact(name=collection_id, type="model",
      metadata=card_to_metadata(card))`; `add_dir(model_dir)` (the dir is **already junk-free** —
      exclusion happened at extraction, since `add_dir` has no `exclude=`); `logged =
      run.log_artifact(art, type="model")`; `logged.wait()`; `run.link_artifact(logged, target,
      aliases=[alias])` where `target = f"{cfg.entity}-org/wandb-registry-{cfg.registry}/{collection_id}"`
      (literal forward slashes).
- [x] 6.2 **Write failing tests** (offline) for lineage: `_resolve_git_sha()` — with the env override
      `SLEAP_ROOTS_TRAINING_GIT_SHA` set → returns it; with a mocked successful `git` → returns the
      SHA (and `+dirty` when porcelain non-empty); with `git` unavailable / no `.git` (mock failure)
      → returns `f"v{version}"`/`"unknown"` and **never raises**; `build_lineage(matrix_path)` returns
      the exact key set (`git_sha`, `git_dirty`, **`matrix_content_sha256`** (of the loaded YAML),
      `selection_matrix_source`, `selection_matrix_date`, `models_snapshot`, and the three
      `*_version`s) with versions from `importlib.metadata` and the matrix hash computed from the file
      bytes.
- [x] 6.3 **Write failing minimal-mock tests** for `publish_card(run, card, model_dir, cfg)`:
      artifact `type == "model"`; artifact metadata **equals exactly** `card_to_metadata(card)`
      (same key set, contains **none** of `registry_id`/`version`/`weights_checksum`, no lineage
      keys); `add_dir` called with the (junk-free) model dir; the call **order** is
      `log_artifact(type="model")` → `logged.wait()` → `link_artifact(...)` (wait **before** link);
      `link_artifact` called with the **exact forward-slash** target string literal and
      `aliases=[alias]`.
- [x] 6.4 **Write failing tests** for the driver `seed_registry(cards, models_root, cfg, run,
      api=None, force=False, only=None)` (inject a fake `wandb.Api`): validates that **all in-scope**
      cards resolve **before** publishing any (a missing in-scope model aborts with zero `publish_card`
      calls); two cards sharing one physical dir yield **two** `publish_card` calls with **distinct**
      `collection_id`s (never one artifact into two collections); the two rice crown cards yield **two**
      `link_artifact` calls to **distinct** targets (`rice-cylinder-crown-age2-5`,
      `rice-cylinder-crown-age6-10`) each `aliases=[alias]` (offline half of "both production"); a
      duplicate `collection_id` aborts naming the collision; `_collection_has_production(...)` → `True`
      makes the card **skip** (reported skipped) when `force=False`; `force=True` **publishes +
      re-points** (reported moved); `only={id}` **narrows both validation and publish** to that card
      (a canary with only its model staged does **not** abort on the other 12 missing); `only={two ids}`
      is repeatable; `only={unknown-id}` **raises** naming the unknown id; per-card progress is logged.
- [x] 6.5 **Write failing tests** for `verify_registry(cfg, expected_collections, api=None)` (fake
      `wandb.Api`): it queries `api.artifact_collections(project_name=project, type_name="model")` /
      `api.artifacts(...)` using `project = f"{cfg.entity}-org/wandb-registry-{cfg.registry}"` (the
      **registry** project, not a run project) and returns/reports, per expected collection, whether a
      production-aliased artifact is present; missing any → a non-empty "missing" result.
- [x] 6.6 Run → confirm fail; implement `lineage.py` + `publish.py` (incl. `seed_registry` `only=`
      scoping + unknown-id guard + `verify_registry`); run → green; lint clean.

## 7. Seed CLI with confirmed execution (`cli.py`)

- [x] 7.1 **Write failing tests** (Click `CliRunner`, using `--selection-matrix <tiny.yaml>` + a stub
      models-root so tests stay light): default `seed-registry --models-root <fix>` (no `--execute`)
      prints planned collections + metadata, resolves each model dir (reports a missing one), makes
      **no** wandb call (assert monkeypatched `wandb.init`/`publish_card` never invoked), exits 0;
      `--execute` with `WANDB_API_KEY` **unset** fails fast **before** any confirm prompt and never
      calls `wandb.init`; `--execute` (key set, no `--yes`) with declined confirm (`input="n\n"`)
      publishes nothing; `--execute --yes` (key set, `publish_card`/`wandb.init` mocked) proceeds,
      calls `wandb.init(config=<lineage>)`, and reports the collections; `--execute --yes` with an
      unresolvable in-scope model fails fast before any publish (CLI mirror of the driver check);
      `--execute --yes --only <id>` passes that `only` through; `--verify` (mocked `verify_registry`)
      runs **without** `--models-root`, reports present/missing collections, exits non-zero when any is
      missing, and fails fast if `WANDB_API_KEY` is unset; missing `--models-root` errors cleanly for
      dry-run/`--execute` **but not** for `--verify`.
- [x] 7.2 Run → confirm fail; implement the `seed-registry` subcommand (dry-run default; `--execute`
      → `require_api_key` **then** `click.confirm` unless `--yes` + warn on a dirty tree; `--verify`
      → `require_api_key` then `verify_registry` (no `--models-root` needed); `--only` repeatable +
      unknown-id fail-fast; lazy-import `wandb` in the network branches;
      `wandb.init(job_type="seed_registry", config=build_lineage(matrix_path))`;
      `seed_registry(..., force=--force, only=--only)`). Run the full suite + `black --check` +
      `ruff check` → green.

## 8. Provenance, docs

- [x] 8.1 **(hard pre-merge gate — the only byte-check of the SHA256 anchor)** Run `seed-registry`
      (default dry run) against the **real** `models-downloader` tree + the committed YAML; confirm it
      resolves all 8 physical model zips (each SHA256-verifying) and produces the expected **13** cards
      / collections; capture the output in the PR description. Also ship a tiny documented helper to
      (re)generate the per-model `sha256` column so the anchor is reproducibly maintained on future
      snapshot updates.
- [x] 8.2 Add a `docs/CHANGELOG.md` `[Unreleased]` entry **and** the from-scratch Keep-a-Changelog
      compare-link definitions (`[Unreleased]` compare link + the `[0.0.1a0]` tag link); add a README
      section documenting the producer env vars (`WANDB_ENTITY`, `SLEAP_ROOTS_MODEL_REGISTRY`,
      `SLEAP_ROOTS_MODEL_ALIAS`, `WANDB_API_KEY`), the `seed-registry` default-dry-run / `--execute` /
      `--yes` / `--force` / `--only` / `--verify` usage + the **rerun contract** (already-seeded
      collections skipped; `--force` re-points; re-run resumes after a partial failure;
      `weights_checksum` is a whole-artifact digest — the snapshot is SHA256-pinned so it's
      deterministic, and re-seeds reuse the identical snapshot; **caution:** `--execute --yes`
      publishes non-interactively — do not bake into shared automation), the **canary-first** rollout,
      and the cross-repo env mapping — explicitly: the producer's `SLEAP_ROOTS_MODEL_REGISTRY` must
      equal the consumer's `SRP_WANDB_REGISTRY` (which has **no consumer default** — operator must set
      it), the entity default is a shared cross-repo invariant, and `WANDB_ENTITY` is wandb-native.
      Also document the two accepted cross-repo consequences: seeded `mode` strings (esp. arabidopsis
      `cylinder` vs `multiplant cylinder`) are a contract A3-params must emit exactly, and shared-weight
      cards yield up to 4× warm-cache materialization (known/accepted; predict-side dedupe is a
      follow-up). Reference `config.py` (defaults) and `chooser.py` (vocabulary) as the single sources
      rather than re-hardcoding. Add a **"W&B compatibility"** subsection stating the tested writer/
      reader pair (producer `wandb 0.28.x` ↔ consumer `wandb 0.21.3`, canary-verified) as a
      compatibility contract, and the rule that **raising the producer's `<0.29` cap requires a
      re-canary + a consumer floor bump** (converts the point-in-time canary into a durable forward
      contract — see D10).

## 9. Acceptance — canary-first, then close the loop with the consumer

- [x] 9.0 **Prep the models-root:** obtain the canonical snapshot (Salk Box / the `models-downloader`
      tree) and place the per-model `<species>/<root>/<id>.zip` archives under `--models-root`
      (resolution unzips + SHA256-verifies them; no manual unzip needed). Confirm a default dry run
      resolves all 8 physical models.
- [x] 9.1 **(requires explicit user go-ahead + `WANDB_API_KEY`) — CANARY:** seed a **representative
      pair** (`seed-registry --execute --only arabidopsis-multiplant-cylinder-primary-age2-14 --only
      rice-cylinder-crown-age6-10`) to the eberrigan `sleap-roots-models` registry — the arabidopsis
      card is the gnarliest shape (**space in `mode`** `"multiplant cylinder"` **and** a member of the
      4× shared-weight dedup set), and the rice card exercises the two-crown/two-collection shape, so
      the round-trip stresses the space-in-mode + dedup + two-collection cases rather than a trivial
      soybean primary. Then run the consumer
      gate (9.2) on the canary. This de-risks the **wandb version skew** (0.28 writer vs 0.21.3 reader)
      before publishing all 13. If it round-trips, seed the rest (`seed-registry --execute` — the
      idempotent skip leaves the canary untouched) and run `seed-registry --verify`; also run the
      **producer-side read-back** using `project = f"{entity}-org/wandb-registry-{registry}"` (**not**
      the run project) to assert the production alias is present on every seeded collection.
- [x] 9.2 **(required rollout gate)** In the `sleap-roots-predict` checkout (branch
      `add-warm-model-worker`): `WANDB_API_KEY=… SRP_WANDB_ENTITY=<entity> SRP_WANDB_REGISTRY=<registry>
      uv run pytest -m wandb -q` → green; **assert on the derived values, not just "green"**: a known
      card's `registry_id` (versionless qualified name) and `version` (concrete) are as expected,
      `materialize()` downloads + caches, and the seeded `species`/`mode` values are exactly the ones
      predict selects on (the vocabulary reconciliation point).
- [x] 9.3 Report back: the final entity + registry + alias + published collections/artifacts **and the
      seed run URL** (a durable repo-side pointer to the producing run, so it can flip its default
      source); the ask for predict to pin a **tested wandb range** (min `>=0.21.3,<0.22.0`, ideally
      converge up to the producer's `>=0.28.0,<0.29.0` band gated by a re-canary) **and add a CI marker
      that re-verifies on a bump** — not just a bare floor; the durable record of the tested pair
      (writer 0.28.x ↔ reader 0.21.3, canary-verified <date>) in both repos' docs; the seeded
      `mode`-string contract for A3-params (arabidopsis `cylinder` vs `multiplant cylinder`); the
      accepted shared-weight 4× warm-cache note (predict-side dedupe by `weights_checksum` follow-up);
      and the roadmap status precision — **A3-training is partial** (legacy feeds-half done, native
      sleap-nn rebuild pending) and **A3-predict is short of its parity gate** — so neither is marked ✅
      when the external *sleap-roots-pipeline* bloom-integration roadmap is updated.
