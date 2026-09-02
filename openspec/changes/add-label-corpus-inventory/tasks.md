# Tasks

**TDD.** `(RED)` / `(GREEN)` label the *authoring order within a commit*, not separate
commits. Each group lands as **one commit carrying its tests and its implementation**, per
`.claude/commands/tdd.md` Phase 6 and `openspec/project.md`'s "Keep `main` green: `pytest`
must pass before every commit". Write the tests first, confirm they fail for the right
reason (`ImportError`, `AttributeError` or `AssertionError` — not an unexpected error, per
`tdd.md` Phase 2), then implement, then commit both.

**Never land a module without its tests in the same commit.** `--cov-fail-under=95` is
repo-wide, and the measured baseline is 97% (1545 statements, 39 missed) — so an
under-covered module can redden CI even when every test passes.

**No CI on the proposal commit.** `openspec/**` is outside `ci.yml`'s paths filter, so the
proposal commit produces *no checks*, which is absence of signal rather than green.

**Approval gate.** No implementation task starts until the proposal is approved.

## 0. Before any code

- [ ] 0.1 **Rebase onto `origin/main`.** The branch is behind, including the breaking
      registry reshape and the change that collapsed the root-type vocabulary into the
      contract's. Re-read this proposal's `registry/` and vocabulary claims against the
      rebased tree.
- [ ] 0.2 Add `requests` as a **direct** dependency in `pyproject.toml` and re-lock in the
      same commit (`uv lock --check` runs on every PR). Cite the `pandas is DIRECT, not
      transitive` comment already in that file as the precedent.
- [ ] 0.3 Confirm `#48` has merged, or place the `inventory` group before the `labeling`
      group in `cli.py` rather than at end of file. `#48`'s final hunk is an EOF append; two
      EOF appends conflict for whoever rebases second.

## 1. Path resolution and digest verification

- [ ] 1.1 **(RED)** Test the recorded-path→share mapping over a table of all three observed
      prefixes plus the drive-relative `D:name` form, and an unrecognized prefix that must
      be reported. Assert identical results under POSIX and Windows semantics — the repo has
      this scar already in `labeling/copy_images.py`, whose docstring records a
      `PurePosixPath`-based check that returned `False` for `C:\data\scan1` twice.
- [ ] 1.2 **(RED)** Test that the digest compared is the **manifest entry's** digest (the
      per-file base64 MD5), not the artifact-level digest, and that a **same-size** file with
      different content is excluded — so a size comparison cannot pass this test.
- [ ] 1.3 **(RED)** Test that verification invokes **no** download: assert the injected
      registry double records zero `download` / `checkout` / `file` calls.
- [ ] 1.4 **(RED)** Test that a path resolving to a **directory** is refused, and that an
      **I/O error** is reported as unreadable and *not* as a digest mismatch.
- [ ] 1.5 **(RED)** Test that the registry client is **injected**, mirroring
      `registry/publish.py`'s `api=None` seam, and that the double is **strict** — raising on
      any attribute outside an enumerated read allowlist, so a typo'd write cannot pass by
      auto-creating a mock attribute. Precedent: `tests/test_registry_cli.py`'s `_no_wandb`,
      which raises `AssertionError("unexpected wandb call")`.
- [ ] 1.6 **(RED)** Test with `isolate_wandb_env` (`tests/conftest.py`) that the run works
      with `WANDB_API_KEY` / `WANDB_ENTITY` / `NETRC` cleared and `HOME` repointed, so an
      "offline" test cannot pass by borrowing a contributor's ambient `wandb login`.
- [ ] 1.7 **(RED)** Test that a collection with **no registry counterpart** is inventoried
      and reported as **unregistered** with share-only fields, distinctly from a digest
      mismatch. This is the majority of the corpus — ~17-22 of the expected 25-30 — and the
      reason the capability exists.
- [ ] 1.8 **(RED)** Test that two collections resolving to the **same** share file are both
      reported, naming the shared path.
- [ ] 1.9 **(RED)** Test that one collection failing verification does not prevent the others.
- [ ] 1.10 **(GREEN)** Implement `inventory/resolve.py`.

## 2. Reading the labels file

