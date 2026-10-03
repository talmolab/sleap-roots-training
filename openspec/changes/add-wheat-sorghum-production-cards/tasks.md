# Tasks

## How this is executed

**TDD, committed green.** `openspec/project.md` mandates test-first, and pytest must pass before
every commit. So each numbered group below is **one commit unit**, worked in four steps:

1. Write the unit's tests.
2. Run them and confirm each new one fails **for the stated reason**. Tests marked *(guard)* pass
   already; they are regression guards.
3. Implement.
4. Commit, only when green.

Red tests are never committed alone. Paste each unit's red-run summary into the PR description. Each
unit ticks its own boxes in the same commit.

**Check every commit before pushing** (non-interactive, and it does not move the base):
`git rebase --keep-base --exec "uv run --locked pytest -m 'not integration' -q" origin/main`. If a commit
is red, the rebase stops there; `git rebase --abort` restores the branch.

**CI-equivalent checks** (from `ci.yml`):

- `uv run --locked pytest -m "not integration" --cov=src/sleap_roots_training --cov-fail-under=95 tests/`;
- `uv run --locked black --check src/sleap_roots_training tests`;
- `uv run --locked ruff check src/sleap_roots_training`.

A bare `uv run pytest` also runs integration tests, which download from W&B.

**Test locations.** Tests are cited by **name**. Line numbers drift once earlier units edit a file.

**Order.** The rows land **last** (group 10), after truthful lineage and both guards, so no commit has
the rows without the guards. Groups 13–14 are operator work:

- group 13 runs before merge and makes no writes;
- group 14 runs **after merge** (design D7).

Ids and strings are written once, in `design.md` (Context and D1).

## 0. Decisions (owner, 2026-10-02 / 2026-10-03)

- [x] 0.1 The three models, windows and root types in `proposal.md`. Wheat seminal maps to `crown`.
      The existing `sorghum-*` collections are not substituted.
- [x] 0.2 Provenance is recorded per row (`source`) and per model (`origins`).
- [x] 0.3 Origins are run-relative, with no share paths.
- [x] 0.4 Widen the shared `SPECIES_VOCAB`.
- [x] 0.5 Guard 1: under `--execute`, a non-default alias requires `--only`.
- [x] 0.6 Guard 2: a first-time `production` link requires `--promote`. This includes alias
      normalization and the target echo. The owner chose this on 2026-10-03, after review showed that
      guard 1 alone still let two things reach `production`: a lost alias prefix, and the post-merge
      window.

## 1. Commit `docs(openspec): propose add-wheat-sorghum-production-cards`

- [x] 1.1 Commit the change directory alone. It triggers no CI.

## 2. Commit `test(labeling): use alfalfa, not wheat, as the out-of-vocabulary crop`

- [x] 2.1 Change `wheat` to `alfalfa` in three tests, and in the `match=` of the third:
      - the species-rejection test in `tests/test_labeling_cli.py`;
      - the one in `tests/test_labeling_metadata.py`;
      - the one in `tests/test_labeling_skeletons.py`.

      *(guard)* They stay green, and they must stay green after group 3.

      Note in the PR: `tests/test_labeling_skeletons.py` (here) and `skeletons.yaml` (3.4) are in the
      `push: main` paths of `verify-skeleton-table.yml`, so that job runs once on merge. Recent runs
      finish in about 13 seconds.

## 3. Commit `feat(vocab): add wheat and sorghum to SPECIES_VOCAB`

- [x] 3.1 Tests (`tests/test_registry_chooser.py`):
      - `{"wheat", "sorghum"} <= chooser.SPECIES_VOCAB`. *Red: both are absent.*
      - An inline matrix with a `wheat` row and a `sorghum` row loads. *Red.*
      - Every member equals `.lower()`. *(guard)*
      - A row with `species: alfalfa` is still rejected, with the row-numbered message. *(guard)*
- [x] 3.2 Test (`tests/test_config.py`): an experiment config with `species: wheat` validates, and one
      with `species: sorghum` does too. *Red.*
