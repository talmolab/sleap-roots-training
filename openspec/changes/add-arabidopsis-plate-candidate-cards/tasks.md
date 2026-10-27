# Tasks: add-arabidopsis-plate-candidate-cards

## How this is executed

**TDD.** In every code group:

1. Write the listed tests first.
2. Run them and confirm they fail **for the stated reason**.
3. Implement until they pass.
4. Run the CI-equivalent suite:
   - `uv run --locked pytest -m "not integration" --cov=src/sleap_roots_training --cov-fail-under=95 tests/`
   - `uv run black --check src/sleap_roots_training tests scripts`
   - `uv run ruff check src/sleap_roots_training`

Never run `pytest` without `-m "not integration"`, because the integration tests download from W&B.

**Commits.**

- One commit per group, with the group's boxes ticked in the same commit.
- Group 0 is the proposal commit.
- Before review, prove every commit is green with:
  `git rebase --keep-base --exec "uv run --locked pytest -m 'not integration' -q" origin/main`.

**Ordering rule.** The plate row lands **last** (group 7), after the loader (2), card status (3), the
refusal guard (4) and verify (5). No commit has the row without `status: candidate` and its guard.
Before group 2 the loader silently ignores unknown keys, so a row committed early would load as
production.

**Test spies.** Refusal tests use the recording spies already in `tests/test_registry_cli.py`:

- `_spy_everything`;
- the autouse `API_CALLS` backstop for `wandb.Api`;
- the autouse `PROMOTION_CHECKS` stub for `unpromoted_collections`.

They assert empty call lists. Never raise inside a spy: `CliRunner` turns that into exit 1, which is
indistinguishable from the refusal.

## 0. Proposal

- [x] 0.1 Commit the change directory:
  `docs(openspec): propose add-arabidopsis-plate-candidate-cards`.

## 1. Reproducible archive build (`scripts/build_model_zip.py`)

- [x] 1.1 Tests first (`tests/test_scripts.py`), using a `tmp_path` model directory with
  `best_model.h5`, `training_config.json`, one nested file and one OS-junk file:
  - **Determinism:** two builds, with the source files' mtimes changed between them, give identical
    SHA256s.
  - **Layout:** every entry sits under `<dirname>/`, entries are sorted, `compress_type ==
    ZIP_STORED`, every `date_time == (1980, 1, 1, 0, 0, 0)`, and OS junk is excluded.
  - **Resolution:** the archive resolves with
    `resolve_model_dir(model_id, root, {model_id: sha}, require_pinned=True)`.
  - **No overwrite:** an existing output path makes the script exit non-zero, with the file unchanged.
  - **Missing source:** a source that is not a directory makes the script exit non-zero.
  - **Output:** the script prints the SHA256.
- [x] 1.2 Implement the script: `main(model_dir, out_zip)` with a google-style docstring, matching
  `regen_model_checksums.py`. It reuses the registry's `junk_filter` and `_sha256_of_file`.
- [x] 1.3 Owner step, no code. Build both archives from the curated copy into a scratch `--models-root`.
  - Primary source: `primary_root/labels/models/230804_133809.multi_instance.n=606/`.
  - Lateral source: `lateral_roots/labels/models/231130_135922.multi_instance.n=38/`.
  - Confirm the digests:
    - primary: `ed1a939058e7989f938720b5461b795dc75d1c081b41e1d928284c09ad0ab721`
    - lateral: `f42c4d06fe46c53c07150a95e308fcbfeadbf0771b6657bbe85346604b0ec265`
    - Both were measured 2026-10-26 with the committed script, two builds each, byte-identical.
    - **Why these instead of the proposal's digests?** The proposal recorded digests from a
      scratch prototype that set permission bits `0o644`. The committed script records a
      regular-file mode, `0o100644`, which is what `zipfile` writes for a real file. The archive
      header bytes therefore differ. The file contents are unchanged.
  - Confirm each archive contains:
    - `best_model.h5` and `training_config.json`;
    - `labels_gt.val.slp`, which predict's parity harness needs;
    - `labels_pr.val.slp` and `metrics.val.npz`.
  - Confirm each `best_model.h5` is byte-identical to the original training-run copy.

## 2. Row status in the loader (`registry/chooser.py`)