- [ ] 2.1 **(RED)** Test that skeleton name, node names, node count, frame count and
      instance count are read from a labels file **round-tripped through a synthetic `.slp`
      written with `sio.save_slp` and loaded with `sio.load_slp`** — not from an in-memory
      `Labels` object, so the real loader is exercised. Precedent: `tests/conftest.py`'s
      existing `sio.save_slp(labels, str(path), embed=False)` helper.
- [ ] 2.2 **(RED)** Test that the skeleton name is reported as the file's **literal** value,
      including an auto-generated one, with no canonical name substituted.
- [ ] 2.3 **(RED)** Test video-path parsing to `(qr_code, day, date, scanner)` over the
      shapes present in the corpus, including the scanner-suffixed directory form; and that
      a malformed path, or one yielding an **empty** QR, is reported rather than parsed into
      wrong fields.
- [ ] 2.4 **(RED)** Test that provenance — recorded source path **and** species metadata — is
      read from the **original** version on a two-version collection whose repair version
      carries a temp path and no species tags. This is what retires `#49`'s "share paths are
      unusable" assessment and currently has no other test.
- [ ] 2.5 **(RED)** Test that a **single-version** collection reads provenance and the
      images-embedded value from that one version, using a `.pkg.slp` fixture — the shape of
      the two soybean collections, which have no repair version.
- [ ] 2.6 **(RED)** Test that a labels file with **zero videos** yields a collection entry
      recording that, not a division by zero, an empty CSV without a header, or a silently
      skipped collection.
- [ ] 2.7 **(GREEN)** Implement `inventory/read.py`.

## 3. Bloom resolution

- [ ] 3.1 **(RED)** Test that the Bloom client issues **only `GET`**: assert the recorded
      method of every request, and that a client attempting any other method fails the run.
      This is the enforceable form of the read-only guarantee — the available credentials
      carry write authority, so no permission check protects us.
- [ ] 3.2 **(RED)** Test that the client is **injected** and the double is **strict**, per
      1.5's pattern.
- [ ] 3.3 **(RED)** Test the QR→scan lookup returns `species_name`, `plant_id`,
      `plant_age_days`, `experiment_id`, against a fake speaking the **`cyl_scans_extended`
      row keys** (`qr_code`) while the emitter uses the **`scans.csv` column names**
      (`plant_qr_code`) — the two differ and conflating them breaks the join.
- [ ] 3.4 **(RED)** Test that lookups are **batched** against the **rendered,
      percent-encoded** URL length, not the sum of identifier lengths, and that every scan in
      an over-limit collection still resolves. The identifiers are strings needing quoting,
      and the quote and bracket characters are themselves percent-encoded, so
      `len(str(v)) + 1` under-counts. `bloomctl`'s `_postgrest.py` measured the real ceiling
      (1,312 ids passed, 1,343 did not, ≈5.4 KB) and budgets 4,000 characters — reuse the
      budget, not the counting method, since it only ever batched bigints.
- [ ] 3.4a **(RED)** Test the `in.(…)` quoting rule for string identifiers — supabase-py
      wrapped any value containing `,:()` in quotes and we no longer get that for free.
- [ ] 3.5 **(RED)** Test that an **expired session** is detected by the gateway's own signal
      — an unauthorized status carrying its JWT-expiry code, not by matching free text — and
      that the lookup is retried once after obtaining a fresh session, with a scan that
      resolves on retry not left unresolved.
- [ ] 3.5a **(RED)** Test that the token exchange is the **only** non-`GET` request: assert
      every PostgREST-base request used `GET`, that the sole non-`GET` in the recorded log is
      the token endpoint, and that a second non-`GET` elsewhere fails the run. A client-wide
      `GET`-only rule would forbid logging in — the read path is `GET`, the login is a `POST`.
- [ ] 3.6 **(RED)** Test that a QR code absent from Bloom yields `unresolved` with the
      "no record" reason, distinct from the malformed-path reason, and does not raise.
- [ ] 3.7 **(RED)** Test that loaded credentials appear in **no** repr, log line, exception
      message, or emitted artifact — formatting an exception that carries the credentials
      object must not print them. Precedent: `bloomctl`'s `field(repr=False)` on its two
      secret fields, with the comment that a dataclass renders every field by default.