- [x] 3.3 Test (`tests/test_labeling_cli.py`, mirroring the pennycress test):
      `build --species wheat --root-type crown` exits non-zero, with `No labeling skeleton` in the
      output, no traceback, and no output directory created. *Red: today it fails at the metadata
      vocabulary check instead.*
- [x] 3.4 Implement:
      - add both species to `SPECIES_VOCAB`;
      - in its comment, drop "models-downloader" and state the lowercase common-name rule
        (design Context);
      - add one line to `labeling/data/skeletons.yaml`'s header: wheat and sorghum are in the
        vocabulary for the model registry, and have no skeleton row yet.

## 4. Commit `test(registry): share the publish fakes and a matrix-writing helper`

- [x] 4.1 Move the whole fakes block from `tests/test_registry_publish.py` into
      `tests/registry_fakes.py`, and import it back. pytest won't collect the new file, since it
      doesn't match `test_*.py`. The block is:
      - `_FakeRun` with `_FakeLogged`;
      - `_FakeApi` with `_FakeCollection`;
      - `_FakeArtifact`, `_FakeArt`, `_SELECTORS_META` and `_LEGACY_META`.

      Make `_FakeApi.artifacts(type_name, name)` **raise `ValueError`** for a name with no collection,
      matching wandb 0.28 (`wandb/apis/public/artifacts.py:918-924`). Fix any existing test that
      relied on `[]`.
- [x] 4.2 Extend `_FakeRun` for CLI use:
      - `project` and `entity` attributes;
      - `finish(exit_code=None)`;
      - a **list** of `(target, aliases)` link calls, not only the last one.
- [x] 4.3 Add a conftest helper,
      `write_matrix(tmp_path, rows, *, checksums=None, origins=AUTO, drop=(), override=None)`:
      - by default, derive each row's `source` and an `origins` entry for every referenced id;
      - accept `drop`/`override` keyed per row (`("row", i, key)`) and per model
        (`("origin", model_id, key)`);
      - support writing `origins` as absent, `null` or a list.

      Every new loader test uses it.
- [x] 4.4 In `tests/test_registry_cli.py`:
      - Add an autouse fixture that replaces `wandb.Api` with a spy that records the call and raises.
        Then no CLI test can reach api.wandb.ai by accident. Tests that need a registry override it
        with `_FakeApi`.
      - Add `isolate_wandb_env` to `test_execute_declined_publishes_nothing`.

## 5. Commit `feat(registry)!: require per-row source and per-model origins in the selection matrix`

- [x] 5.1 Data first. These stay green on today's loader, because `_parse_matrix` reads only
      `species`/`mode`/`age`, the three id slots and `checksums`:
      - `model_selection.yaml`:
        - add `source` to the 7 rows and an `origins` entry for each of the 8 models (design D1
          strings);
        - rewrite the header. It drops the single-source-of-truth claim and the "8", keeps the
          plate-row omission note, and states the models-downloader URL once.
      - Add `source`/`origins` to every inline matrix that loads successfully: `TINY_MATRIX` in
        `tests/conftest.py`, the string-model-id control matrix in `tests/test_registry_chooser.py`,
        and `test_dry_run_resolves_real_zip`'s matrix.
      - Leave alone the matrices that assert an earlier failure (missing age, `turnip`, `teacup`,
        malformed, non-string model id, the CLI teacup/malformed cases), and the lineage
        `b"models: []"` hashes.
