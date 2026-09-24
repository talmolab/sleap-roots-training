Every behaviour lands as two commits: a **RED** commit of failing tests, then a **GREEN**
commit that makes them pass. Run the RED tests and record the failure before writing the
fix; `git log` must be able to corroborate the red state.

Existing YAML fixtures gain a `mode:` key in the RED commit. The current loader ignores
unknown keys, so this keeps the existing tests passing while the new ones fail.

## 1. Table mode key (`Skeleton Table Mode Key`)

- [ ] 1.1 RED: tests in `tests/test_labeling_skeletons.py` for the four scenarios.
  - A row without `mode` fails, naming its row number.
  - `mode: plates` fails, listing the accepted modes.
  - A cylinder `age: null` row plus a plate age-split row for one pair loads with both.
  - A duplicate `(species, mode, root_type, age)` fails.
  - Add `mode: cylinder` to every inline YAML fixture.
- [ ] 1.2 GREEN: in `_parse_table`, require `mode` and validate it against
  `chooser.MODE_VOCAB`. Key the dedup on `(species, mode, root_type, age)` and the
  agnostic-versus-split check on `(species, mode, root_type)`. Add `SkeletonRow.mode`.

## 2. Mode-aware lookup (`Mode-Aware Skeleton Lookup`)

- [ ] 2.1 RED: tests against an injected two-mode table.
  - An omitted mode raises, naming both modes.
  - An omitted mode with a single mode returns that row.
  - A given mode with no row raises, naming the existing modes.
  - The unverified-row warning names the mode.
- [ ] 2.2 GREEN: `lookup_skeleton(..., mode=None)`. Filter by the given mode first, then
  apply the existing age logic within that mode.

## 3. Committed rows (`Committed Skeleton Rows Carry Their Mode`)

- [ ] 3.1 RED tests:
  - Every row except arabidopsis plate primary is `cylinder`.
  - Against the packaged table: `mode="plate", age=3` gives 8 nodes, `mode="cylinder"`
    gives 6, and `mode="plate", age=8` raises listing 2-7 DAG.
  - Read `inventory/label-inventory.csv` with `csv.DictReader`. Among
    `species=arabidopsis, mode=plate, root_type=primary`, the most common `node_count`
    equals the plate row's. Skip with a reason if the CSV is absent.
  - Update `test_the_doc_table_is_transcribed_faithfully` to pass `mode="cylinder"`.
- [ ] 3.2 GREEN: `skeletons.yaml`.
  - Add `mode: cylinder` to every row.
  - Add `arabidopsis / plate / primary / age "2, 3, 4, 5, 6, 7" / 8 / verified: true`.
  - In the header, state the evidence (15 families at 8 nodes, the registered
    `plate_arabidopsis_2-7DAG_primary_8nodes_labels`) and the unresolved 7-node and
    misfiled 6-node wheat families.

## 4. Builder uses the package mode (`Labeling Packages Use Their Own Mode`)

- [ ] 4.1 RED: in `tests/test_labeling_build_package.py`, `skeleton_for("arabidopsis",
  "primary", [3, 4, 5], mode="plate")` has 8 nodes and `mode="cylinder"` has 6. A build
  through the orchestrator with `mode: plate` metadata writes 8 nodes into
  `package_metadata.yaml`'s `skeletons`.
- [ ] 4.2 GREEN: add `mode` to `skeleton_for`, and pass `metadata.mode` from
  `build_package.py:477` and `package.py:226`.

## 5. Gap report matches on mode (`Skeleton Table Mode Gap`, replacing `Skeleton Table Keying Gap`)

- [ ] 5.1 RED, in `tests/test_inventory_gap.py`:
  - A 3-node plate arabidopsis lateral family against a table with only a cylinder
    lateral row is reported as a mode gap. The finding names the node count and the
    table's modes.
  - Cylinder 6-node and plate 8-node primary families against a two-mode table report no
    gap.
  - Replace `test_two_capture_modes_select_one_row`, whose premise this change removes.
  - Update `test_inventory_emit.py::test_the_mode_collision_section_is_rendered` to assert
    the new section against report bytes.
  - Add `mode=` to injected `SkeletonRow`s.
- [ ] 5.2 GREEN:
  - In `gap.py`, replace `ModeCollision`/`mode_collisions` with
    `ModeGap(species, root_type, mode, table_modes, node_counts, paths)`/`mode_gaps`.
  - Render it in `emit.py` under "Capture modes with no row".
  - Update both module docstrings, which state that `lookup_skeleton` has no mode.

## 6. Integration test (#61)

- [ ] 6.1 Fix `test_the_table_agrees_with_the_published_label_collections`.
  - Query `type="dataset"`.
  - Pass `mode` from an explicit literal map of the two mode-bearing collection names. A
    collection not in the map passes `mode=None`, so an ambiguous pair is reported as a
    mismatch rather than guessed.
  - It is `integration` and CI does not run it. Run it once locally with
    `SLEAP_ROOTS_LABEL_SKELETON_CHECK=1` if credentials allow, and paste the result
    (pass or its mismatch list) into the PR.

## 7. Docs and verification

- [ ] 7.1 Add a `docs/CHANGELOG.md` entry. Update `docs/labeling-packages.md` if it
  describes the table key.
- [ ] 7.2 Run CI's gate: `uv run black --check src/sleap_roots_training tests && uv run
  ruff check src/sleap_roots_training tests && uv run pytest -m "not integration"
  --cov=src/sleap_roots_training --cov-fail-under=95`.
- [ ] 7.3 Run `openspec validate add-skeleton-mode --strict` on both pinned CLIs
  (`npx -y @fission-ai/openspec@1.5.0` and `@1.11.0`) and paste both into the PR body.
- [ ] 7.4 Reconcile the implementation against `proposal.md` and `spec.md` before the PR.
  Any deviation gets a `### Why N instead of M?` note here.
