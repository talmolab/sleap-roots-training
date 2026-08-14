# Building a labeling package

How to turn a finished cylinder experiment into a self-contained SLEAP package a labeler can
open — and how to add frames to one that has already been published.

A **labeling package** is a directory. It carries the labeled `.slp` per root type, the curated
images, `sample_manifest.csv` with one row per labeled frame, `package_metadata.yaml`, and a
`README.md` for the labeler. Everything a consumer needs is inside it: no `Z:` mount, no
reference to the machine that produced it. That is the contract `publish-labels` reads.

```
soybean-weep-labeling/
├── README.md
├── package_metadata.yaml                        # identity, selection parameters, skeletons
├── sample_manifest.csv                          # one row per labeled frame
├── images/                                      # curated JPGs, flat, renamed
├── soybean_weep_primary_labels.v000.slp         # primary root predictions
└── soybean_weep_lateral_labels.v000.slp         # lateral root predictions
```

## Prerequisites

The experiment folder must already have completed the sleap-roots pipeline:

- `images_downloader_output/scans.csv` and the downloaded `images/` (from a Bloom download)
- `sleap_roots_traits_input/` with prediction `.slp` files (from sleap-roots-predict)
- QC output from sleap-roots-analyze — one `10_final_data.csv` per age group

**Accession names are a manual lookup.** Nothing in this repo talks to Bloom. Query the
`accessions` table for the ids your `scans.csv` uses and save the result as JSON:

```json
{"12742739": "A3244", "12742740": "WEEP-1-4", "12742741": "WEEP-1-1"}
```

Pass it as `@accessions.json` to both `select` and `build`. Every id the manifest uses must be
in it — an unmapped id fails the build rather than documenting a genotype as a number.

## 1. Select

```bash
sleap-roots-training labeling select \
  --cleaned-csv "<experiment>/sleap-roots-analyze-output/*/10_final_data.csv" \
  --scans-csv "<experiment>/images_downloader_output/scans.csv" \
  --output-csv "<work>/sample_manifest.csv" \
  --plants-per-group 5 \
  --views-per-plant 3 \
  --seed 42 \
  --accession-names @accessions.json
```

`--cleaned-csv` takes a glob directly. QC writes one file per age group; the glob is resolved
here, so there is no manual concatenation step.

Selection reads the QC-cleaned barcodes as the sampling pool (so poorly germinated plants are
excluded), stratifies by `plant_age_days` × `accession_id`, and picks evenly-dispersed
rotational views, stepped uniformly around the rotation so every count covers the whole
cylinder. It is deterministic: the same parameters select the same frames. Raising
`--plants-per-group` yields a superset of the narrower selection; raising `--views-per-plant`
re-spaces the views, so it adds frames without guaranteeing it keeps every old one. Either way
a given curated filename always names the same view of the same plant, which is what makes
step 4 below a real recovery path — a re-derived package can be merged with labels returned
against the narrower one.

**Write down the parameters you used.** `build` needs them, and records them in the package.

## 2. Build

```bash
sleap-roots-training labeling build \
  --manifest "<work>/sample_manifest.csv" \
  --scans-csv "<experiment>/images_downloader_output/scans.csv" \
  --predictions-dir "<experiment>/sleap_roots_traits_input" \
  --output-dir "<out>/soybean-weep-labeling" \
  --species soybean --mode cylinder --experiment weep \
  --root-type primary --root-type lateral \
  --bloom-experiment-id 10102496 \
  --accessions @accessions.json \
  --seed 42 --plants-per-group 5 --views-per-plant 3 --total-views 72
```

This gathers the images, builds one `.slp` per root type with the predictions as starting
points, writes the metadata and the README, and validates the result. **It is all-or-nothing**:
the output directory does not exist until a complete, validated package is ready to move into
it, so a failed run leaves nothing that a later step could mistake for a package.

The selection parameters are repeated here on purpose — they go into `package_metadata.yaml`, and
the build checks them against the manifest rather than taking them on trust.

Skeletons come from the committed table in `src/sleap_roots_training/labeling/data/skeletons.yaml`,
keyed by `(species, root_type)` and, for rice, by age. A pair the table does not cover **fails**;
it does not fall back to another crop's node counts. Add a verified row before labeling a new crop.

### Re-running one stage

`build` runs the copy step itself. `labeling copy-images` exists for when you need that stage
alone — a re-download, or diagnosing a path problem:

```bash
sleap-roots-training labeling copy-images \
  --manifest "<work>/sample_manifest.csv" \
  --scans-csv "<experiment>/images_downloader_output/scans.csv" \
  --output-dir "<out>/soybean-weep-labeling/images" \
  --total-views 72
```

`source_image` resolves against **the directory holding the `scans.csv` you pass**, and every
row must be described by that file. Pointing at the wrong `scans.csv` is an error naming the
scan, not an empty copy that reports success.

## 3. Validate

```bash
sleap-roots-training labeling validate "<out>/soybean-weep-labeling"
```

`build` already runs this; run it again on a package you were handed, or after moving one. It
checks the layout, the manifest's columns, that the declared frame count and the curated images
agree with the manifest, that the recorded skeletons are the ones actually in the `.slp` files,
and that each `.slp` is self-contained. It reads nothing outside the directory, so a package
validates where it lands and not only where it was built.

This is the entry point `publish-labels` calls before any upload.

## 4. Adding frames later: re-derive and republish

**To add labeled frames to a package that has already been published, re-select wider and
publish a new version. Do not edit or de-embed the published artifact.**

