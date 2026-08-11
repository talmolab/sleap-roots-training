# Verify a labeling package's Bloom identity against the pipeline's own export

## Why

`labeling build` takes `--bloom-experiment-id` as a required, free integer and writes it into
`package_metadata.yaml` unchanged. Nothing in the package can corroborate it. It is the trace back
to source data that `#10`'s `LabelCard` depends on, and a typo produces an artifact whose own
provenance is wrong in a way no consumer can detect — the exact failure
`Provenance`'s docstring argues is worse than recording nothing.

This was recorded in `add-labeling-package-generator` task 9.10 as **genuinely blocked**, on the
grounds that nothing in the inputs could corroborate it. **That was wrong**, and the correction is
the reason this change exists: the sleap-roots pipeline's per-scan traits export carries
`experiment_id` as a column — constant `10102496` across all 372 rows of the real WEEP export, zero
nulls — alongside `experiment_name` (`WEEP_Soybean`) and a per-row `scan_id`. The limit was
asserted without reading the file that had the answer.

Per-row `scan_id` makes this stronger than reading a constant. The check is not "does the operator's
number match the file's number" but **"does every scan in this manifest actually belong to the
declared experiment"** — which also catches a manifest assembled from two experiments, something no
amount of care with the `--bloom-experiment-id` flag would.

The operator doc's own `head -2 "$EXPERIMENT_FOLDER/images_downloader_output/scans.csv"` idiom
(`build-labeling-package.md:76`) implies the same shape — a constant column readable from the first
data row — which is weak corroboration that whoever wrote that line was describing something real.
Whether `scans.csv` *also* carries the column is unconfirmed and does not matter here: this change
reads whichever export it is given, by column name.

## What Changes

- **`labeling build` accepts an optional export** carrying `experiment_id` and `scan_id`, and
  cross-checks the manifest against it: every manifest `scan_id` must appear in the export, and
  every matched row's `experiment_id` must equal the declared `--bloom-experiment-id`. A mismatch
  fails the build before anything is written.
- **`package_metadata.yaml` records `experiment_name`** when the export supplies it, so the package
  carries a human-readable identity and not only an integer.
- **`provenance` records that the identity was verified**, so a consumer can distinguish a package
  whose Bloom trace was checked from one where it was typed. A package built without the export
  stays valid — it is recorded as unverified rather than rejected.
- The check is **opportunistic and column-driven**, not filename-driven: it requires only
  `experiment_id` and `scan_id`, so it works against the traits export today and against `scans.csv`
  if `bloomctl` ever carries the column.

## What This Change Does *Not* Do

- **Retire the manual accession lookup.** The traits export has a `genotype` column beside
  `accession_id`, and the obvious guess is that it is the accession name — which would eliminate the
  `psql` step in `build-labeling-package.md` Phase 0 step 3, including its hardcoded database host
  and its password read from a `.env`. **It is not the accession name** (confirmed 2026-08-10), so
  `--accession-names` remains the manual Bloom lookup design.md F2 describes. Recorded here because
  the guess is natural and someone will otherwise make it again.
- **Interpret the export's `primary` / `lateral` columns.** They are per-scan and may state which
  root types a scan has predictions for — which the builder currently discovers by globbing
  `predictions_dir`, and which bears on the "never asked" vs "asked and found nothing" distinction
  in `build_slp_project`. Their semantics are unconfirmed, so nothing here depends on them.
- **Make the export required.** Requiring it would break every existing workflow and make the
  pipeline's traits stage a hard prerequisite of the labeling stage, which it is not today.
- **Re-derive the selection.** Verifying the recorded `seed` needs the QC-cleaned pool, which the
  build stage does not receive. That is a separate gap, tracked in
  `add-labeling-package-generator` 9.10.
- **Talk to Bloom.** design.md F2 stands: nothing in this repo makes a network call. This reads a
  file the pipeline already wrote.

## Impact

- **Depends on `add-labeling-package-generator` (#40)**, which introduces the `labeling-package`
  capability, `Provenance`, and the `labeling build` command this extends. That change is complete
  and green; this one is deliberately scoped out of it so it can merge.
- Affected specs: `labeling-package` (ADDED requirements only — no existing requirement changes).
- Affected code: `labeling/metadata.py` (two provenance fields), `labeling/package.py` (the check
  and its wiring), `cli.py` (one optional option), `docs/labeling-packages.md`,
  `.claude/commands/build-labeling-package.md`.
- **No existing package becomes invalid.** Both new fields are optional on read, exactly as
  `provenance` itself is.