- [ ] 3.8 **(GREEN)** Implement `inventory/bloom.py`. Keep credential loading and client
      construction in one thin adapter so the offline-untestable surface is a handful of
      statements, per the coverage note above.

## 4. Reconciliation

- [ ] 4.1 **(RED)** Test the three-state classification — agreed, disagreed (carrying both
      values), unresolved (carrying its reason) — comparing **age and scan date** only.
- [ ] 4.2 **(RED)** Test that species is taken from Bloom when the collection name and the
      containing folder both say otherwise, and that the disagreement is recorded.
- [ ] 4.3 **(RED)** Test that a collection whose scans record **more than one species** is
      reported as **mixed**, naming each, with no majority chosen.
- [ ] 4.4 **(RED)** Test that a species outside the model-side vocabulary is reported without
      error.
- [ ] 4.5 **(RED)** Test that aggregates exclude disagreed and unresolved rows, with a
      fixture where including them would change the answer.
- [ ] 4.6 **(RED)** Test scan/plant counting from **Bloom `plant_id`**, not the filename
      code: one plant at two ages is 1 plant / 2 scans; one plant twice in a day from two
      scanners is 1 plant / 2 scans; and where distinct codes and distinct `plant_id`s differ
      in number, the reported count is the `plant_id` count.
- [ ] 4.7 **(RED)** Test that a scan count below the plant count fails loudly, naming the
      collection, and emits no aggregate for it.
- [ ] 4.8 **(RED)** Test that a collection with exceptions has **its** aggregate withheld
      while other collections are still emitted, and that a clean collection emits without
      withholding.
- [ ] 4.9 **(RED)** Test that a collection with **no surviving scans** is emitted as an entry
      recording that, not as an aggregate of zero marked verified.
- [ ] 4.10 **(GREEN)** Implement `inventory/reconcile.py`.

## 5. Discovery and the skeleton diff

- [ ] 5.1 **(RED)** Test that the walk **root is a parameter** by walking a `tmp_path` tree
      with no share present, so discovery runs on every CI platform; that a folder with a
      top-level labels file is inventoried; and that one without is skipped **with a reason**.
- [ ] 5.2 **(RED)** Test that split files beneath a collection are not treated as
      collections, and that the reported frame count is the top-level file's — using a
      fixture whose split count differs, so the test discriminates.
- [ ] 5.3 **(RED)** Test the skeleton diff's three outcomes (verifies / contradicts / no row)
      and that nothing is written back to the table.
- [ ] 5.4 **(RED)** Test that two collections differing only by capture mode with different
      node counts are reported as a **keying gap**, not a contradiction on either row.
- [ ] 5.5 **(GREEN)** Implement `inventory/discover.py` and `inventory/skeleton_diff.py`.

## 6. Redaction, emission, determinism

- [ ] 6.0 **(GREEN, first)** Define the three closed vocabularies — per-scan status,
      per-field confidence (`verified` / `share_only` / `unverified` / `absent`), and
      collection outcome — as constants in a **leaf** `inventory/vocab.py`, importable
      without the registry or Bloom client libraries. Nothing else creates these, and 8.9's
      doc-lock has nothing to lock without them.
- [ ] 6.1 **(RED)** Test that redaction is **structural**: a user segment whose name appears
      in no enumerated substitution is still redacted, and any UNC host segment is redacted.
      The share holds several people's directories, so a literal denylist redacts one person
      and passes the rest through into a **public** repo — and a test written around the
      enumerated name would call that clean. Assert additionally that no un-redacted host or
      user segment survives into **any** artifact, and that redacted paths remain
      distinguishable by prefix.
- [ ] 6.1a **(RED)** Test that `inventory/redact.py`'s rule still covers
      `scripts/pull_tf_reference.py`'s `_REDACTIONS` as a floor, loading that script **by
      path** the way `tests/test_scripts.py` already does — `scripts/` has no `__init__.py`,
      so `src/` cannot import from it, and this is what keeps the two from drifting.
