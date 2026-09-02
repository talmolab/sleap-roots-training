# Tasks

**TDD, as separate commits.** `(RED)` lands the tests and is **expected to be red**;
`(GREEN)` lands the implementation that turns it green. Subjects use `test(RED): …` /
`feat(GREEN): …`. Confirm each RED fails for the right reason — `ImportError`,
`AttributeError` or `AssertionError`, not an unexpected error, per `.claude/commands/tdd.md`
Phase 2.

This requires amending `openspec/project.md`, and **two other documents that restate the same
rule** — task 0.4. Note honestly what the convention buys: because PRs here are
squash-merged, the pair collapses on merge, so the labels serve *branch* review, not `main`'s
history.

**Push discipline.** CI evaluates the head of a push, so push each RED+GREEN pair in one
`git push`. A RED pushed alone against an open PR produces a genuine red run — permitted, but
noisy.

**No CI on the proposal commit.** `openspec/**` is outside `ci.yml`'s paths filter — absence
of signal, not green. `README.md` is outside it too.

**Approval gate.** No implementation task starts until the proposal is approved.

## 0. Before any code

- [ ] 0.1 **Rebase onto `origin/main`.** The branch is 3 behind, including the breaking
      registry reshape and the root-type vocabulary collapse. Re-verify against the rebased
      tree that `bloomctl` resolves against the `0.1.0a8` contracts pin — the earlier
      resolution was measured against the stale `0.1.0a6`.
- [ ] 0.2 Add `bloomctl` as a dependency and re-lock **in the same commit** — `ci.yml` runs
      `uv sync --locked`, which fails on a stale `uv.lock`. Pin it the way every other
      dependency here is pinned (a lower bound with an upper cap), not bare.
- [ ] 0.3 Confirm `#48` has merged, or place the `inventory` group before the `labeling`
      group in `cli.py` rather than at end of file. `#48`'s final hunk is an EOF append.
- [ ] 0.4 Amend the green-every-commit rule in **all three places it is written**:
      `openspec/project.md`'s Testing Strategy; `.claude/commands/tdd.md` Phase 6, which
      stages implementation and tests in one commit; and `.claude/commands/review-pr.md`,
      which restates the rule verbatim *inside the TDD-reviewer prompt* and would otherwise
      have the review tooling flag every RED commit the new convention permits. Keep
      `black --check` and `ruff check` green on every commit. Describe the pattern as
      **adopted from** a trial in `sleap-roots-contracts` — one landed pair of 57 commits,
      using bare `RED:`/`GREEN:`; the `test(RED)`/`feat(GREEN)` form is on an unmerged branch
      there, and that repo's own `project.md` says "red → green → commit". Do not claim it is
      established practice. **Its own commit**, since every future change inherits it.
- [ ] 0.5 **(GREEN)** Define the four closed vocabularies as constants in a leaf
      `inventory/vocab.py`, importable without the registry or scan-metadata clients:
      per-scan status, unresolved reason, per-field confidence, collection outcome. This is
      first because groups 1-4 assert vocabulary members, and defining it later means three
      modules carry local literals and a refactor.

## 1. Resolution, digest verification, containment

- [ ] 1.1 **(RED)** Test the recorded-path→share mapping over every prefix the corpus uses
      plus the drive-relative form, with an unrecognized prefix reported. Assert identical
      results under POSIX and Windows semantics; `labeling/copy_images.py`'s docstring records
      this scar twice. **Write the prefix table into the spec as it is chosen** — it is a
      value the committed artifacts carry forever and it currently exists only in the
      background design doc.
- [ ] 1.2 **(RED)** Test that the digest compared is the **manifest entry's** per-file
      base64 MD5, not the artifact-level digest, and that a **same-size** file with different
      content is excluded.
- [ ] 1.3 **(RED)** Test that verification invokes no download: the injected registry double
      records zero `download` / `checkout` / `file` calls.
- [ ] 1.4 **(RED)** Test that a directory is refused and an I/O error is reported as
      unreadable, distinctly from a mismatch.
- [ ] 1.5 **(RED)** Test that the registry client is **injected** and the double is
      **strict** — raising on any attribute outside an enumerated read allowlist. Note
      `tests/test_registry_cli.py`'s `_no_wandb` is two `monkeypatch.setattr(..., boom)`
      calls, not an allowlisted double, so this harness is new work.
