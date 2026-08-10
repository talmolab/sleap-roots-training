# Tasks

Groups **1** and **2** are work in *other* repos. They are recorded as acceptance conditions with
**unchecked prose, not checkboxes**, because `openspec archive` expects a change's tasks to be
completable here and nothing in this repo can tick a `sleap-roots-contracts` box. The few items in
those groups that genuinely are ours (filing the tracking issues, verifying a consumer behavior we
depend on) stay checkboxes. See `proposal.md` "Blocked on".

## 0. Decisions required before implementation (blocking)

- [ ] 0.1 Approve the bundled-selector shape (`Selector`, `ModelCard.selectors`, scalar `root_type`).
- [ ] 0.2 Decide the **collection-id scheme** (`design.md` "Open question"). Recommendation: derive
      from `source_model_id`. This renames all 13 live production collections. **This decision is a
      hard input to everything below** — it sets the orphan count (0.4, §6.2), whether the re-seed is
      additive or in-place (§6.1), whether old-pinned consumers keep a working fallback
      (`design.md` "Reverse compatibility"), and the ordering inside §3. Whatever is chosen, the id
      must be a legal wandb artifact name: every `source_model_id` contains `/`, which wandb rejects.
- [ ] 0.3 Decide the **migration strategy**: flag day vs tolerant read. Recommendation: tolerant
      read, so the production registry is never unreadable by an upgraded consumer. Note this covers
      only new-code-reads-old-data; the reverse direction is handled operationally (0.4).
- [ ] 0.4 Decide the disposition of the collections **orphaned** by the collapse. The count follows
      from 0.2: **all 13 under option 1** (every id changes, so the re-seed is purely additive and
      nothing is overwritten), 5 only under option 3, which `design.md` rejects.
      Recommendation: **explicitly retire them** (drop the `production` alias) as the final step,
      *after* the 8 new collections verify **and** the upgraded `sleap-roots-predict` is confirmed
      deployed. Leaving them forever is not neutral — once the schema tightens, predict's registry
      lister is believed to skip old-shape collections with only a logged warning, so those models
      stop being selectable **silently**. But retiring them *early* is worse: under option 1 those 13
      collections are the only thing an un-upgraded consumer can still read, so the alias drop, not
      the re-seed, is the compatibility cliff.
- [ ] 0.5 Confirm cross-repo ownership and sequencing with the `sleap-roots-contracts` owner
      (unassigned as of this proposal — group 1 blocks everything else).
- [ ] 0.6 Once 0.2/0.3/0.4 are agreed, **fold the decisions back into `design.md`** and update this
      file — including writing the literal id formula into the Collection Identifier Scheme
      requirement in the delta spec, which currently states only the properties any formula must
      satisfy.

## 1. Contracts (`sleap-roots-contracts`, separate repo — must land first)

Acceptance conditions this repo waits on; the work and its checkboxes live in that repo's own
OpenSpec change.

- Add `Selector` (`species`, `mode: Mode`, `age_min`, `age_max`) with the existing `age_min`/`age_max`
  validation (reject `bool`/`numpy.bool_`, enforce ordering).
- Change `ModelCard` to `root_type` + `selectors: tuple[Selector, ...]`; reject an empty `selectors`.
  Keep `sleap_nn_version` a scalar card-level field — it describes the weights, not a selection
  context.
- If tolerant read (0.3) is chosen, accept a legacy flat card and lift it to a single selector.
- Release a new pre-release version.

- [ ] 1.0 File the tracking issue/proposal in that repo and link it here (none exists yet). **Ours.**

## 2. Consumer (`sleap-roots-predict`, separate repo)

Acceptance conditions, as above.

- Generalize `choose_models` to "any selector matches all of species/mode/age".
- Match age against the **matching selector**, never a card-level min/max (see `design.md` risks —
  otherwise canola silently gains a year of coverage).
- Add a regression test that a card serving (canola, cylinder, 2–13) and (arabidopsis, multiplant
  cylinder, 2–14) matches **neither** (canola, multiplant cylinder) nor (canola, age 14).
- Pin the new contracts version.

- [ ] 2.0 File the tracking issue in that repo and link it here (none exists yet); cross-link
      predict#14. **Ours.**
- [ ] 2.5 Confirm what predict's registry lister actually does with a card it cannot parse — skip with
      a warning, or raise. `design.md` leans on "skips with a warning" to argue the additive re-seed is
      safe for un-upgraded consumers; if it **raises**, the canary is itself the outage and §6 must be
      re-planned. Read the code, do not assume. **Ours, and blocking §6.1.**

## 3. This repo — commit 1, atomic: pin + expansion + metadata + collection id + tests

**Must be one commit**, for two verified reasons — *not* the "a separate pin commit would redden
`main`" one an earlier draft gave, which is false: this repo squash-merges and CI runs on PR sync, so
no intermediate commit is ever built on `main`. The real reasons:

- `uv sync --locked` requires `pyproject.toml` and `uv.lock` to move together.
- A pin-only commit is red regardless: `tests/test_registry_chooser.py:180` does
  `ModelCard.model_fields["species"]`, which raises `KeyError` the moment the contract drops
  card-level `species`.