- [x] 2.1 Tests first (`tests/test_registry_chooser.py`), using `write_matrix`:
  - **Default:** a row without `status` has `status == "production"`.
  - **Explicit values:** `status: production` and `status: candidate` load as written.
  - **Invalid values:** `staging`, `null`, `""`, `1`, `Candidate` and `" candidate "` each raise a
    ValueError naming the row index, `production` and `candidate`.
  - **Order:** a row with both a bad `status` and a missing `source` reports the `source` error.
  - **CLI:** `seed-registry` over a matrix with `status: staging` exits non-zero with that message,
    and no traceback.
- [x] 2.2 Implement:
  - Add `ROW_STATUSES = (config.DEFAULT_ALIAS, "candidate")`.
  - Add `SelectionRow.status: str = "production"` as a trailing field.
  - Check status after `source` and before `origins`.

## 3. Card status and mixed status (`registry/cards.py`)

- [x] 3.1 Tests first (`tests/test_registry_cards.py`). Extend the `_row` helper with
  `status="production"`.
  - **Inherited status:** cards from a candidate row are `candidate`; all others are `production`.
  - **Mixed status:** one model under a production row and a candidate row raises a ValueError naming
    the model.
  - **Same status:** two candidate rows sharing a model give one candidate card.
  - **Not published:** for a candidate card, `card_to_metadata` has no `status` key and equals the same
    card's metadata with status `production`.
- [x] 3.2 Implement:
  - Add `Card.status: str = "production"` as a trailing field.
  - Collect each model's row statuses in `expand_rows_to_cards`, and reject mixed status there.
  - Leave `card_to_metadata` unchanged.

## 4. Candidate scoping and refusal under production (`cli.py`)

- [x] 4.1 Tests first (`tests/test_registry_cli.py`), over an inline matrix with one production row and
  one candidate row.
  - **Refusal:** under the default alias, `--execute --yes --only <cand> --promote` exits 1.
    - The output names `<cand>`, `status`, and the production-ids remedy.
    - `calls == []`, `API_CALLS == []` and `PROMOTION_CHECKS == []`.
    - `result.exception` is `None` or a `SystemExit`.
  - **The refusal comes from this check:** the same invocation with `--force`, and again without
    `--promote`, is refused the same way. Its output names `status` and does not contain
    `Pass --promote`, and `PROMOTION_CHECKS == []`.
  - **Lost alias variable:** the candidate command without `SLEAP_ROOTS_MODEL_ALIAS`
    (`--only <cand> --execute --yes`) is refused the same way.
  - **Unscoped re-seed:** `--execute --yes` with no `--only` under the default alias prints
    `skipped (status: candidate)` for `<cand>`.
    - `unpromoted_collections` receives only the production cards.
    - `resolve_all` and the publish receive only the production cards.
  - **Candidate alias:** under `SLEAP_ROOTS_MODEL_ALIAS=candidate`, `--execute --yes --only <cand>`
    (no `--promote`) links exactly `[(f"{project}/{cand}", ["candidate"])]`. Model this test on
    `test_the_candidate_publish_links_exactly_the_three_new_cards_as_candidate`.
  - **Dry run:** a dry run under the default alias is not refused, and lists `<cand>` marked
    `status: candidate`.
  - **Verify:** `--verify --execute` under the default alias reaches `verify_registry` and is not
    refused.
- [x] 4.2 Implement:
  - Place the guard after the `--promote` usage validation, conditioned on `execute and not verify`,
    under the default alias, and before `_require_api_key`.
  - It refuses when `--only` names a candidate card. Otherwise it drops candidate cards from
    `all_cards` and prints each skip.

## 5. Status-aware verify (`registry/publish.py`, `cli.py`)

- [x] 5.1 Make the existing tests that must change first. They are part of this group's commit.
  - Add `unexpected_production=()` and `barred_unreadable=()` to `_verify_report`.
  - Change the 7 fake `verify_registry` signatures in `test_registry_cli.py` (lines ~277, 565, 585,
    932, 1055, 1349, 1533) to accept `**kw`.
  - Rewrite `test_a_non_default_alias_verify_without_only_is_allowed`. Its matrix gets one
    `status: candidate` row, and the test asserts `expected` is exactly that row's collections.
  - **Also changed, which the review did not list.** Two more existing tests ran an unscoped
    `--verify` under an alias that no row carries. The new empty-expected refusal (spec: *An alias
    no row carries fails verification*) reverses what they assumed:
    - `test_verify_prints_the_target_line` now scopes with `--only soy-p`, so it still tests the
      target line.
    - `test_the_verify_orphan_line_is_ascii_escaped` became
      `test_an_unscoped_verify_under_an_alias_no_row_carries_is_refused_in_ascii`.
      - **Why replace it instead of keeping it?** An orphan line can now print only under
        `production` or `candidate`, the only statuses, and both are ASCII. The non-ASCII alias
        that test used now reaches the refusal instead, so the ASCII guarantee is asserted there.