- [ ] 1.6 **(RED)** Test with `isolate_wandb_env` that the run works with `WANDB_API_KEY` /
      `WANDB_ENTITY` / `NETRC` cleared and `HOME` repointed.
- [ ] 1.7 **(RED)** Test that a collection with **no registry counterpart** is inventoried,
      reported unregistered with share-only fields, distinctly from a digest mismatch.
- [ ] 1.8 **(RED)** Test that two collections resolving to the same share file are both
      reported, naming the shared path.
- [ ] 1.9 **(RED)** Test containment: a collection failing verification, and a collection
      whose aggregate is withheld, each leave the others emitted.
- [ ] 1.10 **(RED)** Test that an absent registry or absent share exits naming the missing
      source and emits nothing.
- [ ] 1.11 **(RED)** Test provenance is read from the original version and images-embedded
      from the repair, on a two-version collection where the two answers differ; and that a
      single-version collection reads both from that version. **Name the mechanism that
      enumerates versions** — it is registry-client work, not labels-file work.
- [ ] 1.12 **(GREEN)** Implement `inventory/resolve.py`.

## 2. Reading the labels file

- [ ] 2.1 **(RED)** Test that skeleton name, node names and node count are read from a labels
      file **round-tripped through a synthetic `.slp` written with `sio.save_slp` and loaded
      with `sio.load_slp`**, using `open_videos=False` — a host without the share cannot
      resolve video backends, and `scripts/clean_pkg.py` documents that resolving them raises.
- [ ] 2.2 **(RED)** Test the counts distinguish user labels from predictions: assert
      `n_user_frames`, `n_user_instances` and `n_pred_instances` are reported separately, on
      a fixture carrying predicted instances and at least one frame with no instance.
      `tests/test_labeling_package.py` asserts such empty frames really occur.
- [ ] 2.3 **(RED)** Test the three recorded-path shapes: a **referenced** path yielding code,
      age, date and device; an **embedded** package whose code comes from the embedded source
      rather than the package's own filename, including the list form and the deliberately
      cleared form; and a **generated** package whose filename is a list carrying code and age
      but no date, which must resolve rather than be withheld.
- [ ] 2.4 **(RED)** Test that a file carrying more than one skeleton is reported as such —
      `Labels.skeleton` raises rather than choosing, and a scalar cannot describe it.
- [ ] 2.5 **(RED)** Test that a labels file with zero videos, and one with a video carrying
      no labeled frames, each yield a recorded entry rather than a crash or a silent skip.
- [ ] 2.6 **(GREEN)** Implement `inventory/read.py`.

## 3. Bloom resolution

- [ ] 3.1 **(RED)** Test that only `bloomctl`'s documented **read** entry points are called,
      that the client is injected, and that the double is strict.
- [ ] 3.2 **(RED)** Test at the transport level that every data-plane request used the read
      method, and that a request using any other method fails the run. The session exchange
      is the permitted exception.
- [ ] 3.3 **(RED)** Test that no module in `inventory/` imports or references `bloomctl`'s
      ingest surface — an import-level assertion, so a future edit cannot quietly add one.
- [ ] 3.4 **(RED)** Test the scan lookup returns species, plant identity, age and experiment
      for a known code, against a fake speaking the **row keys** while the emitter uses the
      **export column names** — they differ for the identifying code, and conflating them
      breaks the join.
- [ ] 3.5 **(RED)** Test batching via `bloomctl`'s helper: a collection larger than one
      filter still resolves every scan.
- [ ] 3.6 **(RED)** Test that a code absent from Bloom yields `unresolved` with the
      no-record reason, distinct from the malformed-path reason.
- [ ] 3.7 **(RED)** Test that loaded credentials appear in no repr, log line, exception
      message or emitted artifact.
- [ ] 3.8 **(RED)** Test the **plate** read path resolves a plate collection through
      `bloomctl`'s plate surface rather than the cylinder view, and that a plate collection's
      age epoch is recorded as its own — the two epochs differ upstream.
- [ ] 3.9 **(GREEN)** Implement `inventory/bloom.py` over `bloomctl`'s read surface, keeping
      credential loading and client construction in one thin adapter.

## 4. Reconciliation

- [ ] 4.1 **(RED)** Test the three-state classification with the reason recorded on every
      unresolved row.
