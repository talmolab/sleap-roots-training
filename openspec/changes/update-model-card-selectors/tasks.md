# Tasks

Groups **1** and **2** are work in *other* repos, recorded as acceptance conditions in **prose, not
checkboxes**. The reason is bookkeeping, not tooling: `openspec archive` only *warns and prompts* on
incomplete tasks (it hard-fails solely in `--json` mode without `--yes`, and this repo's convention is
`--yes`), but a change archived at 41/43 with two boxes nobody here can ever tick is a false record.
The items in those groups that genuinely are ours stay checkboxes. See `proposal.md` "Blocked on".

**TDD.** `openspec/project.md` mandates test-first. Groups 3 and 4 are numbered by *subject* so that
cross-references stay stable, **not** by execution order. Each group states its own execution order,
and in both cases the tests are authored and confirmed red before the implementation tasks.

## 0. Decisions required before implementation (blocking)

- [ ] 0.1 Approve the bundled-selector shape (`Selector`, `ModelCard.selectors`, scalar `root_type`).
- [ ] 0.2 Decide the **collection-id scheme** (`design.md` "Open question"). Recommendation: derive
      from `source_model_id`. This renames all 13 live production collections. **This decision is a
      hard input to everything below** — it sets the orphan count (0.4, §6.2), whether the re-seed is
      additive or in-place (§6.1), whether old-pinned consumers keep a working fallback
      (`design.md` "Reverse compatibility"), and the ordering inside §3. Whatever is chosen, the id
      must be constructible as a `wandb.Artifact` name: every `source_model_id` contains both `/` and
      `=`, and both are illegal (see 3.14).
- [ ] 0.3 Decide the **migration strategy**: flag day vs tolerant read. Recommendation: tolerant
      read, so the production registry is never unreadable by an upgraded consumer. Note this covers
      only new-code-reads-old-data; the reverse direction is handled operationally (0.4). It also
      decides whether §3 is one commit or two, and it is coupled to 0.7.
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
      (unassigned as of this proposal — group 1 blocks everything else). *Not tickable here either;
      kept as a checkbox only because the conversation is ours to start.*
- [ ] 0.6 Once 0.2/0.3/0.4/0.7 are agreed, **fold the decisions back into `design.md`** and update
      this file — including writing the literal id formula into the Collection Identifier Scheme
      requirement in the delta spec **and deleting its pending-decision paragraph**, which otherwise
      archives into the permanent spec as a TODO pointing at a file that has moved into
      `changes/archive/`.
- [ ] 0.7 Decide how `choose_models` behaves when **more than one** production card matches one
      selection context. Under option 1 plus the tolerant read, the interval between the re-seed and
      the retirement has both the old flat card and the new physical-model card matching, e.g.,
      (canola, cylinder, 2–13, primary) — both production-aliased, both valid, both pointing at the
      same weights (`design.md` "Reverse compatibility"). Options: raise on ambiguity, pick by a
      deterministic order, or dedupe on `weights_checksum`. If it does not raise, §6.1's canary MUST
      assert on the **selected card's `registry_id`**, or a passing canary is consistent with the old
      card serving every request. 0.3 and 0.4 are coupled through this: without the tolerant read the
      ambiguity cannot arise.

## 1. Contracts (`sleap-roots-contracts`, separate repo — must land first)

Acceptance conditions this repo waits on; the work and its checkboxes live in that repo's own
OpenSpec change.

- Add `Selector` (`species`, `mode: Mode`, `age_min`, `age_max`) with the existing `age_min`/`age_max`
  validation (reject `bool`/`numpy.bool_`, enforce ordering).
- Change `ModelCard` to `root_type` + `selectors: tuple[Selector, ...]`; reject an empty `selectors`.
  Keep `sleap_nn_version` a scalar card-level field — it describes the weights, not a selection
  context.
- If tolerant read (0.3) is chosen, accept a legacy flat card and lift it to a single selector.
- Release a new pre-release version, and **do not yank it**: `uv.lock` pins contracts from PyPI with
  sdist and wheel hashes, so a yanked or deleted pre-release fails `uv sync --locked` on every CI leg,
  on the PR and on `main`, until the lock is regenerated.

- [ ] 1.0 File the tracking issue/proposal in that repo and link it here (none exists yet). **Ours.**

## 2. Consumer (`sleap-roots-predict`, separate repo)

