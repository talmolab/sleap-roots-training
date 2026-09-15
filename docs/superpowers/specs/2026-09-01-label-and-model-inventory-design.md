# Label and model inventory — design

**Status:** draft for review
**Date:** 2026-09-01
**Author:** eberrigan (with Claude Code)
**Related:** talmolab/sleap-roots-training#49, #3, #11; `skeletons.yaml`; `model_selection.yaml`

## Why

Nobody has ever enumerated what labeled data and trained models actually exist. Every
table in this program was seeded from a *snapshot of deployed state* rather than from an
inventory, and the snapshots' omissions silently became the system's schema:

- `model_selection.yaml` was transcribed from the `models-downloader`
  `model_chooser_table.xlsx` (snapshot 2025-02-04). Its header records that the
  arabidopsis **plate** row was *omitted* because those models were "absent from the
  snapshot" — tracked as #3, still open.
- `skeletons.yaml` was transcribed from a different source — the
  `build-labeling-package.md` onboarding table, itself a Box snapshot — which was written
  for **cylinder** labeling packages. It is keyed `(species, root_type, age)` with **no
  `mode`**, so it has no column plates could be omitted *from*.
- `wandb-registry-sleap-roots-labels` holds 8 collections: what happened to get uploaded,
  not what exists. The expected corpus is roughly 25–30 collections across cylinder,
  multiplant cylinder, and plate.

Two tables, two snapshots, two different keys, and the `mode` dimension fell through the
seam. The same pattern produced the label gap.

This design describes a one-time audit that produces the inventory, plus the durable
artifacts that keep it from being re-derived.

## Scope

**In scope**

- All label collections in `wandb-registry-sleap-roots-labels` (currently 8).
- SLEAP project folders under `Z:\users\eberrigan\SLEAP` (~30 exist; the exact boundary
  is Open Question 4), taking the **superset labels file per collection** — not
  `train_test_split.vNNN/` derivatives, which describe a training run rather than a
  corpus.
- All trained models found in those folders, plus W&B project `sleap-roots` runs.
- A cross-check of every recovered fact against Bloom `cyl_scans_extended` (prod, **read
  only**).

**Out of scope**

- Writing to any registry, or to Bloom. No `bloomctl cyl ingest`, no W&B publish.
- Changing `skeletons.yaml`, `model_selection.yaml`, or any shipped code path. This
  effort *reports*; schema changes are proposed separately (see Open Questions).
- Retraining, re-embedding, or repairing artifacts.

## Key findings this design is built on

All verified during design, not assumed:

1. **`Z:` is `hpi_dev` and is reachable.** All 8 registry `v0` artifacts' recorded
   `data_path`s (three different prefixes: `D:/SLEAP/…`,
   `//multilab-na.ad.salk.edu/hpi_dev/…`, `Z:/users/…`) map onto one tree, and every one
   resolves and size-matches its registry copy.
2. **`v0` carries provenance; `v1` carries trainability.** Six collections have a `v1`
   that is a *"Re-embedded (referenced_videos) repair … to restore trainable images"*.
   `v1` drops every species tag and records a throwaway temp `data_path`; `v0` has the
   real path and the species metadata. The two soybean collections were uploaded as
   `.pkg.slp` with images already embedded and so have no `v1`.
3. **Video filenames join to Bloom.** `bloomctl`'s `scan_relative_dir` builds
   `images/Wave{n}/Day{day}_{date}/{qr}`; legacy paths are
   `…/Day14_2-7-2025FastScanner/A2R61V978O.h5`. The 10-char code is `qr_code`, and
   `cyl_scans_extended` is selectable by `plant_qr_code`.
4. **Scans and plants differ.** Wheat: 170 videos, 125 distinct QR codes. Plants are
   imaged at multiple ages, and at Day 11 by both the Fast and Slow scanner. Deriving
   `n_plants` from video count would overcount by 36%.
5. **`skeletons.yaml` cannot represent the corpus.** `cyl_arabidopsis…primary_6nodes`
   and `plate_arabidopsis…primary_8nodes` are both arabidopsis primary with different
   node counts, and the table has no `mode` key. Wheat, sorghum, medicago and alfalfa
   have no rows at all. Its own header states that verifying against these eight
   collections is what flips its `verified:` flags.

## Architecture

Three sources, two independent derivations, one reconciliation.

