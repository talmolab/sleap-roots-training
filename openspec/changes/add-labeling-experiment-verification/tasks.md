# Tasks — verify a labeling package's Bloom identity

Sequenced so the verification exists and is tested before any CLI surface is added, and so the
"unverified" path is pinned first — it is the one every existing workflow takes.

## 0. Confirm the export's shape before designing to it

- [ ] 0.1 Confirm the traits export is **one row per scan**. The WEEP export is 372 rows over 197
      plants (~1.9 scans per plant), which is consistent with per-scan and also confirms multi-age
      is the normal shape of this data. If it is per-scan-per-something-else, the join in 1.2 needs
      revisiting.
- [ ] 0.2 Confirm the `experiment_id` dtype as pandas reads it. `bloom_experiment_id` is an `int`
      in `PackageRecord`; a column pandas types `float64` because of a null elsewhere would make a
      naive `==` fail on a correct package. Compare as `int` on both sides, the way
      `_accession_key` already normalizes accession ids.
- [ ] 0.3 Record what `primary` / `lateral` mean in this export. **Do not build on them in this
      change** — noted because they may state which root types a scan has predictions for, which
      `build_slp_project` currently discovers by globbing, and which bears on the "never asked" vs
      "asked and found nothing" distinction.

## 1. The check itself

- [ ] 1.1 Add `assert_manifest_belongs_to_experiment(manifest, export, bloom_experiment_id)` to
      `labeling/package.py`. Validate the required columns first and name a missing one, following
      `copy_images._assert_required_columns`.
- [ ] 1.2 Cross-check on `scan_id`: every manifest scan must appear in the export, and every matched
      row's `experiment_id` must equal the declared id. Report **all** offending scans, not the
      first — the same rule the other multi-row checks in this package follow.
- [ ] 1.3 (RED first) Tests: all-match passes; one scan in another experiment fails naming the scan
      and both experiment ids; a scan absent from the export fails naming it; a missing column fails
      naming the column; an export whose `experiment_id` pandas typed `float64` still passes.

## 2. Recording the outcome

- [ ] 2.1 Add `experiment_verified: bool = False` and `experiment_name: Optional[str] = None` to
      `Provenance`. Both optional on read, like every field added in the #40 review.
- [ ] 2.2 Serialize both in `to_container` / `_read_provenance`, and pin the round trip.
- [ ] 2.3 (RED first) Test that a package written before these fields existed still reads, with
      `experiment_verified` false and `experiment_name` absent — the eight published collections and
      every package built during #40 are in this state.
- [ ] 2.4 Test that a build **without** the export produces a valid package recording
      `experiment_verified: false`. This is the path every existing workflow takes and must not
      regress.

## 3. Wiring

- [ ] 3.1 Thread an optional export path through `build_labeling_package` into `build_provenance`.
      Keep it keyword-only and defaulted, so no existing caller changes.
- [ ] 3.2 Run the check **before** the staging directory is created, alongside
      `_assert_selection_could_have_produced` — a failure here must leave nothing behind, and the
      check needs no filesystem work to perform.
- [ ] 3.3 Add the optional CLI option to `labeling build`. Use
      `click.Path(exists=True, dir_okay=False)` so a bad path fails at the argument rather than
      inside the build.
- [ ] 3.4 Test end to end through the CLI: verified build, and a mismatched build that exits
      non-zero as a clean `Error:` rather than a traceback.

## 4. Docs

- [ ] 4.1 `docs/labeling-packages.md`: document the option under **Build**, and say plainly that
      omitting it leaves the Bloom trace unverified rather than absent.
- [ ] 4.2 `.claude/commands/build-labeling-package.md`: add the flag to the Phase 2 invocation.
      **Do not touch Phase 0 step 3** — the `psql` accession lookup stays; see 4.3.
- [ ] 4.3 Record in `design.md` that the export's `genotype` column is **not** the accession name
      (confirmed 2026-08-10), so `--accession-names` remains the manual lookup design.md F2
      describes. The guess is natural and will otherwise be made again — the payoff would have been
      retiring a `psql` call against a hardcoded host with a password read from a `.env`.
- [ ] 4.4 `docs/CHANGELOG.md` entry under Added.

## 5. Validation

- [ ] 5.1 `openspec validate add-labeling-experiment-verification --strict`
- [ ] 5.2 `uv run pytest`, `uv run black --check src/sleap_roots_training tests`,
      `uv run ruff check src/sleap_roots_training`
- [ ] 5.3 Run a real build against `~/data/weep` with the real traits export and confirm the
      verified path on actual data, not only fixtures — the same standard
      `add-labeling-package-generator` 9.2a set for the validator.
- [ ] 5.4 Correct `add-labeling-package-generator` task 9.10 to point here, rather than leaving
      `bloom_experiment_id` recorded as blocked.
