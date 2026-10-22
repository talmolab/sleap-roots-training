## Why

The label inventory reads a family's species and capture mode off its path. Two of today's
rules give wrong answers on the committed scan, and neither says so.

1. **Today, species comes from the folder first, and this change reverses that.** `derive()`
   takes the `SLEAP_<species>/` directory before it looks at the filename, and a name listing
   several species gets one of them (#59). So `SLEAP_arabidopsis_plates/.../labels_wheat_2-3DAG.slp`
   reads as arabidopsis, and `labels_canola_pennycress_arabidopsis.v015.slp` reads as
   arabidopsis in one directory and medicago in another. After this change, the filename
   decides, the folder is only a fallback, and a name listing several species gets none.
2. **Today, the first mode token wins, and there is no `multiplant` token (#65).** So
   `multiplant_cylinder/` derives `cylinder` and is checked against the single-plant row.

Multi-species label files are never registered as they are. Each is split per species, or the
per-species files that match it are found (eberrigan, 2026-09-24). So the inventory has to list
such a file as needing that. This change fixes derivation and reports what it cannot decide. It
**resolves no file**: that is #59's follow-up, which comes before label backfill step 2
(#11/#49, `docs/roadmap.md`).

A third gap was found while planning the re-scan. The tool refuses to write only when it found
nothing at all. A scan that missed one directory overwrites the committed artifacts, prints a
warning and exits 0, so this change closes that too.

## Evidence

The numbers come from applying the rules below to the paths in the committed
`inventory/label-inventory.csv` (656 families, #58). Nothing was re-scanned. Three of the five
reviewers reproduced them independently. "Labelled" means `user_instances > 0`.

- **228 families change species. All are labelled.**
  - 165 are in `experiments/…` directories whose names list six species
    (`…sorghum_soybean_canola_pennycress_rice_arabidopsis…_on_…soybean…`). Today they all read
    as `sorghum`, the first token. Each filename names one species.
  - 33 become empty because they are multi-species (next bullet).
  - 18 move from a non-crop folder word to their filename's species: 9 from `packages`,
    5 from `circumnutation` (to rice), and 4 from `multiple`.
  - 12 move between crops, and all 12 are flagged `folder-species-differs` (below):
    4 arabidopsis→wheat (`labels_wheat_2-3DAG*`), 3 wheat→rice (`labels_rice_*` under
    `SLEAP_wheat/`), 2 arabidopsis→canola, 2 sorghum→soybean (`soy`) and 1 medicago→canola.
- **33 labelled families are multi-species.** 20 have filenames naming several species
  (#59's table). 13 name none, under `SLEAP_Canola_Pennycress/`, and today silently read as
  `canola`. A barcode cross-reference on #59 suggests at least two of them are pennycress, and
  that one canola-named file is pooled. No determination is made here.
- **12 labelled families in 9 directories have a filename species their folder contradicts.**
- **12 families spell the species glued to `ONLY`** (`labels_ONLYpennycress_primary_6nodes`).
  Their folders already give the same species, so recognising `only<species>` changes no row
  today. It matters where the folder names no crop.
- **Mode.** 0 families carry `multiplant` and 0 name two modes, so the #65 fix changes no row
  today and guards the next scan.
- **The `labeling-skeletons` plate evidence still holds.** `Committed Skeleton Rows Carry
  Their Mode` needs 8 nodes to be the strict plurality among labelled arabidopsis plate primary
  families. Re-deriving gives 13/1/3 at 8/6/7 nodes, down from 13/5/3, because the four wheat
  files leave. `day2and3 copy.slp` names no species and stays arabidopsis by its folder; only
  its images say wheat. A test in this change pins 13/1/3 against the committed CSV, so drift
  shows at PR time, not after the re-scan.

## What Changes

The rules themselves are normative only in the spec delta. Briefly:

- **Species (`Filename-First Species Derivation`).** The stem decides. If the stem names no
  species, the first `SLEAP_<x>` directory decides, or else the first directory naming a
  species. A deciding part naming several species gives no species and the flag
  `multi-species`. `only<species>` is recognised. A single filename species that the deciding
  directory contradicts is kept and flagged `folder-species-differs`.
- **Mode (`Capture Mode Derivation`).** An exact `multiplant` token anywhere in the path
  derives `multiplant cylinder`, the `MODE_VOCAB` spelling, and absorbs any `cyl`/`cylinder`
  token in the path. Several distinct modes give no mode and the flag `ambiguous-mode`. This
  answers #65's "unrecognised mode tokens": `multiplant` is the only mode word derivation
  missed.
- **`Derived`** gains defaulted fields: `species_named`, `species_from` (`filename`, `folder`
  or `None`), `folder_species`, `modes_named` and `flags`. Each is a sorted tuple, except
  `species_from`.
- **Table.** Two columns go after `species_source`: `species_named` (JSON) and `flags`
  (sorted, space-joined). The table does not record which part decided. The report does, for
  multi-species families.
- **Report (`Derivation Findings Are Reported`).** A "Name derivation" section follows
  "Coverage". It states the precedence once and holds three subsections, each omitted when
  empty:
  - "Families naming more than one species"
  - "Folder and filename disagree on species" (one line per directory)
  - "Paths naming more than one capture mode"
- **Gap report (`Skeleton Table Mode Gap`, MODIFIED).** A family is skipped as
  `multi-species` or `ambiguous-mode` rather than `no-species` or `no-mode`. Multi-species
  named crops still count as uncovered. A multiplant family becomes a mode gap against the
  cylinder row, not a false cylinder match.
- **Partial scans (`Deterministic Artifacts`, MODIFIED).** If any directory cannot be listed,
  `emit.build` raises `PartialScan`. The CLI then writes nothing, names the unreadable
  directories relative to the root, and exits non-zero (`click.ClickException`). `PartialScan`
  used to escape as a raw traceback.
- **Docs.** The `skeletons.yaml` plate-row comment, which says the inventory reads "from the
  directory before the filename (#65)", is corrected. So are `gap.py`'s "derivation is open"
  docstring and its misplaced `KNOWN_SPECIES` comment, `emit.py`'s "Species with no row"
  prose, the README's inventory paragraph, `docs/roadmap.md` backfill step 1, and the
  CHANGELOG.

**Compatibility.** The schema change is additive: `Derived` gains defaulted fields, and the CSV
gains columns without reordering. **The values change**: on the next scan 228 families' `species`
changes, 33 of them to empty. That is why the plate plurality is pinned. **BREAKING for the
CLI:** a scan that cannot list every directory now exits non-zero and writes nothing, where it
used to write and exit 0.

## Decisions (eberrigan, 2026-09-24 unless dated)

- The filename takes precedence over the folder. A part naming several species is reported as
  needing a split or its per-species equivalents, never given the first.
- A filename with no species under a folder naming several is multi-species too. It is not
  read from video names in this change (2026-10-15 conversation; the barcode findings are on
  #59).
- `multiplant` maps to `multiplant cylinder`. Multiplant cylinders are arabidopsis only, all
  from Javier, who also labelled single-plant cylinders, so only the literal token counts.
- A path naming more than one mode is skipped as `ambiguous-mode`.
- Multi-species presentation: blank species, the two columns and a report section. Folder
  disagreements are flagged and grouped by directory. `only<species>` is recognised.
- Resolving the multi-species files is a separate follow-up (#59).
- A scan that cannot list every directory writes nothing and exits non-zero (2026-10-15).
  This makes the approved re-scan command safe exactly as written.

### Why "contradicts" requires a known species in the folder

The loose rule, "the folder's derived value differs", flags 195 labelled families. Most sit in
`SLEAP_packages_10-24-23/` or `SLEAP_circumnutation/`, which name no species, or in six-species
`experiments/` directories that include the filename's species. None of those is a
disagreement. The rule here flags 12, every one a real cross-crop placement. Only the deciding
directory is consulted: a species-named subdirectory under a species-less `SLEAP_` directory
is not compared.

## Out of scope

- **Mode for the 515 of 611 labelled families whose paths carry no mode token.** No heuristic
  is added for them.
- **Resolving any multi-species file**, reading species from video barcodes, and a Bloom join
  (#59).
- **#64** waits for LabelCard metadata (#11/#49). **#62** waits until the multiplant files are
  found. **#60** is unrelated.
- **Path parts above the scan root reach `derive()`**, as today. No part of the approved root
  matches a token, but a pytest temp directory can, so the tests avoid it (tasks rules). That
  is #78.
- **CI runs no `openspec validate`** (#80). Both pinned CLIs run locally, and their output goes
  in the PR body.
- **The CSV formula neutralisation is never applied** (#79). That predates this change. The
  two new columns cannot start with a formula character: `species_named` is JSON and `flags`
  are fixed words.

## Impact

- Specs: `label-inventory`.
  - ADDED: `Filename-First Species Derivation`, `Capture Mode Derivation` and `Derivation
    Findings Are Reported`.
  - MODIFIED: `Deterministic Artifacts` keeps all 4 scenarios and adds 1, and its exit-status
    scenario now names partial scans. `Skeleton Table Mode Gap` keeps all 8 scenarios and adds
    3.
  - `labeling-skeletons` needs no delta. Its plurality evidence is projected at 13/1/3.
- Code: `inventory/gap.py`, `inventory/emit.py` and `cli.py` (the `inventory labels` command).
- Tests: `tests/test_inventory_gap.py`, `tests/test_inventory_emit.py`,
  `tests/test_inventory_cli.py` and `tests/test_labeling_skeletons.py`.
- Docs: `README.md`, `docs/CHANGELOG.md`, `docs/roadmap.md` and
  `labeling/data/skeletons.yaml` (a comment only; the rows are unchanged, so
  `skeleton_table_sha256` changes but no lookup does).
- Artifacts: `inventory/` is re-scanned once, after this merges, in its own PR (tasks §7). The
  archive PR follows.