```bash
# 1. Re-fetch the experiment if the download is gone.
bloomctl download --experiment-id <id> <dir>

# 2. Re-select with a wider frame set — same seed, larger counts.
sleap-roots-training labeling select ... --plants-per-group 8 --views-per-plant 4 --seed 42

# 3. Build the next version.
sleap-roots-training labeling build ... --version v001 --output-dir "<out>/soybean-weep-labeling-v001"
```

A widened re-run keeps every plant the narrower one selected, and every frame it keeps arrives
under the same `output_filename` — the name embeds the *view*, not its position in the
selection. So labels a labeler returned against the narrow package still attach to the right
image in the wide one, which is the only reason this works. Widening `--views-per-plant` also
re-spaces the views, so some narrow frames may not recur; they are not lost, they are simply
not re-requested, and their names never get reused for different pixels.

**Why not edit the published package.** The `.slp` embeds its images, and de-embedding to widen
it does not round-trip: `save_slp` restores the original video only *if it is still available*.
A package whose source paths have gone unreachable — a dead temp directory, an unmounted `Z:` —
is therefore capped at whatever frames were embedded, permanently. Six of the eight collections
in `wandb-registry-sleap-roots-labels` carry `repaired_from: "v0"` for exactly this reason: an
external-reference `.slp` broke and was hand-patched into a package afterwards, and its label set
can no longer grow. Embedding at build time is what stops that happening again; re-deriving is
what you do instead of repairing.

W&B artifact versions are immutable snapshots anyway, so a new version is the natural grain.

## What changed from the vault scripts

If you ran the previous `select_samples.py` / `copy_selected_images.py` / `build_slp_project.py`
/ `generate_readme.py`, the behavior differences that affect you:

- **A given seed selects different plants.** The draw is now a stable hash ordering rather than
  `pandas.sample`, which is what makes widening the plant dimension monotone. Packages built
  before this change cannot be reproduced by re-running with the same seed.
- **View indices are unchanged.** Three views are `[1, 25, 49]` and four are `[1, 19, 37, 55]`,
  the same uniform step the published collections were selected with, so new packages share
  their view geometry.
- **Curated filenames name the view, not its position**: `A3244_9DK8KJJEZR_age3_view025.jpg`
  rather than `A3244_9DK8KJJEZR_age3_0.jpg`. The old name meant something different depending
  on how many views the run asked for, so merging corrections from a re-derived package could
  attach one view's root traces to another view's image.
- **The `.slp` embeds its images.** Opening a package no longer depends on `images/` being beside
  it. `images/` still ships, for review and for the manifest's `output_filename` to resolve against.
- **Failures are failures.** An unresolvable source image, a scan with no predictions, a scan
  whose predictions do not cover every selected view, a duplicate or case-colliding curated
  filename, a curated filename that is not a plain filename, an absolute or `..`-bearing source
  path, a scan whose view count contradicts `--total-views`, a null `accession_id` or
  `plant_age_days`, and an empty selection each stop the run. All of them previously warned and
  continued, or were not checked at all, producing a package that reported success.
- **A frame the model found nothing in ships empty**, rather than vanishing. The labeler opens
  it, confirms nothing is there, and that confirmation is ground truth — a true negative the
  corpus previously had no way to record. A young plant with no lateral roots is no longer
  indistinguishable from predictions that missed the view. The build still fails if a declared
  root type is empty in *every* frame of every scan.
- **`validate` opens the `.slp` files and counts their frames**, rather than comparing the
  declared count against the manifest it was derived from. A package whose projects are shorter
  than its manifest is rejected wherever it is validated, including one built by an older tool.
- **`package_metadata.yaml` records a `provenance` block**: the `scans.csv` and manifest hashes,
  the skeleton-table hash, the code version, and the model that produced the `v000` starting
  points (labelers anchor on those, so the predicting model is a confounder in what comes back). The selection parameters alone only reproduce a
  package against a byte-identical pool, and the usual reason to re-derive one is that new waves
  have landed — so this is what lets you check you are re-deriving from the same thing. Packages
  built before this exists read back fine, with `provenance` absent.
- **`.DS_Store` no longer fails a package.** Operating-system sidecars in `images/` are ignored,
  so opening a package on macOS before validating it does not reject it.
- **Stratification no longer leaks across age groups.** A plant selected at one age used to drag
  in all its other ages, over-representing the plants that survive to be scanned repeatedly —
  survivorship correlates with vigor, so the sample skewed toward healthy plants. Groups smaller
  than `--plants-per-group` are now reported rather than silently taken whole.
- **Predictions whose skeleton does not match the package's are rejected.** The rebind is
  positional, so a model emitting the node chain tip-first would have had every root's polarity
  silently reversed. Only the node *count* was checked.
- **A build that would not fit in memory fails first.** Embedding holds every frame in RAM before
  writing, so a large enough package was killed by the OS mid-write — and a SIGKILL runs no
  cleanup, leaving a partial package nothing sweeps. The ceiling is 2 GiB of curated images per
  `.slp`, overridable with `SLEAP_ROOTS_LABELING_EMBED_CEILING_BYTES`.
- **Counts are validated as counts.** `--plants-per-group 0` or `-1` used to select nothing, or
  every plant but the last in each group, and exit 0.
- **An incomplete `--accession-names` map fails at `select`**, not three stages later at `build`
  where fixing it would rename every file in the package.
- **The copy step takes `--scans-csv`**, not the experiment directory.
- **The README is generated from `package_metadata.yaml`**, so it is no longer hand-edited per
  crop, and its counts cannot disagree with the manifest.

The full list, with the reasoning for each, is in the change's `tasks.md` §7.