- [x] 5.2 New tests first.
  - **Publish level** (`tests/test_registry_publish.py`, using `_FakeApi`/`_FakeArt`):
    - **Candidate absent from the registry** (the real pre-publish state): `verify_registry(CFG,
      [prod], matrix_collections=[prod, cand], barred_collections=[cand], api=_FakeApi(collections=[prod],
      arts_by_name={prod: [_FakeArt(["production"])]}))` does not raise.
      - `unexpected_production == []`.
      - `cand` is in no other bucket.
      - `verify_failed` is False.
      - `cand`'s versions are never read.
    - **Candidate linked to production:** `cand` carries `["production", "candidate"]`. It is in
      `unexpected_production` and not in `present` or `orphans`, and `verify_failed` is True.
    - **Read error:** reading `cand`'s versions raises. It lands in `barred_unreadable` and
      `verify_failed` is True.
      - Add a per-name failure knob (`fail_names`) to `tests/registry_fakes.py` to drive this.
    - **Orphans under `candidate`:** a production-status collection that carries `candidate` and is in
      `matrix_collections` is not an orphan. A `candidate`-carrying collection outside
      `matrix_collections` is still an orphan.
    - **Not-yet-linked production rows:** the existing test that production-status cards still
      unlinked are reported missing keeps passing.
  - **CLI**, with a capturing fake `verify_registry(cfg, expected, api=None, **kw)`:
    - **Default alias:** `expected` equals the production ids, `kw["matrix_collections"]` equals all
      ids, and `kw["barred_collections"]` equals the candidate ids.
    - **Under `candidate`:** `expected` equals the candidate ids and `barred_collections == []`.
    - **`--only <cand>` under the default alias:** `expected == []` and `barred_collections == [cand]`.
    - **An alias no row carries:** `SLEAP_ROOTS_MODEL_ALIAS=candidtae --verify` exits 1, names the
      alias, and `API_CALLS == []`.
    - **Report output:** a report with `unexpected_production=["x"]` prints
      `UNEXPECTED PRODUCTION LINK: x (row status is candidate)` and exits 1.
      `barred_unreadable=["y"]` prints `unreadable: y …` and exits 1.
- [x] 5.3 Implement:
  - **`verify_registry`:** add the keyword-only `matrix_collections` and `barred_collections`, both
    defaulting to empty.
    - A barred collection is read only if it is in `existing`.
    - Add the two new buckets, and include both in `verify_failed`.
  - **CLI:**
    - Capture all collection ids before the `--only` filter.
    - Build `expected` and `barred` by status per design D2, and refuse an empty unscoped expected
      set.
    - Print the new buckets.

## 6. Promotion safety pinned at the library boundary

- [x] 6.1 Add a test documenting the residual risk: `publish.seed_registry` itself does not filter by
  status (design D3). The test asserts the CLI never passes it a candidate card under the default alias
  in the scoped, unscoped and `--force` paths, by spying on `seed_registry`'s `resolved` argument.

## 7. Add the plate row (`registry/data/model_selection.yaml`)

- [x] 7.1 Tests first. They fail until the row lands.
  - **`test_registry_chooser.py`:**
    - `test_load_selection_matrix_has_nine_rows` becomes `…_has_ten_rows`; its counts become 10 rows
      and 13 checksums; its "plate row omitted" comment goes.
    - New test: `test_the_arabidopsis_plate_source_zips_are_pinned_to_their_measured_digests`, pinning
      both SHA256s. Model it on the wheat/sorghum digest test.
    - New test: both plate origins have `snapshot is None` and a non-empty `pinned_by`, and the
      no-share-path test covers their `location`.
  - **`test_registry_cards.py`:**
    - Every 11 becomes 13, comments included (lines ~67, 70, 72, 74, 472, 580, 581).
    - Add the plate entries to `EXPECTED_SELECTORS_BY_MODEL`, each `(arabidopsis, plate, 2, 7)`.
    - Add the plate entries to `EXPECTED_COLLECTION_BY_MODEL`.
    - New test, *Committed Matrix Totals*: exactly the two plate cards are `candidate` and the other
      11 are `production`.
  - **`test_registry_publish.py`:** lines ~123, 157 and 158 change from 11 to 13.
  - **`test_scripts.py`:** line ~403 changes from 11 to 13.
  - **`test_labeling_skeletons.py`:** the plate primary skeleton row's window equals the matrix plate
    row's `parse_age_window` (2, 7). The test documents that no plate lateral skeleton row exists.
  - **CLI against the committed matrix** (`test_registry_cli.py`):
    - **Refusal:** under the default alias, `--execute --yes --only <2 plate ids> --promote` is refused
      naming both, with no wandb calls. This is the offline version of the live check in 10.3.
    - **Candidate publish:** under `candidate`, `--only <2 plate ids> --execute --yes` links exactly
      those two under `["candidate"]`.
      - `lineage_config["row_sources"]` has the single row `(arabidopsis, plate)`.
      - Both `model_origins` have `snapshot is None`.
    - **Dry run:** a dry run with `--only <2 plate ids>` prints metadata with the selector
      `(arabidopsis, plate, 2, 7)` and no `status` key.