- [x] 5.2 Loader tests (`tests/test_registry_chooser.py`, via `write_matrix`). Each expects a
      `ValueError` naming the row or model and the key. *Red: the loader ignores both keys.*
      - `source`: (a) missing; (b) `""`; (c) `5`.
      - (d) A referenced id with no origin.
      - (e) No `location`; (e2) `location: ""`.
      - (f) No `pinned_by`; (f2) `pinned_by: 5`.
      - (g) `snapshot: 20250204` unquoted, so an int.
      - (h) A stale origin.
      - (j) No `origins` key, and `origins: null`. Both report the first uncovered id.
      - (k) `origins` as a list, which names `origins`; a scalar entry, which names the model. Neither
        raises `KeyError`, `TypeError` or `AttributeError`.
      - (l) An origin with no `snapshot` key.
      - (m) Row 0 references an id with no origin, and row 1 has no `source`. The error names row 1
        and `source`.
      - (n) *(guard)* An out-of-vocabulary row with no `source` reports the vocabulary error. A
        non-string `primary_model_id` with no `source` reports the `primary_model_id` error.
      - (i) A valid matrix parses `origins` into `ModelOrigin` records, including `snapshot=None`.
- [x] 5.3 Committed-file tests. *Red until 5.1; write them first if running strictly red-first.*
      - Every row's `source` is a non-empty `str`.
      - The `origins` keys are exactly the referenced ids.
      - No `location` starts with `/`, or contains `:\`, `\\`, `hpi` or `users/`.
- [x] 5.4 CLI test (`tests/test_registry_cli.py`, `_no_wandb`). Run it once with a row missing
      `source` and once with a referenced id missing from `origins`. Each run exits non-zero, with
      `Error:` in the output, `row 0`/`source` or the model id in the output, and
      `not isinstance(result.exception, ValueError)`. *Red.*
- [x] 5.5 Implement (design D2):
      - add `ModelOrigin`, `SelectionRow.source` (no default) and `SelectionMatrix.origins`;
      - order the checks in `_parse_matrix`: required keys → vocabulary → model-id types → `source` →
        (after all rows) `origins`;
      - in the same step, change `tests/test_registry_cards.py::_row` (16 call sites) to pass
        `source="test row"` by keyword. It raises `TypeError` until the field exists;
      - rewrite the module docstring. It currently says the matrix mirrors the xlsx row for row.

## 6. Commit `feat(registry)!: record row_sources and model_origins in seed lineage`

- [x] 6.1 Tests (`tests/test_registry_lineage.py`). *Red: the signature and keys are new.*
      - `build_lineage(sha, cards, matrix)` returns exactly these keys: `git_sha`, `git_dirty`,
        `matrix_content_sha256`, `row_sources`, `model_origins`, `sleap_roots_training_version`,
        `wandb_version` and `sleap_roots_contracts_version`.
      - None of the three old keys is present, and none of the three old constants exists in the
        module.
      - Scoping:
        - the `canola_pennycress_arabidopsis` primary card alone → 4 `row_sources` and 1
          `model_origin`;
        - `CANOLA_LATERAL` alone → its 2 rows;
        - all committed cards → every row and every origin.
      - `model_origins` is sorted by `model_id`. `row_sources` is in file order, with the raw `age`
        string.
      - JSON round-trip.
      - The real-TF-run-config disjointness test is kept, under the new signature.
- [x] 6.2 Implement (design D3):
      - delete the three constants;
      - rewrite the module docstring (it says "six selection keys");
      - make the `build_lineage` call site in `cli.py` pass the in-scope `all_cards` and the `matrix`.

## 7. Commit `feat(registry): normalize the model alias and always print the target`

- [x] 7.1 Tests. *Red: there is no strip, no blank check and no echo.*
      - `tests/test_registry_config.py`:
        - `" production "` resolves to `"production"`;
        - unset resolves to `"production"`;
        - `""` and `"  "` resolve to `""` **without raising**.
      - `tests/test_inventory_*.py` *(guard, behavioural)*: with `SLEAP_ROOTS_MODEL_ALIAS=""`, the
        labels-registry check still resolves the entity and proceeds to its (faked) read.
      - `tests/test_registry_cli.py` (`isolate_wandb_env`):
        - `SLEAP_ROOTS_MODEL_ALIAS=""` → non-zero exit, `Error:` naming the variable, no wandb spy
          called. Check this in a dry run, under `--verify` and under `--execute`.
        - A dry run under `candidate` prints
          `alias 'candidate' (from SLEAP_ROOTS_MODEL_ALIAS)` and `seed project`.
        - Unset prints `alias 'production' (default)`.
        - `--verify` prints the target line.
        - `--execute --yes --only <tiny id>` (faked, with the unit-9 stub not yet needed) prints it
          before anything else.
- [x] 7.2 Implement (design D6) in `registry/config.py` and `cli.py`. Fix the docstrings that say "the
      production alias" when they mean the configured alias:
      - `registry/config.py`, module docstring;
      - `registry/publish.py`, module docstring, plus `publish_card`, `_existing_collections` and
        `seed_registry`;
      - `registry/__init__.py`;
      - the `--force` help in `cli.py`;
      - `seed_registry_command`'s first docstring line;
      - the orphan message in `cli.py`, which should use `cfg.alias`.

## 8. Commit `feat(cli): refuse --execute under a non-default alias without --only`

- [x] 8.1 Tests (`tests/test_registry_cli.py`, `isolate_wandb_env`). Use recording spies on
      `sleap_roots_training.registry.config.require_api_key`, `click.confirm` and `wandb.init`, plus
      the autouse `wandb.Api` spy, and assert `calls == []`. Never raise inside the spies: CliRunner
      swallows the exception (see the note in `test_execute_declined_publishes_nothing`).
      - (a) `candidate`, `--execute --yes`, no `--only` → `exit_code == 2`, with `candidate` and
        `--only` in the output. *Red.*
      - (a′) The same without `--yes`, with `input="y\n"` → exit 2, and the confirm spy is never
        called. *Red.*
      - (b) (a) plus `--force` → exit 2. *Red.*
      - (d) *(guard)* A `candidate` dry run without `--only` → exit 0.
      - (e) *(guard)* `candidate` `--verify` without `--only` → the faked `verify_registry` receives
        `cfg.alias == "candidate"` and the full expected set.
- [x] 8.2 Test (`tests/test_registry_publish.py`). Call `seed_registry` with
      `RegistryConfig("ent", "reg", "candidate")` against a `_FakeApi` collection carrying
      `production` but not `candidate` → it is re-published and linked `["candidate"]`. With
      `candidate` already present → skipped. *(guard)* This pins the per-alias behaviour that both
      guards exist for.
- [x] 8.3 Implement (design D4): the guard goes after the dry-run return and before
      `_require_api_key()`.

## 9. Commit `feat(cli): require --promote to link production to a collection for the first time`

- [x] 9.1 Unit tests for `publish.unpromoted_collections(cfg, cards, api)`, against `_FakeApi`.
      *Red: the function doesn't exist.*
      - An absent collection is listed. This **fails without the existence check**, because the fake
        raises for absent names.
      - A collection carrying only `candidate` is listed.
      - A collection carrying `production` is not listed.
      - The result is sorted.
      - A listing error propagates.
      - With `api=None`, it builds `wandb.Api()` lazily (spy).
- [x] 9.2 Add a `test_registry_cli.py` fixture, autouse for the module, that stubs
      `publish.unpromoted_collections` to return `[]`. Guard-2 tests opt out. This covers every
      default-alias `--execute` test, including:
      - `test_execute_yes_seeds_and_reports`;
      - the seed-failure and stale-skip tests;
      - the collection-id-scheme test;
      - `_execute_with_fake_run` and its callers;
      - the 7.1 echo test.

      In `test_execute_declined_publishes_nothing`, also assert that the prompt was reached
      (`"Publish"` or `"Aborted"` in the output). Otherwise it could pass on any early refusal.
- [x] 9.3 Guard-2 CLI tests (default alias, `isolate_wandb_env`, spies as in 8.1,
      `unpromoted_collections` faked per case). *Red: there is no check and no flag.*
      - (a) One unpromoted id with `--execute --yes --only <id>` and no `--promote` → `exit_code == 1`,
        with the id and `--promote` in the output. The confirm, `resolve_all` and `wandb.init` spies
        are not called.
      - (a′) The same without `--yes`, with `input="y\n"` → exit 1, and the confirm spy is never
        called.
      - (b) (a) plus `--force` → refused the same way, and the check still ran.
      - (c) (a) plus `--promote` → proceeds to (faked) publishing.
      - (d) Everything already promoted → proceeds both without and with `--promote`.
      - (e) `--promote` without `--only` → exit 2, before the credential spy.
      - (f) `--promote` under `candidate` → exit 2.
      - (f2) `--promote` in a dry run, and `--promote` with `--verify` → exit 2.
      - (g) The check raises `RuntimeError("boom")` → non-zero, `Error:` in the output,
        `result.exception is None or isinstance(result.exception, SystemExit)`, and `wandb.init` not
        called.
      - (h) `SLEAP_ROOTS_MODEL_ALIAS=" production "`, `--execute --yes`, no `--only`, one unpromoted id
        → not refused by guard 1 (no exit 2); refused by guard 2 (exit 1).
- [x] 9.4 Implement (design D5):
      - `publish.unpromoted_collections`, with a lazy `api`, existence checked first, then
        `_aliased_artifact`;
      - the `--promote` flag. Its usage checks go with guard 1, before the dry-run return;
      - the pre-pass, under the default alias only. It runs after `_require_api_key()` and before the
        confirm prompt, also under `--force`, and errors are wrapped as `ClickException`.

## 10. Commit `feat(registry): add the wheat crown and sorghum primary/lateral selection rows`

- [x] 10.1 Tests. *Red: the rows don't exist.*
      - `tests/test_registry_chooser.py`:
        - 9 rows and 11 checksums. Rename the `..._seven_rows` test and fix its stale "13 cards"
          comment;
        - the three exact checksums;
        - wheat `snapshot is None`; sorghum `"20250204"`.
      - `tests/test_registry_cards.py`:
        - the committed-matrix counts go to 11, with the message updated;
        - `EXPECTED_SELECTORS_BY_MODEL` gains `(wheat, cylinder, 5, 14)` crown and
          `(sorghum, cylinder, 3, 14)` primary and lateral. This drives the selector-equality tests;
        - `EXPECTED_COLLECTION_BY_MODEL` gains the three literal ids.
      - `tests/test_registry_publish.py`: the committed-model counts go to 11, and the
        `test_the_eight_committed_model_ids_…` test is renamed.
      - `tests/test_scripts.py`: `len(missing) == 11`.
      - `tests/test_registry_lineage.py`: for the 3 new cards, exactly 3 `model_origins` (wheat
        `snapshot: None`) and exactly the 2 new rows.
      - `tests/test_registry_cli.py`, the candidate publish. Use `candidate`, `--only <3 new ids>` and
        `--execute --yes`, with these fakes:
        - `wandb.init` returns the extended `_FakeRun`, with `project` and `entity` equal to `cfg`;
        - `wandb.Api` returns `_FakeApi(collections=[])`;
        - `wandb.Artifact` is patched with `_FakeArtifact`;
        - `publish.resolve_all` returns stub dirs (no zips).

        Assert:
        - exactly 3 published;
        - every recorded link has `aliases == ["candidate"]`;
        - the run config's `model_origins` covers exactly the 3, and `row_sources` is exactly the 2 new
          rows;
        - none of the three old lineage keys.
      - `tests/test_registry_cli.py`, the guard-2 variant (opts out of the 9.2 stub). Run the same
        command **without** the alias variable, against the real `unpromoted_collections` over
        `_FakeApi(collections=[])` → exit 1, naming all 3. `wandb.init` and `link_artifact` are never
        called.
- [x] 10.2 Implement: the two rows verbatim from training#72, 3 checksums, 2 `source` strings and 3
      origins (design D1). The header says 11 models.

## 11. Commit `docs: candidate publishing, the alias guards, and --promote`

- [x] 11.1 README section "Seeding the production model registry". It is the canonical, generic
      runbook.
      - **Cross-repo invariant paragraph.** Rewrite it: predict reads `SRP_WANDB_MODEL_ALIAS`
        (default `production`), and no deployment sets it.
      - **Intro and env-table alias row.** Say "the configured alias (default `production`)". The row
        adds that a blank value is an error for `seed-registry`, not the default. This differs from the
        seed-project row below it.
      - **Usage.** Rename `<snapshot-dir>` to `<models-root>`, a directory of `<source_model_id>.zip`.
        The `--execute` comment says the target line prints first, and that first-time `production`
        links need `--only … --promote`.
      - **Rerun contract.** The skip is per configured alias. Until every matrix card is promoted, a
        full default-alias `--execute` is refused; re-seed the promoted ones with `--only <ids>`. A
        re-run after a partial promote repeats `--only … --promote`.
      - **Rollout.** Count-free. First-time production seeding uses `--only … --promote`.
      - **New subsection, "Publishing under a non-default alias":**
        - `--only` is required;
        - verify under that alias;
        - a default `--verify` reports those cards missing and exits 1 until they are promoted;
        - roll back by unlink, never `save()`.
      - **"Do not delete these wandb projects".** Add `sleap-roots-training`, which holds the candidate
        sources.
- [x] 11.2 Other stale prose:
      - `registry/models.py`: in the module docstring and the rejection message, "snapshot-pinned"
        becomes "checksum-pinned". The models test matches `(?i)pin`, so it is unaffected.
      - `scripts/regen_model_checksums.py` docstring:
        - it needs all 11 zips under one root, and a partial root prints MISSING;
        - "holds the snapshot as `<species>/<root>/<id>.zip`" becomes "`<model_id>.zip` under any
          root".
      - `docs/roadmap.md` registry section: add a one-line pointer to #72/#118.
- [x] 11.3 `docs/CHANGELOG.md` `[Unreleased]`. Use the **first** `### Added` and the first
      `### Changed`, and add `### Removed` after Changed. Describe the guards by behaviour, not as
      "guard 1/2".
      - **Added:**
        - the wheat and sorghum rows, committed to be published under `candidate` (not `production`);
        - refusing `--execute` under a non-default alias without `--only`;
        - `--promote`, now required for a first-time `production` link;
        - the target line;
        - `row_sources` / `model_origins`.
      - **Changed:**
        - `SPECIES_VOCAB` is widened, which also widens training `validate` and labeling metadata;
        - the alias is stripped.
        - **Breaking:**
          - the matrix requires `source` and `origins`;
          - `build_lineage`'s signature changed;
          - a first-time default-alias seed needs `--only … --promote`;
          - a blank alias is an error for `seed-registry`;
          - the run-config keys are replaced.
      - **Removed:** `lineage.SELECTION_MATRIX_SOURCE`, `SELECTION_MATRIX_DATE` and `MODELS_SNAPSHOT`.