Acceptance conditions, as above.

- Generalize `choose_models` to "any selector matches all of species/mode/age".
- Match age against the **matching selector**, never a card-level min/max (see `design.md` risks —
  otherwise canola silently gains a year of coverage).
- Add a regression test that a card serving (canola, cylinder, 2–13) and (arabidopsis, multiplant
  cylinder, 2–14) matches **neither** (canola, multiplant cylinder) nor (canola, age 14).
- Implement the 0.7 decision on multiple matching cards.
- Pin the new contracts version.

- [ ] 2.0 File the tracking issue in that repo and link it here (none exists yet); cross-link
      predict#14. **Ours.**
- [ ] 2.5 Read the predict repo and record answers to all of: (a) does its lister enumerate **all**
      collections in the registry project, or only ids it derives itself — because the 8 new
      collections will appear in a full enumeration; (b) does it filter on the `production` alias
      **before** validating metadata? If so, the ~87 non-production collections it tolerates today are
      **not** evidence that it tolerates an unparseable production card, and that argument must not be
      used; (c) on a card that fails `ModelCard` validation, does it skip with a warning or **raise**,
      and per-collection or for the whole listing — fail-closed on the first bad card means the canary
      is itself the outage and §6 must be re-planned; (d) its behavior when more than one production
      card matches (feeds 0.7); (e) whether any persisted state — warm-cache keys, Bloom job records,
      config — is keyed on `registry_id`, which option 1 changes for every model even though
      `weights_checksum` does not. **Ours, and blocking §6.1.**

## 3. This repo — pin + expansion + metadata + collection id + tests

**Execution order (TDD):** 3.1 first (a hard prerequisite — no test can import `Selector` before the
pin), then author 3.8–3.26 and **confirm they fail for the intended reason** (`AttributeError` /
`ImportError` on `Card.selectors`, not an incidental error), then implement 3.2–3.5 to green, then
3.6/3.7 docstrings, then the 3.G gate.

**Commit boundary — one commit or two, decided by 0.3.** Two things genuinely force files together:
`uv sync --locked` requires `pyproject.toml` and `uv.lock` to move as a pair, and
`tests/test_registry_chooser.py:180` (`ModelCard.model_fields["species"]`) raises `KeyError` the moment
the contract drops card-level `species`, so no pin-only commit is green. That forces three or four
files, not nine. An earlier draft claimed a split "would redden `main`" — it would not: this repo
squash-merges and Actions builds the push tip, so no intermediate commit is ever built on `main`. The
residual cost of a red intermediate commit is `git bisect` and `git blame`, not CI.

- Under **0.3 = tolerant read** (recommended): commit A = 3.1 plus the contract-facing test
  adjustments (chooser, smoke, and the `.species`/`.mode` attribute assertions in
  `test_registry_cards.py`) — verified green, because all 13 *unchanged* flat cards still validate
  against a tolerant-read `ModelCard`. Commit B = 3.2–3.5 plus the rest of the tests.
- Under **0.3 = flag day**: A and B merge, because the old cards stop validating the instant the pin
  moves.

