---
name: Build Labeling Package
description: Build a SLEAP labeling package for a labeler from a finished cylinder experiment. Takes the experiment folder, crop, and experiment slug. Produces a self-contained package ready to publish.
category: Research
tags: [sleap, labeling, training-data, sleap-io, cylinder, bloom]
args: experiment_folder
---

**Goal**
Build a self-contained SLEAP labeling package from a finished cylinder experiment's pipeline
output: curated images plus model predictions as `PredictedInstance` for a labeler to correct.

Ported into this repo from the vault workflow (talmolab/sleap-roots-training#26). The four
scripts it used to drive are now `sleap_roots_training.labeling`, reachable from the CLI — so
this command runs published commands rather than `uv run` against paths on one machine.

The contributor-facing guide is [`docs/labeling-packages.md`](../../docs/labeling-packages.md);
it explains the package layout, the deviations from the old scripts, and the re-derive path.
This file is the operational checklist.

**Usage**
```
/build-labeling-package <experiment_folder> --crop <crop> --experiment <slug>
```

**Arguments**
- `<experiment_folder>`: Path to the experiment (e.g. `Z:/users/eberrigan/20250328_..._WEEP_Soybean_March_2025`)
- `--crop <crop>`: Crop species (soybean, canola, arabidopsis, rice — see the skeleton table)
- `--experiment <slug>`: Short experiment slug used in filenames (e.g. `weep`)
- `--plants-per-group <n>`: Plants per age × accession group (default: 5)
- `--views-per-plant <n>`: Rotational views per plant (default: 3)

**Prerequisites**
The experiment folder MUST already have completed the sleap-roots pipeline:
- `images_downloader_output/scans.csv` and its downloaded `images/`
- `sleap_roots_traits_input/` with prediction `.slp` files (from sleap-roots-predict)
- `sleap_roots_traits_output/traits_summary.csv` (from sleap-roots-traits)

If sleap-roots-analyze has NOT been run yet, run it first (Phase 1).

---

## Phase 0: Validate prerequisites

1. **Check the experiment folder** has the required outputs:
   ```bash
   ls "$EXPERIMENT_FOLDER/images_downloader_output/scans.csv"
   ls "$EXPERIMENT_FOLDER/sleap_roots_traits_input/"*.slp | wc -l
   ls "$EXPERIMENT_FOLDER/sleap_roots_traits_output/traits_summary.csv"
   ```
   **Hard stop** if any are missing — the pipeline must be run first via `/run-cylinder-pipeline`.

2. **Check for fresh accession data.** The original `scans.csv` may carry stale accession ids.
   Download fresh metadata from Bloom (`--meta_only` is fast, no images):
   ```bash
   head -2 "$EXPERIMENT_FOLDER/images_downloader_output/scans.csv"   # get the experiment id
   bloomctl download --experiment-id <ID> --meta-only <tmp_meta_dir>
   ```

3. **Query Bloom for accession names — this is a manual prerequisite.**
   Nothing in this repo talks to Bloom; the CLI takes the names as data. Read `DATABASE_URL`
   from `C:\repos\bloom\.env` at runtime (never hardcode the password) and query:
   ```bash
   psql -h <host> -U postgres -d postgres -c \
     "SELECT id, name FROM accessions WHERE id IN (<comma-separated ids>);"
   ```
   Save the result as a JSON object and keep the file — both `select` and `build` take it:
   ```json
   {"12742739": "A3244", "12742740": "WEEP-1-4", "12742741": "WEEP-1-1"}
   ```
   **Every accession id in the manifest must appear in it.** An unmapped id fails the build
   rather than documenting a genotype as a bare number.

4. **Create a merged `scans.csv`** if the ids were stale — old paths, fresh accession ids:
   ```python
   old = pd.read_csv('<experiment>/images_downloader_output/scans.csv')
   fresh = pd.read_csv('<fresh_meta_path>/scans.csv')
   acc_map = fresh[['plant_qr_code', 'accession_id']].drop_duplicates()
   merged = old.drop(columns=['accession_id']).merge(acc_map, on='plant_qr_code', how='left')
   merged.to_csv('<experiment>/images_downloader_output/scans_with_accessions.csv', index=False)
   ```
   Keep it **in the same directory** as the original: `source_image` resolves against the
   directory holding the `scans.csv` you pass, so moving it elsewhere breaks the copy step.

---

## Phase 1: Run sleap-roots-analyze (if not already done)

Check whether `sleap-roots-analyze-output/` exists in the experiment folder. If not:

1. **Create `traits_summary_with_genotype.csv`** — merge accession names into traits:
   ```python
   accession_map = {<id>: '<name>', ...}   # the Phase 0 step 3 lookup
   traits = pd.read_csv('<experiment>/sleap_roots_traits_output/traits_summary.csv')
   traits['genotype'] = traits['accession_id'].map(accession_map)
   traits.to_csv('.../traits_summary_with_genotype.csv', index=False)
   ```

2. **Configure and run QC + Viz** using `/configure-run-all` from `sleap-roots-analyze`:
   - `columns.genotype: "genotype"` (name, NOT numeric id)
   - `columns.barcode: "plant_qr_code"`
   - `columns.replicate: "scan_id"` (MUST differ from barcode)
   - `group_by: "plant_age_days"` for multi-age experiments
   - `heritability.threshold: 0.0` (calculate but don't filter)
   - `max_nan_fraction: 0.0` (strict — drops poorly germinated samples)

3. **Run**: `uv run python -m sleap_roots_analyze run-all --manifest <manifest.yaml> -o "<experiment>/sleap-roots-analyze-output"`

QC writes one `10_final_data.csv` per age group. **Do not concatenate them.** `labeling select`
takes the glob directly — the manual `pd.concat` step this doc used to carry existed only
because the old script could not resolve a wildcard in a directory component, and the port
fixes that.

---

## Phase 2: Build the package

### Step 1: Stratified sampling

```bash
sleap-roots-training labeling select \
  --cleaned-csv "<experiment>/sleap-roots-analyze-output/*/10_final_data.csv" \
  --scans-csv "<experiment>/images_downloader_output/scans_with_accessions.csv" \
  --output-csv "<work>/sample_manifest.csv" \
  --plants-per-group 5 \
  --views-per-plant 3 \
  --seed 42 \
  --accession-names @accessions.json
```

Reads the QC-cleaned barcodes as the sampling pool, stratifies by `plant_age_days` ×
`accession_id`, and picks rotational views stepped evenly around the full rotation.
Deterministic; see the re-derivation section below for what widening does and does not keep.

**Record the parameters.** Step 2 needs them and writes them into the package.

### Step 2: Build

```bash
sleap-roots-training labeling build \
  --manifest "<work>/sample_manifest.csv" \
  --scans-csv "<experiment>/images_downloader_output/scans_with_accessions.csv" \
  --predictions-dir "<experiment>/sleap_roots_traits_input" \
  --output-dir "<out>/<crop>-<experiment>-labeling" \
  --species <crop> --mode cylinder --experiment <slug> \
  --root-type primary --root-type lateral \
  --bloom-experiment-id <ID> \
  --accessions @accessions.json \
  --seed 42 --plants-per-group 5 --views-per-plant 3 --total-views 72
```

One command does the copy, the projects, the metadata, the README, and validation, and is
**all-or-nothing**: `--output-dir` does not exist until a complete validated package is ready
to move into it. There is no separate README step — it is generated from the package metadata.

Skeletons come from the committed table, keyed by `(species, root_type)` and, for rice, by age.
A crop the table does not cover fails; add a verified row rather than letting it guess.

If you need the copy stage on its own (a re-download, a path problem):
```bash
sleap-roots-training labeling copy-images \
  --manifest "<work>/sample_manifest.csv" \
  --scans-csv "<experiment>/images_downloader_output/scans_with_accessions.csv" \
  --output-dir "<out>/<crop>-<experiment>-labeling/images" \
  --total-views 72
```

### Step 3: Verify

```bash
sleap-roots-training labeling validate "<out>/<crop>-<experiment>-labeling"
```

Checks the layout, the manifest columns, the counts, the recorded skeletons against the `.slp`
files, and that each `.slp` is self-contained. This is what `publish-labels` runs before upload.

---

## Phase 3: Deliver

1. **Upload to Box**:
   ```bash
   rclone copy --update -P "<out>/<package_folder>" \
     "box:Phenotyping_team_GH/sleap-roots-pipeline-results/<package_folder>"
   ```

2. **Get the Box link**:
   ```bash
   rclone link "box:Phenotyping_team_GH/sleap-roots-pipeline-results/<package_folder>"
   ```

3. **Create or update the Notion task** in sleap-roots Tasks (collection
   `e372b7a9-31e9-4340-a5f7-575c7c7c4ac6`): Box link, experiment details, sample counts,
   accession names. Tags: "Data Processing", "Model improvement".

---

## Adding frames to a package that already shipped

Re-derive and republish — do **not** edit or de-embed the published artifact. Re-fetch with
`bloomctl download --experiment-id <id>`, re-run `select` with larger counts and the **same
seed**, and `build --version v001` into a new directory. A curated filename names the view,
so any frame that appears in both packages is the same image in both, and labels returned
against the narrower one still attach correctly. Widening `--plants-per-group` keeps every
plant the narrower run selected; widening `--views-per-plant` re-spaces the views evenly, so
some earlier frames may not recur — they are not lost, just not re-requested, and their names
are never reused for different pixels.

The reason editing is not an option: `save_slp` restores an embedded package's original video
only *if it is still available*, so a package whose sources have gone unreachable is capped at
its embedded frames permanently. See [`docs/labeling-packages.md`](../../docs/labeling-packages.md)
for the full explanation and the six published collections it already happened to.

**Reference**
- Contributor guide: [`docs/labeling-packages.md`](../../docs/labeling-packages.md)
- Skeleton table: `src/sleap_roots_training/labeling/data/skeletons.yaml`
- Notion labeling guide: https://www.notion.so/1224a67a766780da8b64c8cab59939b2
- Pipeline command: `/run-cylinder-pipeline`
- Bloom database: `C:\repos\bloom\.env` (credentials), table `accessions` for name lookups