```
  W&B registry v0 ──┐
   (digest, metadata)│
                     ├──▶ [1] Verify ──▶ [2] Read ──▶ [3] Parse ──┐
  Z: share file ─────┘         digest       sleap_io     filenames │
   (.slp)                       gate                               ├──▶ [5] Reconcile ──▶ [6] Emit
                                                                   │
  Bloom prod ──────────────────────────────▶ [4] Resolve ──────────┘
   (cyl_scans_extended)                       by qr_code
```

1. **Verify** — compare the W&B `v0` file digest against the mapped share file. A
   mismatch halts that collection; nothing downstream runs on unverified bytes.
2. **Read** — `sleap_io.load_slp` yields `skeleton_name`, `node_names`, `node_count`,
   `n_frames`, `n_instances`, and the video list.
3. **Parse** — each video path yields `(qr_code, day, date, scanner)`.
4. **Resolve** — look those `qr_code`s up in `cyl_scans_extended`, yielding `scan_id`,
   `species_name`, `plant_id`, `plant_age_days`, `experiment_id`, `experiment_name`,
   `accession_id`, `genotype`, `date_scanned`.
5. **Reconcile** — each scan row is **agreed**, **disagreed**, or **unresolved**.
6. **Emit** — four artifacts (below).

### Required properties

- **Read-only against prod.** `bloomctl cyl` exposes `ingest`; nothing here touches it.
- **Idempotent.** Re-running produces identical output for unchanged inputs.
- **Per-collection isolation.** One collection failing verification does not block others.
- **Aggregates come only from agreed rows.** A collection reports
  "170 scans, 12 unresolved" rather than "170 scans" with a footnote.
- **Human gate on exceptions.** The run **stops** before emitting final aggregates and
  surfaces every unresolved and disagreed row for adjudication. No collection gets a
  finished card until its exceptions are resolved by a person.

## Deliverables

| # | Artifact | Format | Answers |
|---|---|---|---|
| A | Per-scan table, one per collection | CSV | what is actually in each collection |
| B | Aggregate mapping, all collections | YAML | the `LabelCard` fields #49's §2 consumes |
| C | `skeletons.yaml` diff | Markdown | which rows verify, contradict, or are missing |
| D | Model inventory | CSV + Markdown | what is trained, where, and its status |

### A. Per-scan table

One row per video, columns grouped so the provenance of each *field* is visible:

```
from filename   qr_code, day_from_name, date_from_name, scanner, video_path
from .slp       n_frames, n_instances
from Bloom      scan_id, plant_id, species_name, plant_age_days,
                experiment_id, experiment_name, accession_id, genotype, date_scanned
reconciliation  status (agreed|disagreed|unresolved), notes
```

Bloom-derived column names match `bloomctl`'s `CSV_COLUMNS` exactly, so these join to
`scans.csv` and to new-package manifests without translation.

### B. Aggregate mapping

```yaml
- collection: wheat_5-14DAG_seminal_6nodes_labels
  verification:
    v0_digest_match: true
    share_path: Z:\users\eberrigan\SLEAP\20250529_…\labels_sr_5-14DAG.v004.slp
    recorded_data_path: D:/SLEAP/20250529_…/labels_sr_5-14DAG.v004.slp
  card:
    species: wheat            # from Bloom species_name, not the collection name
    mode: cylinder
    root_type: crown
    age_min: 5
    age_max: 14
    skeleton_name: Skeleton-2   # literal from the file; see Open Question 3
    node_count: 6
    node_names: [r1, r2, r3, r4, r5, r6]
    n_frames: 7521
    n_instances: 24760
    n_scans: 170
    n_plants: 125
    images_embedded: true       # describes the linked v1, which is what consumers get
  provenance:
    source_sha256: …
    sleap_io_version: 0.7.1
    experiment_ids: […]
  reconciliation: {agreed: 170, disagreed: 0, unresolved: 0}
  confidence: {species: verified, age_min: verified, n_plants: verified, …}
```

`species` comes from Bloom, never from the collection name — that is the independent
check. `confidence` is per-field, because a collection can have a verified species and an
inferred `n_plants` simultaneously.

### C. `skeletons.yaml` diff

Per collection: which existing row it **verifies**, which it **contradicts**, and which
rows are **missing**. Reports only — the schema change is proposed separately.

### D. Model inventory

One row per trained model found, with a **status**:

- **production** — reachable via `model_selection.yaml` / the chooser (currently 13,
  across arabidopsis, canola, pennycress, rice, soybean).
- **in development** — trained on the share or in W&B `sleap-roots`, not promoted
  (receptive-field sweeps, generalizability experiments, both `seminal_root_generalist`
  folders).
- **superseded** — an earlier version of a model that has a later one.
- **unclassified** — needs a human call.