## 12. Verification and reconciliation (before `/pre-merge-check`)

- [x] 12.1 The CI-equivalent checks (top of this file) and
      `openspec validate add-wheat-sorghum-production-cards --strict` all pass. Lint any touched file
      under `scripts/` separately. *Done 2026-10-03:* 992 passed, 3 skipped; coverage 97.84%
      (gate 95%); black, ruff (`src/` and `scripts/regen_model_checksums.py`) and the strict
      validate are clean. Every commit is green on its own:
      `git rebase --keep-base --exec "…pytest…"` ran each of the 11 commits through the suite.
- [x] 12.2 Re-read proposal, design, spec and these tasks against the diff. Record any deviation here
      as a `### Why N instead of M?` note, and file an issue for any bug found. Commit as
      `docs(openspec): reconcile add-wheat-sorghum-production-cards with the implementation`.
      *Done 2026-10-03.* No bug was found that needed a workaround, so no issue was filed. The
      deviations are below.

### Why the wheat labeling test was corrected after group 3

Task 3.3 says `build --species wheat --root-type crown`. As first committed, the test inherited
`build_args`' `--root-type primary --root-type lateral`. Both fail at the same skeleton lookup, so
the test passed either way, but it did not test what the task names. Reconciliation found the gap,
and a follow-up commit makes the test pass `crown` and assert that the error names it.