- [x] 7.2 Add the row, with these fields:
  - `arabidopsis`, `plate`, `"2, 3, 4, 5, 6, 7"`;
  - the two model ids, and `crown_model_id: null`;
  - `status: candidate`;
  - `source: "owner decision 2026-10-22 (talmolab/sleap-roots-training#3): …"`.

  Also:
  - Add both `checksums` and both `origins`. Each `location` names the curated copy's model directory
    in relative prose with no share path. Each `pinned_by` names the owner's curated selection and the
    reproducible build script.
  - Rewrite the header: "Model selection matrix: 10 rows over 13 physical models; rows with
    `status: candidate` are published under `candidate` and never linked to `production`."
  - Replace the "plate row is OMITTED" note.
- [x] 7.3 Run the dry run against the scratch models-root from 1.3:
  `SLEAP_ROOTS_MODEL_ALIAS=candidate uv run sleap-roots-training seed-registry --models-root <scratch>
  --only <2 ids>`. Both cards must show `[ok]`.

## 8. Docs

- [x] 8.1 Write `docs/arabidopsis-plate-models.md`, a consumer page of about one screen. It has these
  parts:
  - **Models table:** collection id, root type, nodes, training ages, frame counts and validation
    metrics. State that `.n=606` becomes `.n-606` in ids, and that `arabidopsis_plates/primary/…` is a
    registry namespace, not an on-disk path.
  - **Caveats:**
    - the models were trained on full plates, not sections;
    - sleap-nn resizes each frame to fit 1500×1616 and then pads it, so sections are upscaled;
    - the lateral model rests on one imaging session of unconfirmed age, with 4 validation frames;
    - each model's metrics come from its own validation set;
    - ages older than 7 are clamped to 7 with only a warning, and ages younger than 2 get no model.
  - **Fetch:** the literal
    `wandb.Api().artifact("eberrigan-salk-institute-for-biological-studies-org/wandb-registry-sleap-roots-models/<collection>:candidate").download()`.
    The reader needs registry access.
  - **Predict:**
    - `SRP_WANDB_MODEL_ALIAS=candidate`, with `SRP_WANDB_ENTITY` and `SRP_WANDB_MODEL_REGISTRY` at
      their defaults;
    - a scan sidecar with `species: arabidopsis`, `mode: plate` and an `age`;
    - note that Bloom has no plate dispatch, and that the candidate listing also includes wheat and
      sorghum.
  - **Promotion:** "gates: #NEW; mechanics: README". Do not restate them.
  - No share paths. The curated copy's location goes to Benfica in Slack.
- [x] 8.2 README updates:
  - Status, the candidate scoping and refusal, and the status-aware `--verify` with its failure lines.
  - Promotion now starts with "a reviewed PR drops `status: candidate`".
  - Fix lines that are already stale:
    - line ~57: `SRP_WANDB_REGISTRY` becomes `SRP_WANDB_MODEL_REGISTRY`, with default
      `sleap-roots-models`;
    - lines ~72–74: the "8 `production` links" count becomes 11, and wheat/sorghum are promoted;
    - line ~126: the rerun contract;
    - line ~151: the candidate example;
    - lines ~165–169: the alias-lost and promote text.
  - Link the plate doc.
- [x] 8.3 CHANGELOG `[Unreleased]`:
  - Merge the duplicate `### Added` headers.
  - **Added:** per-row status, the plate candidate row, and `build_model_zip.py`.
  - **Changed:** status-aware `--verify`, plus the candidate scoping and refusal.
  - Record the 2026-10-05 wheat/sorghum promotion.