- [ ] 6.2 **(RED)** Test that person-identifying Bloom fields appear in no emitted artifact.
- [ ] 6.3 **(RED)** Test that per-scan CSV columns are grouped by source; that
      `species_name` and `plant_age_days` are asserted against
      `sleap_roots_contracts.params`'s `SPECIES_NAME_FIELD` / `PLANT_AGE_DAYS_FIELD` rather
      than string literals; and that the remaining Bloom column names come from a committed
      `tests/fixtures/bloom_csv_columns.py` transcribed from `bloomctl`'s `CSV_COLUMNS`, with
      the source version recorded in its docstring. The set is a documented **subset** —
      person-identifying and provenance-free columns are excluded, and `genotype` is resolved
      through the accessions lookup or omitted, never read from the scan row.
- [ ] 6.4 **(RED)** `@pytest.mark.integration` — drift test: `pytest.importorskip("bloomctl")`
      then assert the committed fixture equals `bloomctl.cyl.download.CSV_COLUMNS`. Skips
      cleanly wherever `bloomctl` is absent, which is everywhere today.
- [ ] 6.5 **(RED)** Test that the aggregate YAML carries per-field confidence and the
      reconciliation tally, asserted against a committed golden file so 6.7's byte-identity
      check cannot pass by both runs being equally wrong.
- [ ] 6.6 **(RED)** Test that the images-embedded value describes the version a consumer
      receives, on a two-version collection where the two answers differ.
- [ ] 6.7 **(RED)** Test determinism and idempotence: no run timestamp, hostname or run
      identifier appears in any artifact; two runs over unchanged inputs are byte-identical;
      and adding a collection leaves unchanged collections' per-collection artifacts
      byte-identical and their aggregate entries unchanged.
- [ ] 6.8 **(RED)** Test that emission is **atomic** — an interruption mid-emit leaves the
      previous artifact unchanged and no partial file beside it. Precedent:
      `registry/models.py`'s `_extract_atomic` and `labeling/copy_images.py`'s staged rename.
- [ ] 6.9 **(GREEN)** Implement `inventory/redact.py` and `inventory/emit.py`.

## 7. CLI

- [ ] 7.1 **(RED)** Test `inventory labels --out` end to end against injected registry and
      Bloom clients, **passing a `tmp_path` walk root** and applying `isolate_wandb_env`, so
      the CLI test cannot reach the share or build a real client from a contributor's ambient
      `wandb login`. Assert the three artifacts are written, that every PostgREST-base request
      was a `GET`, and that no download occurred.
- [ ] 7.2 **(RED)** Test that an absent **registry** or absent **share** exits naming which
      source is missing and emits nothing, and that absent **Bloom** classifies every row
      unresolved, emits the per-scan output, and emits no aggregate. Note `wandb.Api()`
      raises at construction without a key, so the guard belongs at the CLI, before injection.
- [ ] 7.3 **(GREEN)** Implement the `inventory` command group in `cli.py`, placed before the
      `labeling` group per 0.3.

## 8. Docs

- [ ] 8.1 `README.md`: new "Inventorying the label corpus" section following the
      `seed-registry` pattern — the command, the share / `WANDB_API_KEY` / Bloom-profile
      prerequisites, the joint-requirement and Bloom-degradation behaviour, the rerun
      contract, and where the committed artifacts live. Plus a pointer from the doc list,
      per `add-tf-reference-fixtures` task 5.3's precedent for exactly this.
- [ ] 8.2 `docs/labeling-packages.md`: new "Reading the corpus inventory" section carrying
      the per-scan CSV's column table grouped by source and the aggregate YAML's shape,
      migrated out of the superpowers design doc, which does not archive with this change.
- [ ] 8.3 In the same section, define both closed vocabularies **by name**: `status`
      (`agreed`; `disagreed` — both values carried, none picked; `unresolved` — no Bloom
      record obtained, either a malformed path or a code Bloom has never seen, **not** a
      claim the scan is absent from the corpus, and not an error) and `confidence`. State
      that disagreed and unresolved rows are excluded from every aggregate, so a CSV row
      count and the reported `n_scans` are expected to differ.
- [ ] 8.4 In the same section, note that reported species comes from Bloom and may fall
      outside `SPECIES_VOCAB`, that this is expected, and that widening is `#49`'s D5.
- [ ] 8.5 State that the capability writes nothing to the registry or Bloom and issues only
      `GET` — for the reader; the property itself survives archive in the spec.