- [ ] 4.2 **(RED)** Test that an **unparseable or ambiguous date** yields `unresolved` for
      that reason and never `disagreed` — the recorded form is ambiguous between day-first
      and month-first and may carry a two-digit year, and a parse failure reported as a
      disagreement would withhold a collection on a formatting convention.
- [ ] 4.3 **(RED)** Test that species comes from Bloom when the name says otherwise, and that
      it is normalised by the contract library's own species rule rather than compared raw.
- [ ] 4.4 **(RED)** Test that a collection resolving to more than one species is reported as
      a **defect blocking its card**, not as a species value, and that the
      experiment-to-species mapping is emitted as the evidence.
- [ ] 4.5 **(RED)** Test scan/plant counting from Bloom plant identity, not the filename code.
- [ ] 4.6 **(RED)** Test that a scan count below the plant count is reported against that
      collection only.
- [ ] 4.7 **(RED)** Test that the age window is emitted as an **observed** range labelled as
      such, carrying its epoch and the observed age set — not as an approved window, which is
      what the sibling contract's field means.
- [ ] 4.8 **(GREEN)** Implement `inventory/reconcile.py`.

## 5. Discovery and the skeleton diff

- [ ] 5.1 **(RED)** Test that the walk root is a parameter, by walking a `tmp_path` tree with
      no share present; that a folder with a top-level labels file is inventoried and one
      without is skipped with a reason; and that discovery does not ascend above the root.
- [ ] 5.2 **(RED)** Test that splits are not collections and the reported frame count is the
      top-level file's, with a fixture whose split count differs.
- [ ] 5.3 **(RED)** Test the **sibling-selection rule** where a folder holds more than one
      candidate labels file — versioned siblings are the expected case — and that the
      unselected files are recorded. **Write the chosen rule into the spec.**
- [ ] 5.4 **(RED)** Test the diff's four outcomes and that nothing is written back.
- [ ] 5.5 **(RED)** Test that root type and mode, where name-derived to select a row, are
      used for selection only and appear in no emitted evidence.
- [ ] 5.6 **(RED)** Test that a mode-dependent node count is a **keying gap**, not a
      contradiction on either row.
- [ ] 5.7 **(GREEN)** Implement `inventory/discover.py` and `inventory/skeleton_diff.py`.

## 6. Redaction, emission, determinism

- [ ] 6.1 **(RED)** Test that redaction is **structural**: a user segment appearing in no
      enumerated substitution is still redacted, and any network-path host segment is
      redacted. **Choose and record the user-directory marker set** — it must cover the
      temp-directory shape a repair version's recorded path takes.
- [ ] 6.2 **(RED)** Test the rule still covers `scripts/pull_tf_reference.py`'s `_REDACTIONS`
      as a floor, loading that script **by path** as `tests/test_scripts.py` does — `scripts/`
      has no `__init__.py`.
- [ ] 6.3 **(RED)** Test that person-identifying fields are absent while genotype, accession
      and experiment name are present — approved for the public repo (eberrigan, 2026-09-02).
- [ ] 6.4 **(RED)** Test that Bloom-derived column names come from `bloomctl`'s `CSV_COLUMNS`
      **by import**, and that `species_name` / `plant_age_days` are asserted against
      `sleap_roots_contracts.params`' constants rather than string literals.
- [ ] 6.5 **(RED)** Test confidence is **per field**: file-derived facts are emitted even when
      every scan is unresolved, while reconciliation-derived fields are withheld.
- [ ] 6.6 **(RED)** Test that a collection with no surviving scans is emitted as an entry
      recording that, not as a verified zero.
- [ ] 6.7 **(RED)** Test determinism and idempotence: no timestamp, hostname or run
      identifier; a defined input-derived order; fixed line endings and rendering so output is
      byte-identical **across operating systems**; two runs identical; a new collection leaves
      others untouched. **Name the artifact filenames and the sort key.**
- [ ] 6.8 **(RED)** Test atomic emission: a raised failure leaves the previous artifact
      unchanged and removes the staging file; an orphaned staging file is overwritten.
- [ ] 6.9 **(GREEN)** Implement `inventory/redact.py` and `inventory/emit.py`.

## 7. CLI

- [ ] 7.1 **(RED)** Test `inventory labels` end to end against injected clients, passing a
      `tmp_path` walk root and applying `isolate_wandb_env`. **Name the full option surface**
      — walk root, output directory, Bloom profile, registry entity — since the doc-lock
      asserts every option is documented.