**Ordering inside the group:** 3.5 must land **with or before** 3.2 — 3.2's `(source_model_id,
root_type)` grouping key silently tolerates a model in two slots by emitting two cards, which is
exactly what 3.5 forbids. And 3.4 depends on 0.6, not just 0.2: the formula belongs in the delta spec
before it is implemented. Expect the full suite to be red from 3.1 until the last test lands; drive it
per file (`pytest tests/test_registry_cards.py` etc.) rather than by whole-suite runs.

- [ ] 3.1 Bump the `sleap-roots-contracts` pin (`pyproject.toml`, `uv.lock` together).
- [ ] 3.2 Rewrite `expand_rows_to_cards` to group by `(source_model_id, root_type)` and attach one
      selector per contributing row, **de-duplicated** and sorted on an explicit key
      (`key=lambda s: (s.species, s.mode, s.age_min, s.age_max)`) — a frozen pydantic `Selector` is
      hashable but **not** orderable, so a bare `sorted(selectors)` raises `TypeError`, and a
      set-based dedupe leaves the order salted by `PYTHONHASHSEED`.
- [ ] 3.3 Update `card_to_metadata` to emit `selectors` + `root_type` + `source_model_id`, still
      omitting `registry_id` / `version` / `weights_checksum`, and emitting no card-level `species` /
      `mode` / `age_min` / `age_max`. Selectors must be **plain JSON-native dicts**, not `Selector`
      instances: `wandb.Artifact(metadata=...)` runs the mapping through `validate_metadata`, which
      coerces rather than rejects, degrading a pydantic model to its `repr` string and a `NamedTuple`
      to a positional list — publishing unreadable metadata with a zero exit code.
- [ ] 3.4 Implement the chosen `collection_id` scheme in the one existing function, so publish,
      `--only`, and `--verify` cannot disagree; keep the duplicate-id fail-fast guard.
- [ ] 3.5 Assert every physical model resolves to exactly one `root_type`, failing the seed loudly if
      a future matrix edit breaks that assumption (the whole design rests on it).
- [ ] 3.5b Add the **selector-collision** guard: two different `source_model_id`s of the same
      `root_type` carrying an identical `(species, mode, age_min, age_max)` selector must fail fast.
      Today this is caught incidentally, because the id is built from those four fields and the
      duplicate-id check rejects the pair; an id derived from the model gives them distinct ids, so
      both would publish, both would take the production alias, and the consumer would find two
      matching production cards. Verified no such collision exists in the committed matrix, so this
      guards the future the existing "guard against future matrix edits" scenario is about.
- [ ] 3.6 Rewrite the `cards.py` module/class/function **docstrings**, which describe the per-row,
      per-species semantics as current fact (`cards.py:1`; also the `collection_id` docstring's
      `Returns: "rice-cylinder-crown-age6-10"` example). `publish.py`'s docstrings need **no** change
      — they are card-driven and shape-agnostic; an earlier draft named the wrong file.
- [ ] 3.7 Rewrite `registry/__init__.py:1-8` ("per-species, per-root-type") **and**
      `registry/chooser.py:21-23`, whose comment asserts "``ModelCard.species`` is a free ``str``, so
      there is no contract-side vocabulary to defer to" — false once card-level `species` is gone.
      `SPECIES_VOCAB` still stays local; the reason becomes "a *selector's* `species` is a free `str`".
- [ ] 3.8 Update `tests/test_registry_cards.py`, `tests/test_registry_chooser.py`,
      `tests/test_registry_smoke.py`. Expansion yields **exactly 8 cards**, the shared primary carries
      4 selectors, the two lateral models carry 2 each, every card's metadata validates against the
      real `ModelCard`, legacy models still yield `sleap_nn_version is None`.
- [ ] 3.9 Re-key `test_matrix_lock_collection_to_model` (`tests/test_registry_cards.py:220-226`). It
      asserts `{collection_id: source_model_id} == <13-entry literal>`; under an
      id-derived-from-model scheme that degenerates to `{slug(x): x}` and stops testing anything.
      Re-key it to lock `source_model_id → sorted selector tuples` (the real matrix invariant) and
      keep an explicit `len == 8`.
- [ ] 3.10 New test: each card's selectors equal an exact **set of 4-tuples**, so the shared primary's
      four windows (canola 2–13, the other three 2–14) are all preserved and none is widened.
- [ ] 3.11 New test: a matrix where one `source_model_id` appears in two root-type slots **fails
      fast**, naming the model id, producing no cards. Plus the 3.5b sibling: two models of one
      root_type sharing a selector fails fast, naming the selector and both model ids.
- [ ] 3.12 New test: selector order is stable **across processes** with differing `PYTHONHASHSEED`,
      using ≥3 seeds and the existing helper pattern at `tests/test_registry_chooser.py:236-256`
      (`env = dict(os.environ)` then mutate, `[sys.executable, "-B", "-c", ...]`) — a bare
      `env={"PYTHONHASHSEED": "1"}` breaks on Windows for want of `SYSTEMROOT`. Note `PYTHONHASHSEED=0`
      *disables* randomization, so 0-vs-1 is the discriminating pair. A same-process re-expansion is
      vacuous. Compare the **serialized JSON** from the child's stdout, which also discharges the
      scenario's "byte-identical metadata" clause.
- [ ] 3.13 New test: selector order is independent of matrix **row order** (shuffle the rows, expect
      identical output).
- [ ] 3.14 New test: every collection id is accepted by the **real `wandb.Artifact` constructor** —
      `wandb.Artifact(name=cards.collection_id(card), type="model")`, which is public API, offline, and
      needs no credential. Do **not** assert against
      `wandb.sdk.artifacts._validators.validate_artifact_name` or `INVALID_ARTIFACT_NAME_CHARS`:
      verified that `Artifact.__init__` applies `^[a-zA-Z0-9_\-.]+$` *before* calling that validator,
      so `=` is illegal too, and `validate_artifact_name` **accepts**
      `canola_pennycress_arabidopsis-primary-240611_102513.multi_instance.n=743` while the constructor
      rejects it. Asserting against the validator is a false green whose production symptom is
      `--execute` raising on the first card. `INVALID_ARTIFACT_NAME_CHARS` is exactly `{"/"}` and is
      **not** the effective rule. Also assert the 128-char `NAME_MAXLEN` bound.
- [ ] 3.15 Cross-product regression: no card matches a (species, mode) pair absent from its selectors.
- [ ] 3.16 Update `tests/test_registry_publish.py` and `tests/test_registry_cli.py` **in the same
      commit as 3.2–3.4** — an earlier draft deferred them, and simulating the id change alone proves
      that wrong: **11 failures, 9 of them in these two files** (against the full 226-test suite;
      nothing outside these plus `test_registry_cards.py` moves). Both build expectations from
      `collection_id()`. Anchors: `test_registry_publish.py:10-11,95,103,108,150,157-158,173,210,211`
      (including the hardcoded `len(calls) == 13`);
      `test_registry_cli.py:34-35,115,123,137,143,173,177-178,196-197,200,209-210`. Note
      `tests/conftest.py` needs **no** edit — `soy/p`/`soy/l` slug fine; the constraint it carries is on
      the slug function, not on the file.
- [ ] 3.17 Re-author `test_seed_duplicate_collection_aborts` (`tests/test_registry_publish.py:154-163`).
      Verified: under an id derived from `source_model_id` the current `"a"`/`"b"` fixture **DID NOT
      RAISE**, and id collisions become otherwise structurally impossible (grouping is by
      `(source_model_id, root_type)`; 3.5 rejects a model spanning two root types). The remaining
      collision channel is a **lossy slug** — `/` and `=` must both map to some legal character, so two
      ids differing only there collapse. Build the fixture from that (`x/y` and `x=y`), assert the
      seed raises before any publish and names both, and add a sibling asserting the 8 committed model
      ids slug to 8 distinct ids.
- [ ] 3.18 New test: `card_to_metadata` is **serialization-stable**. Verified the real
      `wandb.Artifact` normalizes metadata (tuple → list, object → dict, pydantic model → `repr`
      string) while `_FakeArtifact` (`tests/test_registry_publish.py:25-33`) stores it verbatim, so
      `art.metadata == card_to_metadata(card)` (`:103`) is a tautology that cannot catch it. Assert
      `json.loads(json.dumps(meta)) == wandb.Artifact(name="n", type="model", metadata=meta).metadata`
      for a real card, with `selectors` a list of dicts of primitives **in the emitted order**. This
      also settles what §4's read-back may compare against.
- [ ] 3.19 New test: the shared primary's `selectors` equal an exact **ordered tuple literal**. 3.10
      (set equality) plus 3.12/3.13 (relative "same order twice") are all satisfied by a stably-wrong
      order, so nothing else pins the absolute one.
- [ ] 3.20 Re-key `test_every_accepted_mode_round_trips_through_the_real_modelcard`
      (`tests/test_registry_cards.py:141-155`) and `test_expected_modes_match_the_live_vocabulary`
      (`:136`) onto the selector shape — the "Every accepted mode survives the round trip" scenario
      otherwise has no test, and the current test builds a flat `cards.Card(...)` that stops
      compiling. Keep `_EXPECTED_MODES` spelled out so an upstream narrowing stays a failure.
- [ ] 3.21 New test: a metadata mapping with an empty `selectors` list fails `ModelCard` validation.
      Update `tests/test_registry_smoke.py:12-31`, which builds the flat six-key card, at the same time.
- [ ] 3.22 New test: `sleap_nn_version` stays a **card-level scalar** and is absent from `Selector` —
      assert it is not in any emitted selector dict and not in `Selector.model_fields`.
- [ ] 3.23 New test: `card_to_metadata` emits an **exact** key set of
      `{root_type, selectors, source_model_id}` and no card-level `species`/`mode`/`age_min`/`age_max`.
      Re-key `test_card_to_metadata_exact_keys_and_raw_mode` (`tests/test_registry_cards.py:95-112`).
- [ ] 3.24 New test: the one-scheme invariant — monkeypatch `cards.collection_id` to a sentinel and
      assert the publish path, the `--only` filter (`cli.py:107-114`), and the `--verify` expected set
      (`cli.py:115-119`) all observe it.
- [ ] 3.25 New test: the two rice crown models remain two distinct cards in two distinct collections.
- [ ] 3.26 New test: a **stale old-scheme** `--only` id (e.g. `canola-cylinder-primary-age2-13`, as
      sitting in runbooks and `README.md` today) fails fast via `cli.py:110-113` with an actionable
      message. `test_only_unknown_fails_fast` (`tests/test_registry_cli.py:148`) covers only a
      synthetic `does-not-exist`.
- [ ] 3.27 Check `scripts/regen_model_checksums.py:24` (`expand_rows_to_cards`, `c.source_model_id`)
      still works. It is in **no** CI path filter, **no** lint target, and **no** test, so a break
      there is silent. Consider adding it to `tests/test_scripts.py`, which currently imports only the
      other three scripts.
- [ ] 3.28 Check `tests/test_config.py:322-329`
      (`test_root_type_vocab_mirrors_cards_slots`, asserting `config.ROOT_TYPE_VOCAB ==
      frozenset(cards._ROOT_SLOTS)`) — green only while 3.2 preserves `_ROOT_SLOTS`.
- [ ] 3.G Gate before committing: `uv lock --check`, `uv run pytest -m "not integration"`,
      `uv run black --check src/sleap_roots_training tests`,
      `uv run ruff check src/sleap_roots_training`. `uv lock --check` is load-bearing here and nowhere
      else: CI installs with `uv sync --locked` (`ci.yml:42,81`), so a lock drifting from 3.1 reddens
      all six matrix legs at install time, before a single test runs.

## 4. This repo — verification and re-publish safety

**Execution order (TDD):** author 4.4, 4.6, 4.8–4.11 and confirm red, then implement 4.1–4.3 and 4.5,
then 4.7, then the 4.G gate.

**This group is *not* green without touching existing tests** — an earlier draft claimed it was, and
that is disproven the same way §3's boundary was. Verified: putting the 4.5 read-back in
`seed_registry` reddens `test_seed_publishes_all_distinct` (`test_registry_publish.py:151`, which
asserts `report["published"] == calls`); putting it in `publish_card` instead reddens `test_publish_card`
with a **real network call**, because that test monkeypatches `wandb.Artifact` but not `wandb.Api`; and
4.1–4.3 redden `test_verify_only_scopes` and `test_verify_needs_no_models_root`, both of which
monkeypatch `verify_registry` with the frozen signature `(cfg, expected, api=None)`
(`test_registry_cli.py:185,208`). So 4.12 is mandatory, not optional.

There is deliberately **no** "delete the per-species duplicate-publish path" task — a previous draft
had one and it was a no-op. `publish.py` is entirely card-driven, so 8 cards produce 8 artifacts with
no diff to `publish_card`; the collapse happens upstream in expansion.

- [ ] 4.1 Extend `--verify` to report production-aliased collections the current expansion no longer
      produces, without deleting or re-pointing them. Determine alias membership **without**
      paginating every version of every collection: `_collection_has_production` (`publish.py:65-76`)
      pages every version at 50/page and is fine for 8 expected collections, but the registry holds
      ~100 collections, most of them sweep/run artifacts. Use `ArtifactCollection.aliases` (one light
      query per collection) or `Registry.versions(...)` (one paginated stream carrying collection name
      + membership aliases + metadata, which answers orphan reporting **and** 4.2's shape check at
      once). `_existing_collections` (`publish.py:57-62`) currently discards the collection objects to
      a set of names and will need to keep them.
- [ ] 4.2 Add the metadata **shape** check to `--verify`: for each expected collection whose
      production-aliased artifact is present, report whether its metadata is the `selectors` shape or
      the legacy flat shape, and exit non-zero on legacy. Without this, `--verify` reports `present`
      for a collection an upgraded consumer cannot read, and §6.2 has no re-runnable way to ask
      whether the registry is migrated. The check must be **structural** (`selectors` present, no
      card-level `species`/`mode`/`age_min`/`age_max`) and must **not** be
      `ModelCard.model_validate(...)`: under 0.3's tolerant read the legacy blob validates fine, so a
      validation-based check reports every stale collection as current.
- [ ] 4.3 Implement the `--only` interaction and encode it in the help text (`cli.py:64`).
      `cli.py:105-119` filters `all_cards` before the expected set is computed, so a canary
      `--verify --only <one>` would report every other collection as orphaned. Suppress orphan
      reporting under `--only` and say so in the output; keep orphans and indeterminate collections
      out of the exit code, while a missing alias or a legacy shape on an *expected* collection fails.
- [ ] 4.4 Tests for orphan reporting, which has **zero** coverage today: an orphan is named; a
      non-production collection is not; an orphan alone does not change the exit code; an
      undeterminable collection is reported indeterminate and does not change the exit code; `--only`
      suppresses the check and says so. Give the fake **spy** `delete`/`link` methods that fail the
      test if called, so the scenario's "does not delete or move the alias" is actually asserted
      rather than passing by `AttributeError`.
- [ ] 4.5 Implement the Re-Publish Metadata Refresh check and its remedy. Read back the server's own
      view — after `logged.wait()`, `logged.metadata` and `logged.digest` are the server's values
      (`wait()` re-fetches), and `run.link_artifact(...)` already returns a membership-backed artifact
      carrying `metadata`, `digest`, and the membership aliases, which `publish.py:46` currently
      **discards** — so no extra query is needed. Do not resolve the read-back through
      `Artifact._from_id`, which returns a process-cached instance. Where the metadata is stale,
      refresh it in place (`Artifact.metadata = ...; Artifact.save()`, i.e. `updateArtifact`) and
      re-read; if it still does not take, report the collection in a distinct `failed` bucket, exit
      non-zero, and continue with the remaining cards. `--force` does not close this
      (`publish.py:146` bypasses only the idempotency read) and cannot create a new version while the
      digest is unchanged.
- [ ] 4.6 Test with a **legacy-metadata fixture** that the read-back fires: `_FakeArt`
      (`test_registry_publish.py:67-69`) gains `.metadata`, `_FakeApi` (`:72-85`) gains
      `artifact(name, type=None)` matching `wandb.Api.artifact`'s signature. Record explicitly that
      the offline test covers **our classifier only** — the premise that wandb leaves the previous
      metadata live after a content-identical re-log is server behavior no fake can confirm (see 6.5).
- [ ] 4.7 Verify a re-seed of unchanged weights produces an **unchanged** `weights_checksum` (Bloom
      idempotency), with a test. `logged.digest` after `wait()` gives this for free. Verify, do not
      assume — and do not credit selector ordering for it.
- [ ] 4.8 Test that the read-back is **structural**, not contract validation: a legacy blob that
      validates fine under a tolerant-read contract is still classified stale.
- [ ] 4.9 **Negative control:** an artifact whose metadata carries `selectors` and no card-level
      selection keys is reported **published**, not failed. Without it, a checker that fails
      everything passes 4.6 — the discrimination gap `tests/test_registry_chooser.py:276` already
      guards against elsewhere ("the guard must discriminate, not just fail").
- [ ] 4.10 Close the `skipped`-path hole and test it. `publish.py:151-159` skips a collection that
      already carries the production alias, so a check scoped to collections reported `published`
      never sees it — and the skip path is the default on every re-run, so a half-migrated collection
      sits there undetected. Check the metadata shape on the skip path too and report it distinctly.
- [ ] 4.11 Test that `--force` alone does not satisfy the refresh check: a `--force` re-seed of
      byte-identical weights whose read-back metadata is still flat is reported **failed**.
- [ ] 4.12 Update `tests/test_registry_publish.py` and `tests/test_registry_cli.py` for the new
      `failed` bucket, the widened `verify_registry` signature, and the new report keys —
      `seed_registry` returns only `{"published", "skipped"}` today (`publish.py:163`) and
      `cli.py:184-185` echoes only those. See this group's header for the four tests that go red and
      why. Also make `test_publish_card` monkeypatch `wandb.Api` so a unit test cannot reach the
      network.
- [ ] 4.13 Make a partial failure recoverable: `seed_registry` logs each publish with `logger.info`,
      nothing in the package configures logging, and `cli.py:179-183` never reaches its `click.echo`
      of the report if an exception propagates. After a failure at card 5 of 8 the operator has **no
      local record** of which collections now carry `production`. Echo per-collection outcomes to
      stdout as they happen, and surface the partial report on failure.
- [ ] 4.G Same gate as 3.G before committing.

## 5. This repo — docs (safe standalone)

Verified standalone-safe: no test reads the files this group edits (`tests/test_training_docs.py` and
`tests/test_backend_docs.py` lock only `docs/training.md` and `docs/training-backend.md`). Land it
**last** and rebase rather than merge — `docs/roadmap.md` is the highest-churn file in the repo and
another branch is already editing the adjacent `LabelCard` material.

- [ ] 5.1 `README.md:99-101` "Notes for downstream consumers" states the **opposite** of the new
      design ("one artifact per species (distinct `registry_id`s) ... predict-side dedupe by
      `weights_checksum` is a follow-up"). Rewrite it, and add that age is read off the **matching
      selector**, never a card-level min/max.
- [ ] 5.2 `README.md:34-35` ("each stamped with **flat** `ModelCard` selection metadata") and
      `README.md:74-79` "Rerun contract", which advertises `--force` as the way to move an alias — now
      explicitly not sufficient evidence of a metadata refresh (§4.5). The canary section at
      `README.md:81-85` needs the `--verify --only` orphan-suppression note and "seeds the rest" is 7,
      not 12; it does **not** need an id update, since it uses the `<collection_id>` placeholder.
- [ ] 5.3 `docs/roadmap.md`: `:93-94` (13 `production` cards), `:102` (#3 "→ 15 cards", per-row math),
      `:182-183` ("already carries 13 `production`-aliased collections"), `:191-208` (the whole
      "Shared/generalist models have no way to be represented once" bullet — note `:191-193` is the
      present-tense framing an earlier draft's `:194-207` range missed), `:229` (which reads "not the
      13 `ModelCard` registrations", **not** "#39 undecided"), `:282` ("train once per distinct
      `weights_checksum`, **not once per card**" — the contrast inverts once one card *is* one physical
      model), and `:558-562` in the live "Open roadmap decisions" section, which is the actual
      "implementation still to be proposed" line. Collapse `:191-208` to the direction plus a pointer
      to #39 and this change rather than re-deriving the matrix math a fourth time.
- [ ] 5.4 `docs/roadmap.md:805-806` carries the age-window slip corrected in `proposal.md` — but it
      sits inside the **dated append-only** revision log (`:796`, under the reconciliations section
      whose own rule at `:648-650` says editing prior dated entries contradicts append-only). Follow
      this repo's established pattern for correcting written prose: a dated inline marker
      (`**Correction (2026-08-xx):**`, as at `docs/roadmap.md:161-167` and `docs/CHANGELOG.md:66`), or
      append the correction in the new revision entry. Do **not** silently rewrite the dated bullet.
- [ ] 5.5 `openspec/specs/model-registry/spec.md:3-4` still holds the literal `TBD - created by
      archiving change seed-production-model-registry` placeholder. Write a real Purpose while this
      change is touching the capability.
- [ ] 5.6 `docs/CHANGELOG.md` under `[Unreleased]`. Amend in place — nothing here has shipped
      (`0.0.1a0`), so a reader of the next release must not see "added flat metadata" followed by
      "removed flat metadata" for a shape they never saw. Specifically: `:99-103` ("flat `ModelCard`
      selection metadata"), `:104-107` ("7 rows → 13 cards over 8 SHA256-pinned models" → 8 cards, one
      per physical model), and inside the `:10-58` contracts-pin entry, `:14-15` ("`ModelCard.species`
      is a free `str`, so there is no contract-side species vocabulary") and `:20`
      ("`ModelCard.mode` is a `Mode`") — both become false and both sit deep inside a 48-line entry, so
      they must be named or they will be walked past. Put the breaking-change and id-rename narrative
      in the `### Changed` entry, **not** inside `### Added`. Use `**For registry operators:**`, which
      exists at `:36`; `**For config authors:**` (`:24`) is the only other, and both sit in one entry —
      a formatting habit rather than a deep convention, so reuse it because it is the accurate
      audience. Do **not** invent `**For downstream consumers:**`; it appears nowhere in the file.