- [ ] 8.6 `openspec/project.md`: extend Purpose to cover corpus inventory alongside
      training and evaluation, and reconcile Important Constraints — W&B is the system of
      record for label *artifacts*; Bloom for *scan metadata*. The current line reads "not
      Bloom" without that split.
- [ ] 8.7 `docs/roadmap.md`: place this under Tier 2 and reconcile with `#23` — state
      whether it supersedes, complements, or is disjoint from the label inventory the
      roadmap already refers to as existing.
- [ ] 8.8 `docs/CHANGELOG.md`: entry under `[Unreleased]` → `### Added`.
- [ ] 8.9 `tests/test_inventory_docs.py`: doc-lock matching `tests/test_labeling_docs.py` —
      every documented command and option exists on the CLI, every option is documented at
      least once, and the documented `status` / `confidence` vocabularies equal the emitter's
      constants, so artifact semantics cannot drift from the code that writes them. All four
      existing top-level docs have such a lock.

## 9. Gate

- [ ] 9.1 Mirror CI exactly: `uv run pytest --cov=src/sleap_roots_training
      --cov-fail-under=95 -m "not integration" tests/`, plus `uv run black --check src tests`,
      `uv run ruff check src tests`, `uv lock --check`, and
      `openspec validate add-label-corpus-inventory --strict`. Re-measure coverage of the new
      tree before declaring the gate met. Headroom grows with the tree, so budget from the
      real arithmetic rather than a fixed number: for `N` new statements the allowance is
      roughly `46 + 0.055·N` misses — about 78 at `N=600`, 89 at `N=800`, implying the new
      tree needs ~87-89%. Forecast ~3 uncovered statements per lazily-constructed client,
      which is what `registry/publish.py`'s four uncovered lines are.
- [ ] 9.2 Run the unfiltered suite separately, as a credentialed step, and record that it
      requires the share and credentials. **Every new `integration` test SHALL skip cleanly
      when its credentials or the share are absent** — there is no `addopts`, and
      `.claude/commands/coverage.md` runs the suite unfiltered, so a hard failure there breaks
      `/coverage` for anyone without production access.
- [ ] 9.3 Archive with `@fission-ai/openspec` **≥ 1.7.0**, which means an explicit upgrade:
      the CLI currently on `PATH` is **0.13.0**. Confirm the live spec's `Purpose` is the real
      text, not the `TBD - created by archiving change …` stub. Verified by bisection: 1.5.0
      and 1.6.0 clobber it; 1.7.0+ preserve it. Four of the five live specs carry the stub
      today.
- [ ] 9.4 Reconcile implementation against this proposal per `/new-feature` step 9: verify
      2.1 really calls `sio.save_slp`/`sio.load_slp`; that 3.1 asserts the HTTP method rather
      than a method name on a mock; that 6.3 reads the contracts constants and the committed
      fixture rather than literals; and that every named module exists. Record any deviation
      with a `### Why N instead of M?` note.

## 10. Follow-ups — deliberately not tasks of this change

Recorded here so they are not lost, and **excluded** from this change's checklist: none can
be a commit in this PR, and leaving them unchecked would keep the change out of the archive
indefinitely, as it has for three other changes now sitting unarchived on `main`.

- **First production run** → a `docs/inventory.md`-style runbook section (8.1), and
  optionally a scheduled workflow following `verify-skeleton-table.yml`, which exists for
  exactly this shape of heavy production-data check. If that route is taken, wire the trigger
  in the same PR — that workflow's own header records a gated check that nothing ever
  triggered, so the risk it was meant to close stayed open.
- **A second reviewer on `inventory/bloom.py`** → a PR-description request, not a task. The
  `GET`-only test (3.1) is the mechanical backstop.
- **Adjudicating the gated exceptions and committing the artifacts** → its own follow-up PR
  after this merges.
- **Retiring `verify-skeleton-table.yml`** → separate change, once this subsumes it.
- **Posting the aggregate YAML to `#49`** → better as a small PR against `#49`'s branch
  striking its §2.1/2.2/2.4/2.5 in favour of consuming this artifact, so the retirement is
  recorded in `#49`'s own change rather than in a comment.