- [ ] 7.2 **(RED)** Test that an absent registry or share exits naming it and emits nothing,
      that absent Bloom emits file-derived evidence and withholds reconciled fields, and that
      exit codes are distinct and documented.
- [ ] 7.3 **(GREEN)** Implement the `inventory` group in `cli.py`, before the `labeling` group.

## 8. Docs

- [ ] 8.1 `README.md`: an "Inventorying the label corpus" section following the
      `seed-registry` pattern, plus a pointer from the doc list.
- [ ] 8.2 `docs/labeling-packages.md`: a "Reading the corpus inventory" section carrying the
      per-scan CSV's columns grouped by source and the aggregate's shape, migrated out of the
      background design doc, which does not archive with this change.
- [ ] 8.3 In the same section, define **all four** closed vocabularies by name — per-scan
      status, unresolved reason, per-field confidence, collection outcome — and state which
      statuses contribute to reconciliation-derived fields, so a reader understands why a CSV
      row count and a reported scan count differ.
- [ ] 8.4 State that species comes from Bloom and may fall outside `SPECIES_VOCAB`; that the
      age window is **observed**, not approved, and carries its epoch; and that plant count is
      distinct Bloom plant records, not a botanical plant count under multiplant modes.
- [ ] 8.5 State that the capability writes nothing and issues only reads.
- [ ] 8.6 `openspec/project.md`: extend Purpose to cover corpus inventory, and record the
      source-of-record split — W&B for label artifacts, Bloom for scan metadata.
- [ ] 8.7 `docs/roadmap.md`: place under Tier 2 and reconcile with the label inventory the
      roadmap already refers to as existing.
- [ ] 8.8 `docs/CHANGELOG.md`: entry under `[Unreleased]` → `### Added`.
- [ ] 8.9 `tests/test_inventory_docs.py`: doc-lock matching `tests/test_labeling_docs.py` —
      every documented command and option exists, every option is documented, and **all four**
      documented vocabularies equal the emitter's constants.

## 9. Gate

- [ ] 9.1 Mirror CI exactly — `uv run pytest --cov=src/sleap_roots_training
      --cov-fail-under=95 -m "not integration" tests/`, `uv run black --check
      src/sleap_roots_training tests`, `uv run ruff check src/sleap_roots_training`,
      `uv sync --locked` — plus `openspec validate add-label-corpus-inventory --strict`.
      Re-measure coverage: headroom grows with the tree, roughly `46 + 0.055·N` misses
      allowed for `N` new statements, so budget ~87-89% on the new modules and expect ~3
      uncovered statements per lazily-constructed client.
- [ ] 9.2 Run the unfiltered suite separately as a credentialed step. **Every new
      `integration` test must skip cleanly** without credentials or the share — there is no
      `addopts`, and `.claude/commands/coverage.md` runs the suite unfiltered.
- [ ] 9.3 Archive with `@fission-ai/openspec` **≥ 1.7.0** — an explicit upgrade, since the CLI
      on `PATH` is 0.13.0 — and confirm the live spec's `Purpose` is the real text, not the
      `TBD` stub. Verified by bisection: 1.5.0 and 1.6.0 clobber it; 1.7.0+ preserve it.
- [ ] 9.4 Reconcile implementation against this proposal per `/new-feature` step 9. Record any
      deviation with a `### Why N instead of M?` note.

## 10. Follow-ups — deliberately not tasks of this change

Excluded from the checklist: none can be a commit in this PR, and leaving them unchecked
would keep the change out of the archive, as it has for three other changes on `main`.

- **First production run** → a runbook section, and optionally a scheduled workflow following
  `verify-skeleton-table.yml`. If that route is taken, wire the trigger in the same PR — that
  workflow's header records a gated check nothing ever triggered.
- **A second reviewer on `inventory/bloom.py`** → a PR-description request. The read-method
  and ingest-import tests are the mechanical backstop.
- **Adjudicating the gated exceptions and committing the artifacts** → its own follow-up PR.
- **Retiring `verify-skeleton-table.yml`** → separate change. Note this capability does *not*
  fully subsume it: that check needs only W&B and works with Bloom down, so the subsumption
  claim holds only for the file-derived half.
- **Posting the aggregate to `#49`** → better as a small PR against `#49`'s branch striking
  its §2 in favour of consuming this artifact.
