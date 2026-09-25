## 0. Pre-implementation decisions (gate: all resolved before §1)

- [x] 0.1 ~~Verify `LabelCard` schema permits `null` for provenance fields~~ — **resolved:** the
      seven provenance fields are `Optional`; the other 15 are required and non-nullable.
      Confirmed against `0.1.0a6` when the question was first asked, and re-confirmed against
      `0.1.0a8` — the release `main` now pins since #47 — where the 7/15 split is unchanged. See
      D1 (the seven) and D7 (the four required ones that are not recoverable from the blob). The
      earlier "no contracts bump needed" reading answered only the provenance half of this
      question.
- [x] 0.2 ~~Decide disposition of medicago~~ — **resolved:** `medicago` is in scope.
- [x] 0.3 ~~Confirm `wheat`, `sorghum`, `medicago` should be added to `SPECIES_VOCAB`~~ —
      **resolved: no.** They go into a new label-side `LABEL_SPECIES_VOCAB`; `SPECIES_VOCAB` is
      unchanged, because it validates the model selection matrix and `experiment.species` in a
      training config, not just labels. See D5. Note the criterion is "no model **in
      `wandb-registry-sleap-roots-models`** and no `model_selection.yaml` row" — not "never
      modelled". Wheat has been trained (the `seminal_root_generalist` work in D3); it is simply
      not in this registry.
- [x] 0.4 ~~Verify the contract's `RootType` accepts `seminal`~~ — **resolved: it does not**, on
      the pin or at contracts HEAD (`0.1.0a8`) — **and the question was the wrong one.** Wheat's
      roots at this age are labeled `crown` in this project, so the card records `crown` and no
      vocabulary changes anywhere. See D3. A nickname/alias concept is tracked upstream as
      `sleap-roots-contracts#34`; low priority, not a dependency.

## 1. Upstream: contracts pin (no new release unless §2 requires one)

D3 no longer needs a contract change, and the `a7`/`a8` pin catch-up that used to sit here is
**already done** — #47 (`b102d43`) landed `sleap-roots-contracts==0.1.0a8` on `main`. So this
section is now *only* whatever D7's gate turns out to require, and if 2.5 reports all four fields
recovered it is empty. 1.3 is conditional on 2.5 and therefore completes after §2.

- [x] 1.1 ~~Open a change directory in `sleap-roots-contracts` for the pin catch-up~~ — **struck:**
      #47 bumped the pin to `0.1.0a8` on `main` directly, so there is no `a6 → a8` delta left to
      review. (Correction to the struck text: the
      `archive/2026-08-05-update-contracts-pin-0-1-0a6` precedent it cited lives in **this** repo,
      not in `sleap-roots-contracts` — contracts has no pin change in its archive.)
- [x] 1.2 ~~Bump the pin in `pyproject.toml` here~~ — **struck:** `pyproject.toml:46` already reads
      `sleap-roots-contracts==0.1.0a8`.
- [ ] 1.3 **Conditional on 2.5** — if any of `age_min`/`age_max`/`n_plants`/`n_scans` is
      unrecoverable for any collection, relax that field (and only that field) to `Optional` in a
      contracts release, with the reason recorded in the contracts change's design. If 2.5 reports
      all four recovered everywhere, this task is struck, not deferred.
- [ ] 1.4 **Conditional on 1.3, and ordered before §4** — if 1.3 cuts a contracts release, bump this
      repo's pin in `pyproject.toml` to *that* release and confirm the full suite passes unfiltered,
      not only under CI's `-m "not integration"` (#53). Without this task §4 builds cards against
      `a8`, where the relaxed fields are still required, and the fallback never takes effect here.
      If 1.3 is struck, so is this.

## 2. Provenance reconstruction (archaeology) — gates §3

The output of this section is a **committed mapping file**, not notes. §4 builds every card from it,
so anything not written down here does not exist downstream.

- [ ] 2.1 For each of the 8 collections, pull the artifact from wandb and extract:
      - `description` free text
      - Existing metadata keys
      - Frame/video counts from the `.slp` or `.pkg.slp` blob
      - Any recoverable `bloom_experiment_id`, accession IDs, species confirmation