**Ordering inside the commit:** the expansion collapse must land with or before the id change — 13
cards over 8 model ids collide on `publish.py:138`'s duplicate-id guard, so an id-first sequence
cannot even run.

- [ ] 3.1 Bump the `sleap-roots-contracts` pin (`pyproject.toml`, `uv.lock`).
- [ ] 3.2 Rewrite `expand_rows_to_cards` to group by `(source_model_id, root_type)` and attach one
      selector per contributing row, **de-duplicated** and ordered by a sort on the selector values
      (not row order, not `hash()`).
- [ ] 3.3 Update `card_to_metadata` to emit `selectors` + `root_type` + `source_model_id` (+
      `sleap_nn_version` where present), still omitting `registry_id` / `version` /
      `weights_checksum`, and emitting no card-level `species` / `mode` / `age_min` / `age_max`.
- [ ] 3.4 Implement the chosen `collection_id` scheme in the one existing function, so publish,
      `--only`, and `--verify` cannot disagree; keep the duplicate-id fail-fast guard.
- [ ] 3.5 Assert every physical model resolves to exactly one `root_type`, failing the seed loudly if
      a future matrix edit breaks that assumption (the whole design rests on it).
- [ ] 3.6 Rewrite the `cards.py` module/class/function **docstrings**, which currently describe the
      per-row, per-species semantics as current fact (`cards.py:1`, "Expand selection rows into
      per-species, per-root-type production cards"). `publish.py`'s docstrings need **no** change —
      they are card-driven and shape-agnostic; an earlier draft named the wrong file.
- [ ] 3.7 Rewrite `registry/__init__.py:1-8`, whose subpackage docstring also states "per-species,
      per-root-type" as fact.
- [ ] 3.8 Update `tests/test_registry_cards.py`, `tests/test_registry_chooser.py`,
      `tests/test_registry_smoke.py`. Expansion yields **exactly 8 cards**, the shared primary carries
      4 selectors, the two lateral models carry 2 each, every card's metadata validates against the
      real `ModelCard`, legacy models still yield `sleap_nn_version is None`, selectors de-duplicate.
- [ ] 3.9 Re-key `test_matrix_lock_collection_to_model` (`tests/test_registry_cards.py:220-226`). It
      asserts `{collection_id: source_model_id} == <13-entry literal>`; under an
      id-derived-from-model scheme that degenerates to `{slug(x): x}` and stops testing anything.
      Re-key it to lock `source_model_id → sorted selector tuples` (the real matrix invariant) and
      keep an explicit `len == 8`.
- [ ] 3.10 New test: each card's selectors equal an exact **set of 4-tuples**, so the shared primary's
      four windows (canola 2–13, the other three 2–14) are all preserved and none is widened.
- [ ] 3.11 New test: a matrix where one `source_model_id` appears in two root-type slots **fails
      fast**, naming the model id, producing no cards.
- [ ] 3.12 New test: selector order is stable **across processes** with differing `PYTHONHASHSEED`
      (`subprocess` with a modified env). A same-process re-expansion is vacuous — it cannot observe
      hash-salt variation at all.
- [ ] 3.13 New test: selector order is independent of matrix **row order** (shuffle the rows, expect
      identical output).
- [ ] 3.14 New test: every collection id is a legal wandb artifact name, asserted against
      `wandb.sdk.artifacts._validators.validate_artifact_name` (or `INVALID_ARTIFACT_NAME_CHARS`,
      which is exactly `{"/"}`) — **not** a hand-rolled regex. `_FakeArtifact` validates nothing, so
      no existing test can catch a `/` surviving into an id.
- [ ] 3.15 Cross-product regression: no card matches a (species, mode) pair absent from its selectors.
- [ ] 3.16 Update `tests/test_registry_publish.py` and `tests/test_registry_cli.py` **in this same
      commit** — an earlier draft deferred them to commit 2, and simulating the id change alone proves
      that wrong: **11 failures, 9 of them in these two files** (baseline 64 passed), because both
      build their expectations from `collection_id()`. Anchors:
      `test_registry_publish.py:10-11,95,103,108,150,157-158,173,211` (including the hardcoded
      `len(calls) == 13`); `test_registry_cli.py:34-35,115,137,143,173,177-178,200,209-210`; and
      `tests/conftest.py:50-69`, whose `tiny_matrix` ids `soy/p` / `soy/l` must slug to legal names.

## 4. This repo — commit 2: verification and re-publish safety

Genuinely separable from §3: new behavior with new tests, green on its own. Note there is **no**
"delete the per-species duplicate-publish path" task — a previous draft had one and it was a no-op.
`publish.py` is entirely card-driven, so 8 cards produce 8 artifacts with a zero-line diff to that
file; the collapse happens upstream in expansion.

- [ ] 4.1 Extend `--verify` to report production collections the current expansion no longer produces
      (orphan reporting), without deleting or re-pointing them.
- [ ] 4.2 Implement the `--only` interaction and encode it in the help text. `cli.py:105-119` filters
      `all_cards` *before* the expected set is computed, so a canary `--verify --only <one>` would
      report the other 7 new collections **and all 13 old ones** as orphaned. Per the delta spec:
      suppress orphan reporting under `--only`, and say in the output that it was skipped.
- [ ] 4.3 Keep orphans out of the exit code — a missing alias on an *expected* collection fails, an
      orphan is advisory. Test both.
- [ ] 4.4 Tests for orphan reporting, which has **zero** coverage today: an orphan is named; an orphan
      alone does not change the exit code; `--only` suppresses the check and says so.
- [ ] 4.5 Implement the Re-Publish Metadata Refresh check: after publishing, read back the
      production-aliased artifact and confirm the metadata is the new shape, reporting the collection
      as failed if it still carries flat `species`/`mode`/`age_min`/`age_max`. Metadata is **not** in
      the manifest digest (`artifact_manifest_v1.digest()` hashes only the header plus sorted
      path/entry-digest lines), so re-logging identical weights can be a content no-op that leaves
      stale metadata live while the report says `published`; `--force` does not close this
      (`publish.py:146` bypasses only the idempotency read).
- [ ] 4.6 Test with a **legacy-metadata fixture** — an artifact carrying the old flat shape — that the
      read-back check fires. This also pins the 0.3 tolerant-read decision on our side.
- [ ] 4.7 Verify a re-seed of unchanged weights produces an **unchanged** `weights_checksum` (Bloom
      idempotency), with a test. Verify, do not assume — and do not credit selector ordering for it.

## 5. This repo — commit 3: docs (safe standalone)

- [ ] 5.1 `README.md:99-101` "Notes for downstream consumers" states the **opposite** of the new
      design ("one artifact per species (distinct `registry_id`s) ... predict-side dedupe by
      `weights_checksum` is a follow-up"). Rewrite it.
- [ ] 5.2 `README.md:34` ("each stamped with flat `ModelCard` selection metadata") and the canary
      section at `README.md:80-86`, whose `--only <collection_id>` walkthrough still reads as one card
      per species and whose ids change under 0.2.
- [ ] 5.3 `docs/roadmap.md`: `:93` (13 `production` cards), `:102` (#3 "→ 15 cards", which assumes
      per-row expansion), `:182-183` (Tier 2, "already carries 13 `production`-aliased collections"),
      `:194-207` ("Implementation not yet proposed"), `:229` (#39 listed as undecided). Also `:806-807`,
      which repeats the age-window slip corrected in `proposal.md`.
- [ ] 5.4 `openspec/specs/model-registry/spec.md:3-4` still holds the literal `TBD - created by
      archiving change seed-production-model-registry` placeholder. Write a real Purpose while this
      change is touching the capability.
- [ ] 5.5 `docs/CHANGELOG.md` under `[Unreleased]`. Amend the existing entries **in place** rather
      than stacking a contradicting one — `:99-103` introduced "flat `ModelCard` selection metadata",
      `:104-107` says "7 rows → 13 cards over 8 SHA256-pinned models", and `:10` is the
      contracts-pin entry this bump supersedes; all three are unreleased, so editing them is correct
      and appending a reversal is not. Use `**For registry operators:**`, the convention that
      actually exists (`:36`); `**For config authors:**` (`:24`) is the only other one, n=1 each. Do
      **not** invent `**For downstream consumers:**` — it appears nowhere in the file. Call out the
      breaking contract change and the collection-id rename.
- [ ] 5.6 Full suite, `black --check`, `ruff check` green.

## 6. Migration — gated, and a separate PR after this change archives

This group runs against the live registry **after** the code PR merges, so it cannot be ticked in the
same PR. Precedent in this repo: the archive lands as its own docs-only PR — `7e81d80`
(`archive add-config-schema`, #45) and `df411d3` (`archive seed-production-model-registry`, #5, the
change this one supersedes). Plan for two PRs: code, then migration + archive.

- [ ] 6.0 **Rollback prep, before touching anything.** Record the current 13 collection → aliased
      artifact **version** mappings into a file committed with the migration PR. Retirement means
      dropping the `production` alias only — **never delete a collection**; deletion is not
      recoverable, and the alias is what makes a version selectable. Rehearse the alias re-point on
      the canary collection so the rollback path is known to work before it is needed.
- [ ] 6.1 **Canary first:** re-seed a single collection with `seed-registry --only <collection>` (the
      flag exists for exactly this and was used in the `seed-production-model-registry` rollout),
      verify it, then re-seed the remaining 7. A live wandb re-seed is not `git revert`-able. Blocked
      on 2.5.
- [ ] 6.2 Run `--verify` and confirm the orphan report matches the 0.2 decision exactly: **13
      collections under option 1**, 5 under option 3. Read the expected count off the decision; do
      not hardcode a number here.
- [ ] 6.3 Execute the 0.4 decision for those collections — gated on confirmed **deployment** of the
      upgraded `sleap-roots-predict`, not merely on `--verify` passing on the producer side. Producer
      verification proves we wrote the new collections correctly; it says nothing about whether
      anything can read them yet.
- [ ] 6.4 Comment the outcome on #39; link the contracts and predict issues from 1.0 / 2.0, plus #46
      and predict#14, so the four do not drift.