- [ ] 5.7 Full suite, `black --check`, `ruff check` green.

## 6. Migration — gated, and a separate PR after this change archives

Runs against the live registry **after** the code PR merges. Precedent: the archive lands as its own
docs-only PR — `7e81d80` (`archive add-config-schema`, #45) and `df411d3` (`archive
seed-production-model-registry`, #5, the change this one supersedes). Note the precedent also shows
these tasks get **ticked**: `seed-production-model-registry`'s live-wandb group 9 was `[x]` when it
archived. So tick 6.0–6.5 in the migration PR before running `openspec archive`. That PR runs no CI
(`openspec/**` is not in `ci.yml`'s path filters), and its risky part is the capability-spec promotion,
not the file move.

**Migration steps are single-operator.** `_existing_collections` is read once up front
(`publish.py:146`), so two concurrent `--execute` runs both see a collection as absent, both publish,
and the alias lands wherever `link_artifact` ran last — with both reporting success. Announce the
window, and re-run `--verify` immediately before 6.3 to confirm nothing else wrote since 6.2.

- [ ] 6.0 **Rollback prep, before touching anything.** An earlier draft wrote this for an *in-place*
      migration; under option 1 nothing is overwritten, so there is no old alias to re-point and the
      real rollback runs the other way. (a) Record the current 13 collection → aliased artifact
      **version** mappings to a file committed with this PR, as a baseline snapshot. (b) The rollback
      for an additive re-seed is to **remove `production` from the newly created collections**
      (`Artifact.aliases` + `.save()`, i.e. `deleteAliases`; or `Artifact.unlink()` to drop the
      membership) — rehearse *that* on the canary, not an alias re-point. (c) **Never delete a
      collection**: deletion is not recoverable, and the alias is what makes a version selectable.
      (d) Record each new collection's first version as it is created, which is what a
      resume-after-partial-failure needs (see 4.13).
- [ ] 6.1 **Canary first**, and make it falsifiable. Re-seed one collection with
      `seed-registry --only <collection>`, then: (a) `--verify --only <id>` for producer-side alias +
      new-shape read-back; (b) run the **upgraded** predict's selection against the live registry for
      that collection's selection contexts and assert the chosen card's `registry_id` is the **new**
      collection — under option 1 plus the tolerant read it now competes with the old card for the same
      context (0.7), so "selection succeeded" proves nothing; (c) if an un-upgraded deployment is still
      reachable, confirm it still resolves those contexts from the untouched old collection and did not
      fail listing. Only then re-seed the remaining 7. A live wandb re-seed is not `git revert`-able.
      Blocked on 2.5 and 0.7.
- [ ] 6.2 Run a **full** `--verify` (never a canary run — orphan reporting is suppressed under
      `--only`) and confirm the orphan report matches the 0.2 decision: **13 collections under option
      1**, 5 under option 3. Read the expected count off the decision; do not hardcode one. While
      here, record the registry's actual storage figures for the 13 collections, so `proposal.md` can
      stop hedging about whether the duplication ever cost real bytes.
- [ ] 6.3 Execute the 0.4 decision — gated on confirmed **deployment** of the upgraded
      `sleap-roots-predict`, not merely on `--verify` passing on the producer side. Producer
      verification proves we wrote the new collections correctly; it says nothing about whether
      anything can read them yet. Acceptance: after retirement, `--verify` reports zero orphans and
      zero legacy-shape expected collections; paste that output into the PR.
- [ ] 6.4 Comment the outcome on #39, and **post the correction** to its 2026-08-10 comment (the
      canola/pennycress pair differs by species *and* age, not "only by age"), so the issue this
      proposal names as the source of truth stops contradicting the landed design. Link the contracts
      and predict issues from 1.0 / 2.0, plus #46 and predict#14.
- [ ] 6.5 While the canary is live, settle the question no offline fake can: re-log one card with
      byte-identical weights and record whether the production-aliased artifact's metadata actually
      refreshed. If it does, the Re-Publish Metadata Refresh requirement is over-built and should be
      downgraded; if it does not, this is the only direct evidence for it that exists.
- [ ] 6.6 In the archive PR, restore the requirement order in
      `openspec/specs/model-registry/spec.md`. Verified: because the expansion and publishing
      requirements are replaced (removed + re-added) rather than modified in place, the archiver
      appends them at the **end** of the file, so the spec reads matrix → metadata → resolution →
      lineage → ... → expansion → publishing. Move the two back above `ModelCard Selection Metadata`
      and `Legacy Model Directory Resolution` respectively.
