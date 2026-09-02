# Tasks

**TDD.** Every group is ordered tests-first and worked top-down. Each `(RED)` task names
the behaviour it pins and is expected to fail on `ImportError` before its `(GREEN)`
partner exists, per `.claude/commands/tdd.md` Phase 2.

**CI criterion.** `(RED)` commits are red by construction. The bar is green at every
`(GREEN)` boundary and at the PR head — not after every commit.

**Approval gate.** No implementation task starts until the proposal is approved.

## 1. Path resolution and digest verification

- [ ] 1.0 **Confirm red:** run the new test file and assert every test fails on
      `ImportError`, not on a typo.
- [ ] 1.1 **(RED)** Test the recorded-path→share mapping over a table of all three
      observed prefixes (mapped drive letter, UNC share path, share drive letter), plus an
      unrecognized prefix that must be reported rather than silently missed.
- [ ] 1.2 **(RED)** Test that a digest mismatch excludes the collection, using a
      **same-size** file with different content — so a size comparison cannot pass this
      test.
- [ ] 1.3 **(RED)** Test that one collection failing verification does not prevent the
      others being inventoried.
- [ ] 1.4 **(GREEN)** Implement `inventory/resolve.py`: prefix mapping, digest comparison,
      per-collection isolation.

## 2. Reading the labels file

- [ ] 2.1 **(RED)** Test that skeleton name, node names, node count, frame count and
      instance count are read from a labels file, **round-tripped through a synthetic
      `.slp` written with `sio.save_slp` and loaded with `sio.load_slp`** — not from an
      in-memory `Labels` object, so the real loader is exercised.
- [ ] 2.2 **(RED)** Test that the skeleton name is reported as the file's literal value,
      including an auto-generated one, with no substitution of a canonical name.
- [ ] 2.3 **(RED)** Test video-path parsing to `(qr_code, day, date, scanner)` over the
      shapes present in the corpus, including the scanner-suffixed directory form, and a
      malformed path that must be reported rather than parsed into wrong fields.
- [ ] 2.4 **(GREEN)** Implement `inventory/read.py`.

## 3. Bloom resolution

- [ ] 3.1 **(RED)** Test that the Bloom client is **injected**, and that a run against a
      recording double invokes only read operations — no write, publish, alias, ingest, or
      delete. Mirrors `registry/publish.py`'s `api=None` seam.
- [ ] 3.2 **(RED)** Test the QR→scan lookup returns `species_name`, `plant_id`,
      `plant_age_days`, `experiment_id` for a known code, against a fake whose column names
      match `bloomctl`'s `CSV_COLUMNS` exactly.
- [ ] 3.3 **(RED)** Test that a QR code absent from Bloom yields `unresolved` and does not
      raise.
- [ ] 3.4 **(GREEN)** Implement `inventory/bloom.py` with the injected-client seam.

## 4. Reconciliation

- [ ] 4.1 **(RED)** Test the three-state classification: agreed, disagreed (carrying both
      values), unresolved.
- [ ] 4.2 **(RED)** Test that species is taken from Bloom even when the collection name and
      the containing folder name both say otherwise, and that the conflict is recorded.
- [ ] 4.3 **(RED)** Test that aggregates exclude disagreed and unresolved rows — with a
      fixture where including them would change the answer, so the test discriminates.
- [ ] 4.4 **(RED)** Test scan/plant counting: one plant at two ages is 1 plant / 2 scans;
      one plant twice on one day from two scanners is 1 plant / 2 scans.
- [ ] 4.5 **(RED)** Test that a computed scan count below the plant count is reported as a
      defect and the aggregate is not emitted.
- [ ] 4.6 **(RED)** Test that a collection with any exception gates before final emission,
      and that a clean collection emits without a gate.
- [ ] 4.7 **(GREEN)** Implement `inventory/reconcile.py`.

## 5. Discovery and the skeleton diff

- [ ] 5.1 **(RED)** Test that a folder with a top-level labels file is inventoried, one
      without is skipped **with a reason**, and split files beneath a collection are not
      treated as collections.
- [ ] 5.2 **(RED)** Test that the reported frame count is the top-level file's, not a
      split's — using a fixture whose split count differs, so the test discriminates.
- [ ] 5.3 **(RED)** Test the skeleton diff's three outcomes (verifies / contradicts / no
      row) and that no value is written back to `skeletons.yaml`.
- [ ] 5.4 **(RED)** Test that two collections differing only by capture mode with different
      node counts are reported as a **keying gap**, not as a contradiction on either row.
- [ ] 5.5 **(GREEN)** Implement discovery and `inventory/skeleton_diff.py`.

## 6. Emission and idempotence

- [ ] 6.1 **(RED)** Test that per-scan CSV columns are grouped by source and that
      Bloom-derived column names equal `bloomctl`'s `CSV_COLUMNS`, asserted against that
      list rather than a transcribed copy.
- [ ] 6.2 **(RED)** Test that the aggregate YAML carries per-field confidence and the
      reconciliation tally.
- [ ] 6.3 **(RED)** Test that the images-embedded value describes the version a consumer
      receives, on a two-version collection where the two answers differ.
- [ ] 6.4 **(RED)** Test idempotence: two runs over unchanged inputs are byte-identical,
      and adding a collection leaves the others' entries byte-identical.
- [ ] 6.5 **(GREEN)** Implement `inventory/emit.py`.

## 7. CLI

- [ ] 7.1 **(RED)** Test `inventory labels --out` end to end against injected registry and
      Bloom clients, asserting the three artifacts are written and no external write occurs.
- [ ] 7.2 **(RED)** Test that a missing share, absent `WANDB_API_KEY`, or absent Bloom
      credentials degrades per-source with an actionable message naming what is missing —
      rather than failing the whole run or emitting a partial artifact silently.
- [ ] 7.3 **(GREEN)** Implement the `inventory` command group in `cli.py`.

## 8. Docs

- [ ] 8.1 `docs/inventory.md`: how to re-run, what each artifact means, and what the three
      reconciliation states imply for a reader.
- [ ] 8.2 `docs/CHANGELOG.md`: entry under `[Unreleased]`.
- [ ] 8.3 State in `docs/inventory.md` that the capability writes nothing to the registry
      or Bloom, so the property survives separately from this proposal once archived.

## 9. Gate

- [ ] 9.1 Full suite unfiltered, `uv run black --check src tests`,
      `uv run ruff check src tests`, `uv run pytest --cov=src/sleap_roots_training
      --cov-fail-under=95`, and `openspec validate add-label-corpus-inventory --strict`.
- [ ] 9.2 Reconcile implementation against this proposal per `/new-feature` step 9: verify
      the round-trip test really calls `sio.save_slp`/`sio.load_slp`, that the Bloom column
      assertion reads `bloomctl`'s list rather than a copy, and that every named module
      exists as specified. Record any deviation with a `### Why N instead of M?` note.

## 10. First run

- [ ] 10.1 Run against the real corpus with a second reader on `inventory/bloom.py` before
      it touches production, per the design's risk note.
- [ ] 10.2 Adjudicate the gated exceptions with eberrigan; commit the resulting artifacts.
- [ ] 10.3 Post the aggregate YAML to `#49` as the input to its §2, noting which of its
      tasks it retires.
