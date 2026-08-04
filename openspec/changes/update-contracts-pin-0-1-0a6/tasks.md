## 0. Gate

- [x] 0.1 Confirm `sleap-roots-contracts==0.1.0a6` is on PyPI and review the `a3 → a6` delta for
      changes to already-released contracts (design.md records the review — only `ModelCard`
      changed).
- [x] 0.2 Confirm every `mode` in the committed `model_selection.yaml` is in the contract's `Mode`
      vocabulary — if not, this is a migration, not an adoption, and stops here. (7 rows:
      `cylinder` ×6, `multiplant cylinder` ×1 — both in vocabulary.)
- [x] 0.3 Enumerate **every** consumer of `MODE_VOCAB`, not just the loader. Found two:
      `chooser.load_selection_matrix` (repo-owned matrix data) and `config._validate_experiment`
      (hand-written user config, added by Tier 1 / #20). Recorded in design.md.

## 1. Pin

- [x] 1.1 `uv add "sleap-roots-contracts==0.1.0a6"` (exact pin retained — design.md).
- [x] 1.2 Regenerate the lockfile; confirm `uv lock --check` passes.
- [x] 1.3 `uv run python -c "import sleap_roots_contracts as c; print(c.__version__)"` reports
      `0.1.0a6`, and `from sleap_roots_contracts import Mode` resolves to
      `('cylinder', 'multiplant cylinder', 'plate')`.

## 2. Collapse the mode vocabulary

- [x] 2.1 In `registry/chooser.py`, derive `MODE_VOCAB` from `sleap_roots_contracts.Mode` via
      `get_args`, keeping the `MODE_VOCAB` name and the loader's row-numbered error message.
- [x] 2.2 Update the module docstring/comment so the source of truth is stated where the constant
      lives, not only in the spec.
- [x] 2.3 Leave `SPECIES_VOCAB` local and say why in the same place.
- [x] 2.4 ~~No change to `config.py`~~ — **superseded, see 2.5.** As originally written this said
      the vocabulary is set-identical so `validate` behavior is unchanged and no code was needed.
      The first half is still true and is the basis of the no-behavior-change claim. The second
      half stopped being true in `38dc152` and was not corrected here at the time.
- [x] 2.5 `config.py` **did** change, in review: `_check_vocab` gained a `difflib` "did you mean"
      hint on an out-of-vocabulary value, and later an `ascii()` fallback so a homoglyph paste is
      not rendered identically to its own suggestion. One of **two** user-visible behavior changes
      here (the other is 2.6) — it arrived from a review suggestion after this file was written,
      which is exactly how it slipped both the TDD gate and the spec-delta gate. Now covered by
      `test_near_miss_mode_gets_a_did_you_mean_hint` (+ a far-miss negative control and a homoglyph
      case); the hint block was previously deletable with the whole suite still green.
      The similarity floor is a named `_HINT_CUTOFF = 0.5`, not `difflib`'s implicit `0.6`, because
      `cyl` scores 0.545 against `cylinder` — and `cyl` is the shorthand this collapse exists to
      close, so the default cutoff gave it no hint at all.
      **Scope:** `_check_vocab` is shared, so this changed the error text for `experiment.species`
      and `experiment.root_type` too, not only `experiment.mode` — wider than this change's stated
      subject. Recorded as a decision with its rationale in `design.md`, and pinned by
      `test_the_hint_covers_species_and_root_type_too`.
- [x] 2.6 `cli.py`: `seed-registry` wraps `ValueError`/`FileNotFoundError` from **both** the matrix
      loader and `cards.expand_rows_to_cards` into a `click.ClickException`, matching what the
      `resolve_all` step in the same function already did. The loader's row-numbered message is
      what the spec promises operators, but unwrapped it reached them as a raw traceback — newly
      load-bearing, since a future upstream narrowing of `Mode` hands exactly that error to every
      operator running `seed-registry`. The second user-visible behavior change here, and the
      reason the spec delta carries a third MODIFIED requirement (**Registry Seeding CLI with
      Confirmed Execution**) rather than only the two vocabulary ones.
- [x] 2.7 The import-time guard in `chooser.py` is a **new failure mode**, not covered by 2.1's
      "derive via `get_args`" wording: `chooser` now raises `RuntimeError` at import if the derived
      vocabulary is empty *or contains a non-string*. Both halves are needed — an emptiness-only
      guard (the first attempt) misses `Annotated[Literal[...], Field(...)]`, `Optional[Literal]`
      and `Union[Literal, Literal]`, and the `Annotated` form is the idiomatic one for a
      pydantic-first contracts package. Rationale and the full shape table are in `design.md`;
      discrimination is tested by 3.6. Not user-visible today — it can only fire on a future
      upstream reshape — which is why it is absent from `docs/CHANGELOG.md` on purpose.

## 3. Tests

Note: there is no RED step **for the bump itself** — it changes no behavior in this repo
(design.md), so these are regression guards on an invariant that previously held only because two
lists agreed, not a red/green pair.

**Scope of that claim, corrected after review.** As written it silently covered every later commit
too, and by `38dc152` that was no longer true: the import-time guard (2.7) is a new failure mode,
the `difflib` hint (2.5) is new user-visible message content, and the CLI error packaging (2.6) is
a new user-visible outcome — all three were shipped with their tests absent. The argument was sound when written and then applied to commits where it had stopped being
sound. The tests that close those two gaps (3.6, 3.7) were written afterwards, so they are honestly
regression guards rather than TDD — but both were verified by fault injection to fail against the
code as it stood before them, which is the property RED was there to establish.

- [x] 3.1 `tests/test_registry_chooser.py`: assert `MODE_VOCAB` is the contract vocabulary
      **unforked**, plus a mirror asserting `SPECIES_VOCAB` stays local. Follows the existing
      `test_root_type_vocab_mirrors_cards_slots` drift-guard idiom.
      **Corrected after review.** The original note claimed the planned test ("every mode in the
      committed matrix is contract-valid") was *unwritable as a failing test*, and attributed the
      scenario to `test_load_selection_matrix_has_seven_rows`. Both were wrong in the same way.
      That test asserts row counts, checksums, and model ids — it contains no assertion about mode
      validity, and satisfies the scenario only as a side effect (a `Mode` narrowing breaks the
      loader, which breaks it as collateral damage). And the test *is* writable: it is vacuous only
      if it reads rows back through `load_selection_matrix`, which already rejects an
      out-of-vocabulary mode. `test_every_committed_matrix_mode_is_contract_valid` parses the
      committed YAML directly, which checks the data rather than the guard, and so fails if a bad
      row is committed and the loader's check is ever loosened.
      Also written, guarding the failure that *can* happen: a human re-forking the vocabulary
      locally (`frozenset(get_args(Mode)) | {"cyl"}`) to let a stray value through.
      **Hardened after review:** `test_mode_vocab_is_the_contract_vocabulary_unforked` re-derived
      the vocabulary exactly as production does, so an upstream `Literal` → `Enum` change degraded
      both sides to `frozenset()` and the assertion still passed. It now carries an independent
      literal witness, `chooser` raises at import on an empty vocabulary, and
      `test_species_vocab_stays_local` asserts on `ModelCard.model_fields["species"].annotation`
      rather than probing for a top-level `Species` symbol the realistic drift path would not add.
- [x] 3.2 `tests/test_registry_cards.py`: parametrized over every mode the loader accepts — a card's
      metadata validates against the real `ModelCard` and round-trips `mode` unchanged. Verified
      non-vacuous: the contract rejects `multiplant-cylinder`, `Cylinder`, `cyl`, and `" cylinder"`,
      so a slug leaking out of `card_to_metadata` fails this test.
- [x] 3.3 `tests/test_config.py`: lock exact matching of `experiment.mode` (`Cylinder`, `CYLINDER`,
      leading/trailing space, `multiplant-cylinder` all rejected), so a later normalization has to
      argue with a test first. Sits with the existing vocab-drift guards.
- [x] 3.4 Confirm the existing off-vocabulary rejection test (`mode: teacup`) still fails at the
      loader with the row-numbered error, not at `ModelCard`.
- [x] 3.5 Confirm `tests/test_registry_lineage.py` still passes — it asserts the recorded contract
      version against `importlib.metadata`, so it follows the pin with no edit.
- [x] 3.6 **Round 2.** Test the import guard itself, which was previously the one statement in
      `chooser.py` that had never executed — coverage reported 98% for the file, against a "100%"
      that appeared in the PR description and nowhere in this directory. Imports `chooser`
      in a subprocess against a stub `sleap_roots_contracts` on `PYTHONPATH`, parametrized over the
      five reshapes `get_args()` destructures without raising, plus a plain-`Literal` negative
      control so the guard has to *discriminate* rather than merely fail. Writing it immediately
      surfaced that the guard was still too weak — see 3.8.
      *Coverage caveat:* the guard executes in a subprocess, so `coverage` still reports
      `chooser.py` at 98% with that line unattributed. The line is genuinely exercised; the tool
      cannot see across the process boundary without `COVERAGE_PROCESS_START` plumbing that is not
      worth adding to CI for one line. Stated rather than papered over with a `# pragma: no cover`.
- [x] 3.7 **Round 2.** Lock the `difflib` hint (2.5) — a near-miss case per vocabulary value, a
      far-miss negative control (`teacup` gets no hint), and the homoglyph rendering. Verified by
      mutation: deleting the hint block previously left the suite green, and now fails 7 tests.
- [x] 3.8 **Round 2.** `tests/test_registry_cards.py` parametrized over `sorted(MODE_VOCAB)`, so an
      upstream *narrowing* silently shrank the suite instead of failing it — drop `plate` and the
      `[plate]` case just stops existing. Now parametrized over a spelled-out `_EXPECTED_MODES`
      with a cardinality check against the live set, so a narrowing is a failure rather than an
      absence. The `plate` literal in `test_registry_chooser.py` is labelled as load-bearing for
      the same reason: no authoring surface uses `plate`, so that assertion is its only coverage.
- [x] 3.9 **Round 2.** `test_every_committed_matrix_card_validates_against_the_real_modelcard` —
      the spec's `ModelCard` scenario asserted on the real committed matrix (7 rows → 13 cards)
      rather than only on synthetic cards. Nothing in `src/` ever constructs a `ModelCard`
      (`publish.py` writes `card_to_metadata` straight into `wandb.Artifact`), so tests on this
      side of the wire are the only place the contract's validation runs at all.
- [x] 3.10 **Round 2.** `tests/test_training_docs.py`'s mode guard now parses YAML-tagged fences
      with `yaml.safe_load` instead of splitting on `:`. It previously went RED on *correct* docs
      edits — quoting the value (`mode: "multiplant cylinder"`, and that is the one multi-word
      mode, so quoting it is what a YAML style guide advises), nesting, or a `python`/`bash` fence
      containing a `mode:`-ish line — and blamed the contract for a bug in the test. Verified: all
      three previously-failing correct edits now pass, and `mode: cyl` still fails.

## 4. Spec + docs

- [x] 4.1 Author the `model-registry` delta (2 requirements MODIFIED). **Not applied to
      `openspec/specs/` here** — per the OpenSpec workflow, `specs/` is updated by
      `openspec archive` in the follow-up archive PR, matching this repo's `#18`/`#19` precedent.
- [x] 4.2 `docs/CHANGELOG.md` Unreleased: the pin bump, the vocabulary collapse, the `config.py`
      surface, and the exact-matching decision.
- [x] 4.3 `openspec validate update-contracts-pin-0-1-0a6 --strict` passes.

## 5. Verify

- [x] 5.1 Run CI locally: `black --check`, `ruff check`, full `pytest`.
- [x] 5.2 Open the PR; note that it unblocks #10 (`add-label-registry`).
- [x] 5.3 **Round 2.** Re-measure the import cost as a true A/B rather than as a total. The figure
      recorded in `design.md` and `docs/CHANGELOG.md` (~183 ms) was `chooser`'s *whole* import cost,
      not what this change adds — `chooser` already imported `omegaconf`, and the two share `yaml`,
      `importlib.metadata` and `re`. Corrected to the measured marginal +72–87 ms, along with the
      claim that it is "one-time": `cli.py` imports `chooser` at module scope, so `--help`,
      `--version` and every TAB completion pay it. The stated *reason* for not deferring was also
      false (a PEP 562 `__getattr__` keeps `MODE_VOCAB` a public constant); replaced with the real
      trade-off, which is that deferring turns the 2.1 guard into a first-use error.
- [x] 5.4 **Round 2.** Reconcile the change record with the shipped diff — `proposal.md`'s affected
      -code list and its "no code change in `config.py`" note, `tasks.md` 2.4 and the §3 TDD claim,
      and the PR description. This directory becomes the durable record on `openspec archive`, and
      `openspec validate --strict` is not run in CI, so review is the only gate on this drift.

## 6. Deferred (not this change)

- [ ] 6.1 Normalizing a hand-typed `experiment.mode` (lowercase + collapse whitespace, canonical
      value written back) is a `validate`-CLI behavior change belonging to the config capability,
      whose spec is still unarchived in `add-config-schema`. Decided against for now — see the
      exact-matching decision in design.md.