### Why `_FakeApi.artifacts` raises only for an unknown, unlisted name

Task 4.1 says the fake raises "for a name with no collection". It raises when the name is neither
an injected artifact (`arts_by_name`) nor a listed collection. Existing publish tests inject an
artifact for a name without listing its collection, and wandb would answer those reads. Raising
there would have broken tests whose subject is not existence. The case the change cares about, an
absent and unlisted collection, raises as wandb 0.28 does.

### Why four `--promote` usage tests were green before group 9's implementation

Task 9.3(e), (f) and (f2) are labelled red. Before the flag existed, click rejected `--promote` as
an unknown option, which is also a usage error (exit 2) whose message names `--promote`. So those
four cases passed vacuously in the red run. After implementation they pass for the right reason.
The assertions are unchanged, and they check exit 2, the flag name, and that nothing was called.

## 13. Operator, before merge (on the branch; no writes, no lineage)

Results are recorded in the PR description.

- [x] 13.1 Design D7.1: stage the zips, and record the `sha256sum` of the staged copies.
      *Done 2026-10-03:* staged under the session scratchpad, outside every worktree. The copies
      hash to `650fe30b…a13f` (wheat), `7c2cd05d…7c07` (sorghum primary) and `f694d6da…0028`
      (sorghum lateral), equal to the matrix.