- [x] 8.4 Rewrite the roadmap's registry adjacent-work list (lines ~89–110):
  - the re-seed is done;
  - wheat/sorghum are in production;
  - #7 is closed;
  - #3 is done as candidate, with promotion in #NEW.
- [x] 8.5 Update the `labeling/data/skeletons.yaml` header and the `tests/test_labeling_skeletons.py`
  docstring: the rice and plate windows are cross-checked against the matrix.

## 9. Validate and hand off for review

- [x] 9.1 Run the CI-equivalent suite from the top of this file, all green.
- [x] 9.2 `openspec validate add-arabidopsis-plate-candidate-cards --strict`.
- [x] 9.3 Reconcile the implementation against the proposal, design and spec (new-feature step 9).
  Update the docs for any deviation, with a `### Why N instead of M?` section.
- [x] 9.4 Run `/pre-merge-check` and `/review-pr`. The PR body says `Refs #3`.
- [x] 9.5 Pre-PR `/review-pr` (report only; 5 reviewers, no blockers, mutation-tested) fixes, each
  test-first:
  - `build_model_zip`:
    - resolve the source (a `.` source wrote rooted entries) and require a model directory;
    - refuse an output inside the source;
    - stream files instead of reading them whole;
    - write through a temporary file, so a failed build leaves nothing;
    - pin a golden digest plus the header fields, so CI proves host and version independence.

    The committed plate digests were rebuilt and are unchanged.
  - CLI and verify:
    - refuse an alias that differs from `production` only in case or invisible characters
      (`Production` passed every guard with `--only`);
    - stop an unscoped run whose whole scope is candidates before the credential check;
    - record `invocation.skipped_by_status`;
    - name each candidate verify found not linked, and keep an unreadable one's cause.
  - Code:
    - `Card.status` is required (no fail-open default);
    - one `CANDIDATE_STATUS` constant;
    - the verify branch moves into `_run_verify`.
  - Docs:
    - the lateral's age is unconfirmed (its frame names say `day1`), and both ages are marked as
      inferred;
    - the metrics are SLEAP 1.3 TensorFlow values, not reproduced under sleap-nn;
    - the primary emits `R1`–`R8`, unlike the `r1`–`r8` label corpus;
    - the window's history is stated.
  - Recorded: the publish record (10.6) gains per-file archive digests.
  - Deferred, with reasons:
    - Unicode-normalising archive names: today's model names are ASCII.
    - Adding `desktop.ini` to the shared junk set: it would change extraction too, and needs its own
      change.
    - Rejecting unknown matrix keys: a broader loader change. (Reversed for row keys in 9.6.)
- [x] 9.6 Post-PR `/review-pr 82` fixes (5 reviewers, no blockers), each test-first, RED then GREEN:
  - Loader: reject unknown **row** keys. A misspelled `status` (`stauts`, `Status`) loaded the plate
    row as production, and the first-link refusal then pointed the operator at `--promote`.
    Top-level matrix keys are unchanged.
  - CLI: under the default alias, a collection that is `candidate` in the **packaged** matrix is
    candidate whatever `--selection-matrix` says. An edited copy plus `--promote` linked it.
  - Verify: `verify_failed` and `_run_verify` index the report keys, so a missing failure key raises
    instead of passing; the test fakes return full reports.
  - `build_model_zip`: refuse an existing `<out>.partial` without deleting it (it deleted another
    build's file); pin the `file_size`-before-stream line against `writestr` under a lowered ZIP64
    threshold.
  - Docs (`docs/arabidopsis-plate-models.md`), from the archives' own files:
    - the metrics are over paired instances ("paired" is not "found"); state labelled, paired and
      predicted counts and OKS mAP/mAR;
    - the split is a random 10% of frames, and some validation images are training images labelled
      again in a second copy (3 of 61 primary, 2 of 4 lateral), so the numbers are not held out;
    - the primary's labels include an IAA-treated set (166 of 545 train, 23 of 61 val frames);
    - the primary's `R1` is the base and `R8` the tip (owner; all 304 validation roots with both ends
      labelled have `R1` above `R8`); the lateral's `r1` is the base (owner, 2026-10-27); both skeletons are
      linear chains;
    - both models resize to 1500 × 1616 (height × width); the lateral runs at scale 1.0;
    - the page says "to be published" until 10.9 records the published versions.
  - Focused review of these fixes (2 reviewers, no blockers), test-first:
    - the packaged statuses apply to `--verify` (barred, not expected) and the dry-run marker too,
      and a packaged matrix that fails to load is a CLI error;
    - tests now prove an edited copy's unscoped run never publishes the packaged candidate, and that
      the verify echo, not only `verify_failed`, requires its report keys (both killed by reverting
      the line they pin);
    - the page: some validation images are training images (3 of 61 primary, 2 of 4 lateral), so the
      numbers are not held out; "paired" is not "found"; the IAA-treated share; the lateral's base
      (then inferred, since confirmed by the owner); one dimension order.
    - Accepted: an edited copy that re-lists the same weights under a new model id gets past the
      collection-keyed bar; the bar guards against slips, not a determined operator.
  - Declined, with reasons: the remaining suggestions (alias NFKC folding, a library-level guard in
    `publish_card`, lazy-pagination fakes, symlink refusal, type and naming clean-ups) do not change
    what this PR publishes; they are noted on the PR.