- [ ] 2.2 Record findings as a **checked-in mapping file** (YAML) per collection: which fields were
      recovered, from which source, which are `null`, and a confidence level. Include the
      **original collection name** on every entry — D4 drops the nickname from the normalized name,
      and this is the only place `seminal` survives for anyone searching by it.
- [ ] 2.3 Verify single-species content: sample frames from each collection to confirm no
      mixed-species data. Record methodology, sample size, and findings per collection in the 2.2
      mapping. This is the one-time human pass; 4.8 is the code that re-checks it on every run.
- [ ] 2.4 For each collection, determine the node count per root type from the `.slp` skeleton.
      This is also the verification `skeletons.yaml`'s header names as what flips its remaining
      rows from `verified: false` — record the result in a form that change can consume.
- [ ] 2.5 **D7 gate.** Report, per collection, whether `age_min`, `age_max`, `n_plants`, and
      `n_scans` were recovered. Expect the two soybean (`Z:`-drive) collections to be the hard
      cases for age, and `n_plants`/`n_scans` to be unrecoverable from any blob. Whichever fields
      come back unrecoverable are what 1.3 relaxes; if all four are recovered everywhere, 1.3 is
      struck and no contracts release is needed.
- [ ] 2.6 Confirm the wheat collection's root type against the blob rather than its name: the
      skeleton's node names are what say whether it matches the existing `crown` rows. D3 rests on
      this being crown-shaped, so it is checked rather than assumed.

## 3. Species vocabulary split

#50 has landed (`54609a9`), so `labeling/metadata.py` and `labeling/skeletons.py` are already on
the single contract-derived `ROOT_TYPE_VOCAB` this section is written against. No coordination is
left; this branch is rebased onto it.

Root type does **not** split (D3). Only species does.

- [ ] 3.1 **Test:** `LABEL_SPECIES_VOCAB` is a strict superset of `SPECIES_VOCAB` and the
      difference is exactly `{"wheat", "sorghum", "medicago"}` (red).
- [ ] 3.2 Add `LABEL_SPECIES_VOCAB` to `registry/chooser.py`, defined as `SPECIES_VOCAB | {...}`
      so the superset relation cannot drift (green).
- [ ] 3.3 **Test — a source check, because a set comparison cannot see this.** 3.1 already compares
      the sets, and that is all a runtime assertion can do: both vocabularies are module-level
      `frozenset`s computed at import, so monkeypatching `SPECIES_VOCAB` and reloading `chooser`
      re-executes the original source either way. A literal copy that happens to match today is
      indistinguishable from a derived superset at runtime. Assert on the **source** instead —
      parse `chooser.py` with `ast` and assert the `LABEL_SPECIES_VOCAB` assignment references the
      name `SPECIES_VOCAB`. This repo has watched the copy-drift happen: #40 landed a third
      `ROOT_TYPE_VOCAB` copy whose docstring claimed to match the contract with nothing checking
      it.
- [ ] 3.4 **Test:** `PackageMetadata` accepts `species="wheat"`, and the skeleton-table loader
      accepts a `wheat` row (red).
- [ ] 3.5 Point `labeling/metadata.py` and `labeling/skeletons.py` at `LABEL_SPECIES_VOCAB` for
      `species` only. Their `root_type` / `root_types` validation stays on `ROOT_TYPE_VOCAB`,
      untouched (green).
- [ ] 3.6 **Test — the half that must NOT change:** `experiment.species: wheat` is still rejected
      by `config.validate_config` (`config.py:112` — the public name; there is no `config.validate`);
      the selection-matrix loader still rejects a `wheat` row;
      `frozenset(cards._ROOT_SLOTS) == chooser.ROOT_TYPE_VOCAB` still holds — that one already
      exists at `tests/test_registry_cards.py:379-381`, so reference it rather than restating it;
      and
      `experiment.root_type: seminal`, a labeling package with `root_types: [seminal]`, and a
      `seminal` skeleton-table row are all still rejected. This is the test that makes the split a
      split rather than a widening — and the last three are what stop `seminal` creeping back in
      through the label side.