- [x] 13.2 Design D7.2: dry run under `candidate`. The target line shows `alias 'candidate'`, and all
      three entries are `[ok]`. *Done 2026-10-03:* the target line reads `alias 'candidate' (from
      SLEAP_ROOTS_MODEL_ALIAS)`. All three entries are `[ok]`, with selectors (wheat, cylinder, 5,
      14) crown and (sorghum, cylinder, 3, 14) primary and lateral. None is `UNPINNED`.
- [x] 13.3 Design D7.3: the credential-less guard checks, with the exact commands and expected
      messages given there. *Done 2026-10-03:* both checks ran with `env -u WANDB_API_KEY
      NETRC=/nonexistent` and an empty `--models-root`.
      - `candidate --execute --yes` (no `--only`) exited 2 with "alias 'candidate' is not the
        default … requires --only".
      - Default alias `--execute --yes --promote` (no `--only`) exited 2 with "--promote requires
        --only".

      Neither reached the credential check.

## 14. Operator, after the squash-merge (ask the owner before each W&B or GitHub write)

Recorded in a follow-up `docs(registry)` PR that ticks this group with dated notes. The archive PR
follows it.

- [ ] 14.1 Design D7.4: prepare the detached worktree, then the read-only probe and the live,
      non-writing guard-2 check (expect exit 1 with the `--promote` refusal).
- [ ] 14.2 Design D7.5: **ask the owner**, then publish. Expect published (3), skipped (0), no FAILED or
      STALE, and a target line showing `alias 'candidate'`.
- [ ] 14.3 Design D7.6: verify.
      - candidate `--only`: 3 present, 0 legacy;
      - default `--verify`: 8 present, exactly the 3 missing, 0 orphans, 0 legacy, exit 1.
- [ ] 14.4 Design D7.6: read back each artifact (`:vN`, digest, aliases never `production`, metadata
      equal to `card_to_metadata`) and the run config (`git_sha` is the squash SHA, `git_dirty`
      false, 3 `model_origins`, 2 `row_sources`).
- [ ] 14.5 Design D7.7: **show the owner the comment text, then post it** on training#72 and
      pipeline#118. Tick #118 step 1 only after the owner agrees.

## Not in this change

See `proposal.md` "Out of scope". training#72 stays open for #118 step 6.