## 10. After merge: smoke test and publish under `candidate` (owner approves each write)

- [ ] 10.1 Load smoke test, local and with no wandb. Extract both archives with `resolve_model_dir`.
  Then, in a `sleap-roots-predict` checkout environment, call `make_predictor([<extracted dir>])` for
  each model, and run one prediction on one plate image from its `labels_gt.val.slp`. Record the
  output instance counts.
- [ ] 10.2 Set up a detached worktree at the squash SHA.
  - Run `uv sync --locked`, and confirm a clean status.
  - Confirm `SLEAP_ROOTS_MODEL_ALIAS` is unset.
- [ ] 10.3 Read-only pre-publish checks:
  - A default `--verify` shows 11 present, nothing unexpected, and exit 0. The plate collections do not
    exist yet, so this exercises the absent-collection path.
  - Refusal check, with **no `--models-root` and no `--yes`**: `seed-registry --only <2 ids> --promote
    --execute` under the default alias. It must exit 1 naming `status`. An exit 2 for a missing
    `--models-root` would mean the guard is absent; nothing is at risk either way.
- [ ] 10.4 Publish:
  `SLEAP_ROOTS_MODEL_ALIAS=candidate seed-registry --models-root <scratch> --only <2 ids> --execute --yes`.
- [ ] 10.5 Verify:
  - `SLEAP_ROOTS_MODEL_ALIAS=candidate seed-registry --verify` shows 2 present and exits 0.
  - A default `--verify` still shows 11 present, nothing unexpected, and exit 0.
- [ ] 10.6 Read both artifacts back. Write
  `docs/migration/<publish date>-arabidopsis-plate-candidate-publish-record.json`, using the same
  schema as `2026-10-04-wheat-sorghum-candidate-publish-record.json`. Also record:
  - the smoke-test result and the rollback (`unlink()` the `candidate` alias);
  - each archive's member list with per-file SHA256, so what was published is reconstructable even if
    the curated copy later changes;
  - the SHA256 of each original training-run `best_model.h5` it was compared against (task 1.3).
  - Before committing, grep the record for `:\`, `\\`, `hpi`, `users/` and a leading `/`.
- [ ] 10.7 Open "Promote arabidopsis plate cards to production (gated)" (#NEW) with these gates:
  - parity on the candidate alias, with a plate prefix mapping in predict's `run_parity_harness.py`;
  - sleap-roots#252;
  - plate dispatch in bloomctl and contracts;
  - the 2–7 window vs traits' 7–14 (sleap-roots#274);
  - a PR that drops `status: candidate` and MODIFIES *Committed Arabidopsis Plate Row*;
  - `--only … --promote --execute`.

  Then close #3 with a comment linking the record and #NEW.
- [ ] 10.8 Send Benfica the doc link and the two collection ids, and confirm her registry access.
- [ ] 10.9 Follow-up PR, after its own `/review-pr`, with two commits:
  - the record plus the ticks for 10.x, and `docs/arabidopsis-plate-models.md` updated to say the
    cards are published, with each artifact's version, digest and the smoke-test result;
  - `chore(openspec): archive add-arabidopsis-plate-candidate-cards`. At archive time, amend the spec
    Purpose line to "…linked under each row's status".
- [ ] 10.10 Cross-repo, owner: a PR to the sleap-roots-pipeline `docs/bloom-integration/roadmap.md`
  changing "plate models deferred (training #3)" to point at the candidate cards and #NEW.
