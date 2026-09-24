## Why

`skeletons.yaml` is keyed `(species, root_type, age)` and has no `mode`, so it cannot tell
a cylinder arabidopsis primary skeleton (6 nodes) from a plate one (8 nodes).
`lookup_skeleton` returns the single `arabidopsis/primary` row for both. A plate package
built today would ship a 6-node skeleton, and the result would look fine and be
uncombinable with the 8-node plate corpus. This is the headline finding of the label
inventory (#58), and it blocks a labels registry keyed `(species, mode, root_type)`.

eberrigan approved the shape of the fix on 2026-09-23. This change implements exactly that
and nothing more. It deliberately does not solve deriving `mode` for the 515 of 611
labelled families whose paths carry no mode token; see *Out of scope*.

## Evidence

All numbers are from the committed scan `inventory/label-inventory.csv` (656 families, #58).
Nothing is re-scanned.

- **Arabidopsis plate primary, by node count:** 15 families at **8 nodes**, 4 at 7, and 5
  at 6.
  - The 8-node families are the canonical ones:
    `labels_plates_arabidopsis_primary_2-7DAP_8nodes.v006` through `.v010` (3,032 user
    instances each), plus the `primary_8nodes/` and `primary_root_8nodes/` copies.
  - The 7-node families are all early versions in one directory,
    `primary_root_8nodes/7_dap/labels/labels.v00{2,4,5}*` (92 user instances).
  - The 6-node families are `labels_wheat_2-3DAG*`: wheat files misfiled under the plate
    tree.
- **Arabidopsis cylinder primary:** 1 family, at 6 nodes. This matches the existing
  transcribed row.
- **The registry already names the plate window.** The labels registry holds
  `plate_arabidopsis_2-7DAG_primary_8nodes_labels` (#11's collection table). So the team
  writes this window as **DAG**, which is also the unit of the table's `age` column. The
  scan shows these families as `unregistered` only because registry matching is by
  filename, and the registered file was re-embedded under another name (a limitation #58
  already states).

The 7-node and 6-node families are **stated, not acted on**. The tool does not decide
whether the 7-node files are an abandoned draft of the 8-node skeleton. That is recorded
in the table's comment for a person to settle.

## What Changes

- **`skeletons.yaml`**
  - Gains a **required `mode` column**, validated against `chooser.MODE_VOCAB` (sourced
    from `sleap_roots_contracts.Mode`).
  - Every existing row becomes `mode: cylinder`. Its provenance, the
    `/build-labeling-package` onboarding doc, covers cylinder only.
  - Gains one row: `arabidopsis / plate / primary`, `age: "2, 3, 4, 5, 6, 7"`,
    `node_count: 8`, `verified: true`.
  - The header states the evidence and the unresolved 7-node files.
- **`_parse_table` (skeletons loader)**
  - A row missing `mode`, or with a mode outside the vocabulary, fails with its row
    number.
  - Duplicate detection keys on `(species, mode, root_type, age)`.
  - The "age-agnostic row shadows an age-split one" check keys on
    `(species, mode, root_type)`. So a cylinder row with `age: null` and a plate row split
    by age can coexist for the same pair.
- **`SkeletonRow`** gains `mode: str`.
- **`lookup_skeleton(species, root_type, age=None, table=None, mode=None)`**
  - `mode` is optional. When it is omitted and rows of **more than one mode** match
    `(species, root_type)`, the call raises `ValueError` naming the modes, **rather than
    picking one**.
  - When it is omitted and only one mode matches, behaviour is unchanged.
  - When a mode is given and no row of that mode exists, it raises and names the modes
    that do exist.
  - The unverified-row warning names the mode.
- **Labeling package builder:** `build_package.skeleton_for` and its `package.py` caller
  pass the package's own `mode`. That is `PackageMetadata.mode`, set from the required
  `--mode` CLI option, validated against `MODE_VOCAB` and already recorded in
  `package_metadata.yaml`. No new input.
- **Label inventory's gap report:** now matches rows on mode.
  - The "rows two capture modes both select" finding can no longer occur. It is replaced
    by **"capture modes observed with no row of their own"**.
  - On the committed scan, that new finding would name `(arabidopsis, plate, lateral)`:
    10 families, all 3 nodes, and no plate lateral row.
  - `label-inventory`'s `Skeleton Table Keying Gap`, which stated that `lookup_skeleton`
    has no mode, is REMOVED and replaced by an ADDED `Skeleton Table Mode Gap`. 1.11.0
    refuses a MODIFIED block that drops a scenario, and keeping the old scenario's name
    with the opposite meaning would mislead.
- **Published-collections integration test:**
  - Queries `type="dataset"` instead of `"model"`. With `"model"` it could never have
    passed; this closes #61.
  - Passes a mode for the two collections whose names carry one, from an explicit
    literal map: `plate_arabidopsis_2-7DAG_primary_8nodes_labels` → `plate`,
    `cyl_arabidopsis_7-11DAG_primary_6nodes_labels` → `cylinder`. There is no name
    parsing.

## Decisions

- **Why raise instead of defaulting to cylinder?** A default is picking. It is the silent
  wrong answer this change exists to remove, and it would make a plate package built
  without `--mode` pass. Callers that know their mode pass it; the builder always does.
- **Why is `mode` required in the YAML rather than defaulting to `cylinder`?** For the same
  reason: a missing mode is a table error, reported with its row number.
- **Why is the plate row age-split at 2–7?** The evidence covers exactly 2–7, and the
  registry collection names that window in DAG. A lookup at day 8 fails with the covered
  window listed, rather than claiming a node count nothing has shown.
- **Why doesn't the gap report also flag node-count disagreement within a mode (the 7-node
  files)?** It would be a new finding kind, and this change adds none. The disagreement is
  written into the table's comment instead.

## Out of scope

- **Deriving `mode` for families whose paths carry no token (515 of 611).** It is a
  prerequisite for the registry backfill (#11/#49) and is not solved here. No heuristic
  is proposed.
- **Mixed-species label files (#59)** and **the missing package age window (#60).** Both
  were found while scoping this change and are filed separately.
- **Tier 2.7 skeleton unification.** This table stays descriptive of the native
  skeletons.

## Impact

- **Affected specs:**
  - `labeling-skeletons`: a new capability, with ADDED requirements. No spec covered the
    table before; it lived only in `add-labeling-package-generator`'s design.md
    Decision 7.
  - `label-inventory`: one requirement REMOVED and its replacement ADDED.
- **Affected code:**
  - `src/sleap_roots_training/labeling/data/skeletons.yaml`
  - `src/sleap_roots_training/labeling/skeletons.py`
  - `labeling/build_package.py`
  - `labeling/package.py`
  - `inventory/gap.py`
  - `inventory/emit.py` (the report section heading and wording)
- **Affected tests:**
  - `tests/test_labeling_skeletons.py`
  - `tests/test_inventory_gap.py`
  - `tests/test_inventory_emit.py`
  - `tests/test_labeling_build_package.py`
- **Breaking for callers:**
  - `lookup_skeleton("arabidopsis", "primary")` without a mode now raises.
  - `SkeletonRow(...)` needs `mode=`.
  - Every in-repo caller is updated. There are no out-of-repo callers: the package is
    unpublished for this module.
- **Reproducibility:** `skeleton_table_sha256` changes, which is the intended signal. A
  package built before this change records the old SHA and stays distinguishable.
- **Sequencing:** stacked on `chore/archive-add-label-inventory`, which archives #58's
  change so this one can amend `label-inventory`.
