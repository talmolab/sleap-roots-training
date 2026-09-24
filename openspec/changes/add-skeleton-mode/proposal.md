## Why

`skeletons.yaml` is keyed `(species, root_type, age)` and has no `mode`. So `--mode plate`
is accepted today, and an arabidopsis primary package gets the 6-node cylinder skeleton
instead of the 8-node one the plate corpus uses. This was the label inventory's headline
finding (#58). It blocks a labels registry keyed `(species, mode, root_type)`.

## Evidence

Every number here comes from the committed scan `inventory/label-inventory.csv` (#58). Nothing
is re-scanned. "Labelled" means `user_instances > 0`.

- **Arabidopsis plate primary: 24 families.**
  - **15 at 8 nodes.** Nine are the `labels_plates_arabidopsis_primary_2-7DAP_8nodes` lineage
    and its copies (3,032–3,186 user instances). They are v006, v008 and v010 with their
    `uncropped` variants, plus copies under `primary_8nodes/`, `primary_root_8nodes/`,
    `primary_root/` and `0908-0901_plates/`. The other six are IAA-experiment and
    prediction-copy files (0–122).
  - **4 at 7 nodes.** These are `labels.v00{2,4,5}*` under `primary_root_8nodes/7_dap/labels/`,
    a directory that also holds 8-node files. Three have 92 user instances; one has 0.
  - **5 at 6 nodes.** Four are named `labels_wheat_2-3DAG*`. The fifth is `day2and3 copy.slp`,
    which has the same 131 user instances as `labels_wheat_2-3DAG.slp`.
- **Arabidopsis cylinder primary:** 1 family, at 6 nodes.
- **Arabidopsis plate lateral:** 10 families, all at 3 nodes. The table has no plate row for
  it.
- **The registry names the plate window in DAG.** The labels registry holds
  `plate_arabidopsis_2-7DAG_primary_8nodes_labels` (#11's collection table). The files
  themselves say **DAP**. This change adopts the registry's DAG reading, which is also the
  unit of the table's `age` column. **It does not establish that DAP 2–7 equals DAG 2–7**;
  that is left for a person to settle.

The inventory derives species and mode from file and directory names. It reads node counts
from the files, but it cannot read node names here: every plate file names its skeleton
`Skeleton-N`.

## What Changes

- **`skeletons.yaml`** gains a required `mode` column. Every existing row becomes
  `mode: cylinder`. Their only in-repo provenance is `/build-labeling-package`, which builds
  "from a finished cylinder experiment".
- **One new row:** `arabidopsis / plate / primary`, `age: "2, 3, 4, 5, 6, 7"`, `node_count: 8`,
  **`verified: false`**. It is flipped in a later change, once the published-collections check
  can read `plate_arabidopsis_2-7DAG_primary_8nodes_labels`. The header records the evidence
  and the open questions: the 7-node and 6-node families, and DAP versus DAG.
- **BREAKING — `SkeletonRow`** gains a required `mode: str`, and the loader validates it
  against `chooser.MODE_VOCAB` (`Skeleton Table Mode Key`).
- **BREAKING — `lookup_skeleton(..., mode=None)`** raises rather than picking when rows of more
  than one mode match (`Mode-Aware Skeleton Lookup`). So `lookup_skeleton("arabidopsis",
  "primary")` now raises.
- **BREAKING — labeling packages** look up their skeleton with their own `--mode`
  (`Labeling Packages Use Their Own Mode`). A `plate` or `multiplant cylinder` package for a
  pair with no row in that mode used to silently get the cylinder skeleton. It now fails
  before anything is written. No multiplant-cylinder rows exist, and none are added here
  (#62).
- **BREAKING — the inventory gap report** matches rows on mode (`Skeleton Table Mode Gap`,
  replacing `Skeleton Table Keying Gap`). `ModeCollision` and `GapReport.mode_collisions`
  are removed. It reports:
  - Modes observed with no row of their own. On the committed scan, the only one is
    `(arabidopsis, plate, lateral)`.
  - Observed node counts that disagree with the matched rows: `(arabidopsis, plate,
    primary)`, row 8, observed 6 and 7. It prints them and decides nothing.
- **Published-collections integration test (#61):**
  - Queries `type="dataset"`, reusing `inventory.verify._LABELS_ARTIFACT_TYPE`.
  - Passes mode and age from an explicit literal map for the two mode-bearing collections.
- **CI** gains `inventory/**` in its path filter, so a re-scan that moves the evidence runs the
  test that checks it.

## Decisions

- **Why raise rather than default?** A default is picking. It is the silent wrong answer this
  change removes. For the same reason, `mode` is required in the YAML.
- **Why age-split at 2–7?** The evidence covers exactly 2–7. A day-8 lookup fails and lists
  the window, rather than claiming a node count nothing has shown.
- **Why `verified: false`?** The table's header defines "verified" as checked against a
  published collection's artifacts. The plate evidence is node counts from unregistered
  files, whose mode is read from their names. The arabidopsis cylinder row, which has
  evidence of the same kind, also stays false.
- **Why does the plate row share the skeleton name `arabidopsis_primary` with the cylinder
  row?** `to_skeleton()` names skeletons `{species}_{root_type}`. The two are told apart by
  node count and by `package_metadata.yaml`'s `mode`. Renaming is out of scope.

## Out of scope

- **Deriving `mode` for the 515 of the 611 labelled families whose paths carry no mode
  token.** It is a prerequisite for the #11/#49 backfill, it is unsolved, and no heuristic is
  proposed.
- **Multiplant-cylinder rows (#62), mixed-species files (#59), and the package age window
  (#60).**
- **Regenerating `inventory/label-inventory.md`.** It is a generated scan output and is not
  hand-edited. Its "Rows selected by more than one capture mode" section describes the table
  before this change. The next scan replaces it. The CSV has no gap columns and is
  unaffected.
- **Tier 2.7 skeleton unification.**

## Impact

- **Affected specs:**
  - `labeling-skeletons`: a new capability. No spec covered the table; it lived only in
    `add-labeling-package-generator`'s design.md Decision 7. `Labeling Packages Use Their
    Own Mode` belongs to `labeling-package`, which is not archived yet, so it lives here.
  - `label-inventory`: one requirement removed and replaced; see the spec delta.
- **Affected code:**
  - `src/sleap_roots_training/labeling/data/skeletons.yaml`
  - `src/sleap_roots_training/labeling/skeletons.py`
  - `src/sleap_roots_training/labeling/build_package.py`
  - `src/sleap_roots_training/labeling/package.py`
  - `src/sleap_roots_training/inventory/gap.py`
  - `src/sleap_roots_training/inventory/emit.py`
  - `.github/workflows/ci.yml`
- **Affected tests:**
  - `tests/test_labeling_skeletons.py`
  - `tests/test_labeling_build_package.py`
  - `tests/test_labeling_package.py`
  - `tests/conftest.py`
  - `tests/test_inventory_gap.py`
  - `tests/test_inventory_emit.py`
- **Affected docs:**
  - `README.md`
  - `docs/CHANGELOG.md`
  - `docs/labeling-packages.md`
  - `docs/roadmap.md`
  - `.claude/commands/build-labeling-package.md`
- **Callers:**
  - Every in-repo caller is updated.
  - sleap-roots-training is not on PyPI. No talmolab repo other than this one calls
    `lookup_skeleton`; checked in `sleap-roots-predict` and `sleap-roots-contracts`.
  - Open PR #49 adds skeleton rows and fixtures, and will need `mode:` when it rebases.
- **Reproducibility:** `skeleton_table_sha256` changes, which is the intended signal. Nothing
  pins its value.
- **Sequencing:** the archive of #58's change merges first. This branch is then rebased onto
  `main`, so it can amend `label-inventory`.