- [ ] 3.7 Confirm all existing tests still pass after the split, unfiltered (`pytest` with no
      marker filter — CI's `-m "not integration"` would not run several of these).

## 4. LabelCard metadata construction

- [ ] 4.1 **Test:** a card built from a collection with *full* provenance validates against the
      contract with every provenance field populated (red).
- [ ] 4.2 **Test:** a card built from a collection with *unrecoverable* provenance validates with
      exactly those `Optional` fields `None` — asserted field by field, not as one blob. Split from
      4.1 deliberately: one test over both cases passes while either half is broken.
- [ ] 4.3 Implement `label_cards.py`: read the §2.2 committed mapping and build each `LabelCard`
      (species, mode, root_type, node_count, age range, provenance). Unrecoverable `Optional`
      fields are explicitly `None`.
- [ ] 4.4 **Test:** the normalized collection name for each card follows `{species}-{mode}-{root_type}`,
      asserted against all eight expected names spelled out — including `wheat-cylinder-crown`,
      whose old name says `seminal`.
- [ ] 4.5 Implement `collection_id()` for label cards following D4's naming convention.
- [ ] 4.6 **Test:** duplicate collection ids fail the migration before any artifact is linked,
      exercised with a **synthetic** pair — two cards differing only in age. The real eight are
      already unique under `{species}-{mode}-{root_type}`, so a test over live data asserts nothing
      about the guard. D4 drops age from the name, which is precisely what makes this collidable.
      **Implemented in 5.4** — this is the one §4 test whose implementer was in neither 5.4's nor
      6.7's "against" list.
- [ ] 4.7 **Test:** every card's `mode` validates against `MODE_VOCAB`, `species` against
      `LABEL_SPECIES_VOCAB`, and `root_type` against `chooser.ROOT_TYPE_VOCAB` — the model-side
      vocabulary, unchanged (D3). No card carries `seminal`.
- [ ] 4.8 **Test then implement:** the single-species check runs as code on every invocation. A
      collection whose mapping or blob-derived species set has more than one member is rejected by
      name; no card is stamped. §2.3 is the human pass that produced the record, this is what stops
      it from being a one-time inspection nobody repeats.
- [ ] 4.9 **Test then implement:** where the committed mapping and the blob both carry a value
      (`node_count`, `n_frames`, species), disagreement fails naming the collection and the field.
      Neither source silently wins.
- [ ] 4.10 **Test:** no card carries a fabricated value for a field §2 reported as unrecovered — it
      is either `None` or the card is not constructible, never a placeholder, sentinel, or zero.

## 5. Registry migration (publish + link)

Every task here is offline. `label_publish.py` takes an injected `api` defaulting to `None` and
imports `wandb` only on the network path — the seam `registry/publish.py` already uses
(`publish.py:28-29,86` in `publish_card`, `:163-168,208-209` in `seed_registry`, and
`:275-278,302-303` in `verify_registry`). Without it these become live-network tests with no marker
to skip them, which is how #53's unrun-integration problem starts.

- [ ] 5.1 **Test:** linking an existing artifact version into a new collection preserves the
      artifact digest (no re-publish), driven through an injected fake `api`.
- [ ] 5.2 **Test:** the old collection's artifact remains resolvable (not orphaned).
- [ ] 5.3 **Test:** the new collection carries the `production` alias and `LabelCard` metadata;
      the old one does not carry `production`.
- [ ] 5.4 Implement `label_publish.py` against 5.1–5.3 **and 4.6**: create normalized collections,
      link existing artifact versions, attach `LabelCard` metadata, and set `production` on the new
      collection only. The 4.6 duplicate-id guard runs **first**, before any collection is created
      or artifact linked — the model side's precedent is `registry/publish.py:196-206` at the top of
      `seed_registry()`, which builds `{collection_id: [owner, ...]}` and raises naming the
      offending **cards**, not just the collapsed id. Signature takes `api=None` and imports
      `wandb` lazily.
- [ ] 5.5 **Test:** re-running skips collections already carrying `production`, and reports them
      as skipped.
- [ ] 5.6 **Test:** `--force` re-links and re-points the alias on an already-migrated collection.
      Spec'd in *Idempotent Label Registry Migration*; this is the task that was missing.
- [ ] 5.7 **Test:** a run that fails partway leaves migrated collections aliased, un-migrated ones
      untouched and still resolvable under their old names, and a re-run completes only the
      remainder.
- [ ] 5.8 Implement idempotency, `--force`, and resumability against 5.5–5.7.

## 6. CLI

Tests precede the implementation they cover.

- [ ] 6.1 **Test:** `seed-label-registry` dry run prints planned collections and per-card metadata,
      and makes no wandb call (assert on the injected `api` never being constructed).
- [ ] 6.2 **Test:** `--only` filters to a single collection; an unknown `--only` value fails fast
      naming it.
- [ ] 6.3 **Test:** `--verify` reports every expected collection and exits non-zero if any lacks
      the `production` alias, against an injected fake registry.
- [ ] 6.4 **Test:** credential guard — `--execute` and `--verify` require a resolvable wandb
      credential (same contract as model `seed-registry`).
- [ ] 6.5 **Test:** `--execute` confirms the target before doing anything, and `--yes` skips the
      prompt. Declining exits non-zero with no collection created, no artifact linked and no wandb
      run minted. This is the parity `seed-registry` actually has and the spec claims: the flag is
      `cli.py:56`, the prompt `cli.py:179-183` (`click.confirm(..., abort=True)`, after the
      credential check so it fails fast first), and the decline test
      `tests/test_registry_cli.py:104-115`. It matters more here than there — these collections are
      the ones D4 treats as uncreatable twice.
- [ ] 6.6 **Test:** `--force` is accepted and reaches `label_publish` (CLI wiring for 5.6).
- [ ] 6.7 Implement `seed-label-registry` against 6.1–6.6: dry-run by default, `--execute`,
      `--only`, `--verify`, `--force`, `--yes`.
- [ ] 6.8 Update `docs/CHANGELOG.md` under `[Unreleased]`.
- [ ] 6.9 Full suite unfiltered **with the coverage gate CI enforces** — `pytest
      --cov=src/sleap_roots_training --cov-fail-under=95` (`ci.yml:89`), run without the
      `-m "not integration"` filter — plus `black --check`, `ruff check`, and
      `openspec validate --all --strict`. Two new modules whose network paths are deliberately
      unexercised are the likeliest place to breach 95%.

## 7. Live migration — gated, and a separate PR after this one merges

Runs against the live registry **after** the code PR merges, as its own PR with no CI, run by hand
with a resolvable credential and explicit sign-off. Precedent: `update-model-card-selectors`' §6,
headed "gated, and a separate PR after this change archives", with its rollback prep as task 6.0.
That precedent also shows these tasks get **ticked** in the migration PR before `openspec archive`
runs.

- [ ] 7.0 **Rollback prep, before touching anything.** (a) Snapshot the current 8 collection →
      aliased artifact **version** mappings to a file committed with the migration PR. (b) The
      rollback for an additive link-and-alias migration is to **remove `production` from the newly
      created collections**, not to re-point an old alias — rehearse *that* on the canary. Prefer
      `Artifact.unlink()`, which raises unless the object really is the link; if using
      `aliases = [...]; .save()`, first fetch the **link** and assert `artifact.is_link`, because
      `save()` on the *source* artifact aliases the source collection, reports success, and leaves
      `production` live where you meant to remove it. (c) Rehearse the un-retirement too: restore
      `production` from the 7.0(a) snapshot on the recorded source version.
- [ ] 7.1 Dry-run review: print all eight planned collections and check each against §2.2's
      committed mapping by hand. This is the gate for a name that cannot be un-created — W&B
      collections can be neither renamed nor deleted.
- [ ] 7.2 Canary: migrate `arabidopsis-cylinder-primary` with `--only`, verify a consumer reads it.
      Chosen because it depends on neither D5's split nor D7's outcome (see D6).
- [ ] 7.3 Full migration: `--execute` for the remaining seven. Re-run `--verify` immediately before
      this to confirm nothing else wrote since 7.2.
- [ ] 7.4 Run `--verify` against the live registry; non-zero exit on any missing alias.
- [ ] 7.5 Worked example: join one model to its training labels via the two registries. Runs
      against **live post-migration data**, which is why it sits here and not in §6 — the fixture
      version would assert the join logic, not that the migration produced a joinable registry.
- [ ] 7.6 Update `docs/roadmap.md` for #11 completion. Three distinct edits, not one: Tier 2's
      tracking line (`roadmap.md:221`), Tier 2.2's depends-on note (`:284`), and Tier 2.7's
      label-metadata dependency (`:326,:329`). Plus a dated revision-log entry at the bottom and
      the `**Last revised:**` date at the top, per the file's own convention.