Columns: `model_id, species, mode, root_type, age_band, n_frames, path_or_run,
registered (bool), status, notes`.

## Consumers

- **#49's §2** consumes B directly. Its archaeology tasks collapse to reading a verified
  file rather than gathering evidence, and D7's "unrecoverable fields" premise is
  retired — `n_frames`, `n_instances`, `n_scans`, `n_plants`, `age_min`/`age_max`,
  `skeleton_name`, `node_count` and `node_names` are all recoverable.
- **Visualisation** consumes A, which is why it is per-scan and CSV.
- **#3** is informed by D — the deferred arabidopsis plate models.
- **`skeletons.yaml`** is corrected by a follow-up change informed by C.

## Testing

The audit is a data-producing script, so tests target the deterministic parts:

- Path mapping (`D:` / UNC / `Z:` → share path) — unit, table-driven.
- Video-path parsing to `(qr, day, date, scanner)` — unit, including the malformed and
  scanner-suffixed cases seen in the corpus.
- Reconciliation classification — unit, with synthetic agreed / disagreed / unresolved
  rows; specifically that aggregates exclude non-agreed rows.
- Digest verification — unit, with a deliberate mismatch asserting the collection halts.
- Bloom access is behind an injectable client so the default suite runs offline, matching
  `registry/publish.py`'s `api=None` seam. Any live-Bloom test is
  `@pytest.mark.integration` (registered in `pyproject.toml`, filtered by `ci.yml`).

## Risks

- **Prod credentials.** The work reads prod Bloom with `~/.bloom/credentials.txt`. Read
  paths only; no ingest. Worth a second pair of eyes on the code before first run.
- **Share walk breadth.** ~30 project folders, some with abandoned experiments. D's
  `unclassified` status exists so judgement calls surface rather than being guessed.
- **Scope creep into fixes.** This effort reports. Every correction it implies
  (`skeletons.yaml` `mode` key, new species rows, #3, tip models) is a separate change.
- **Bloom coverage.** Legacy scans may predate Bloom ingestion; those become `unresolved`
  rather than errors. (Re-keying is *not* a failure mode here — eberrigan, 2026-09-11. An
  earlier draft of this bullet named it and the term was never defined.)

## Decisions (resolved 2026-09-02, eberrigan)

1. **Tip models: inventory, do not classify.** Deliverable D lists them with `root_type`
   blank and `status: unclassified`, so they are visible and counted without putting a
   contract change on the audit's critical path. File a separate issue for the `RootType`
   gap. Note there is currently **zero prior art** for tip models anywhere in
   `src/`, `docs/`, or `openspec/` across these repos.
2. **Alfalfa: include, flag for widening.** Walk alfalfa folders and report what is
   there, flagging that it needs the label-side species widening. `SPECIES_VOCAB` is
   `{soybean, canola, pennycress, arabidopsis, rice}`; #49's D5 already proposes adding
   wheat, sorghum and medicago label-side, and alfalfa would be a fourth. Report-only —
   this effort does not edit that vocabulary or #49.
3. **Share walk boundary: structural filter.** Walk every folder under
   `Z:\users\eberrigan\SLEAP`, but inventory only those containing a **top-level labels
   file** — the superset-per-collection rule. Abandoned and scratch folders drop out
   without a judgement call, and the filter is reproducible rather than a hand-maintained
   list that would only encode what we already remember.
4. **Artifacts: repo now, W&B later.** Commit them to this repo so they are reviewable in
   the PR and diffable over time. W&B publishing is a follow-up once the shape has
   settled. This matches what #49's §2 already expects and keeps the change
   self-contained.
5. **`skeleton_name`: record the literal value and flag it.** Files carry inconsistent
   values — real ones like `soybean_primary`, auto-generated ones like `Skeleton-2`. The
   literal goes in deliverable B; deliverable C carries the diff against
   `skeletons.yaml`. No silent normalisation.

## Resolved by execution

- **Sorghum crown, wheat primary/crown age split.** Named in the expected corpus but
  absent from every current table. Whether collections exist is answered by the walk
  itself, so it is an output rather than a prerequisite.

## Change split

Two OpenSpec changes, per repo convention (one change per PR) and because they have
different consumers:

- **Change 1 — label corpus inventory.** Deliverables A, B, C. Feeds #49's §2 directly.
- **Change 2 — model inventory.** Deliverable D. Feeds #3 and the roadmap.

They share the share walk but land independently. Framed as a **re-runnable capability**
("the repo can inventory and verify its label corpus against the registry, the share, and
Bloom"), not a one-time script — anything one-shot rots the moment a ninth collection
appears.
