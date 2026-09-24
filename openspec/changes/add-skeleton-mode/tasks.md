## Rules for every group

Each behaviour lands as a **RED** commit (failing tests), then a **GREEN** commit that makes
them pass. CI must be green after every GREEN commit. RED commits stay local until their GREEN
commit exists, so push only at GREEN points.

- **Evidence in the RED commit body.** Paste the `uv run pytest -rf` failure lines: the test
  ids and the assertion or `ValueError`. No CI run will exist for a RED commit, and squash-merge
  keeps only commit text.
- **Fail for the intended reason.** Each RED commit includes at least one behaviour-level
  failure (`DID NOT RAISE`, a wrong value, a missing report heading), not only a `TypeError`
  from a missing keyword.
- **Characterisation tests.** A RED commit may include tests that already pass. Name them in
  the body as characterisation tests.
- **No collection errors.** A RED commit adds no new top-level imports. Build `SkeletonRow`s
  and two-mode tables inside test functions (YAML plus `load_skeleton_table(write_table(...))`),
  not as module constants or `parametrize` arguments. Reach new names as attributes
  (`gap.ModeGap`, `report.mode_gaps`), so a missing name fails one test, not the module.
- **Lint.** RED commits must pass `black --check` and `ruff check`.

## 1. Table mode key (`Skeleton Table Mode Key`)

- [ ] 1.1 RED — `test(labeling): pin the skeleton table's mode key (RED)`
  - Add `mode: cylinder` to every packaged `skeletons.yaml` row and to every inline YAML
    fixture. The loader ignores unknown keys, so the existing tests stay green.
  - In `tests/test_labeling_skeletons.py`, add:
    - `test_a_row_without_a_mode_is_rejected`: row 0 is valid and row 1 lacks `mode`. It
      matches `"row 1: missing required key 'mode'"`.
    - `test_an_unknown_mode_lists_the_vocabulary`: `mode: plates`. It asserts every item of
      `sorted(MODE_VOCAB)` is in the message.
    - `test_multiplant_cylinder_is_a_valid_table_mode`: a characterisation test.
    - `test_one_key_in_two_modes_is_not_a_duplicate`
    - `test_a_pair_may_be_agnostic_in_one_mode_and_split_in_another`
  - Tighten the existing duplicate and shadow tests to put both rows in one mode, and to
    assert that the message names the mode.
- [ ] 1.2 GREEN — `feat(labeling): key the skeleton table on capture mode (GREEN)`
  - In `skeletons.py`:
    - Add `SkeletonRow.mode: str`, second after `species`.
    - `_parse_table` requires `mode` and validates it against `MODE_VOCAB`.
    - The dedup key becomes `(species, mode, root_type, age)`.
    - The shadow check applies per `(species, mode, root_type)`.
    - Messages name the mode.
  - Add `mode="cylinder"` to the `SkeletonRow` in `tests/test_inventory_gap.py`, since the
    commit that changes the signature fixes its callers.
  - Update the module, `SkeletonRow` and `_parse_table` docstrings.

## 2. Mode-aware lookup (`Mode-Aware Skeleton Lookup`)

- [ ] 2.1 RED — `test(labeling): pin that lookup refuses to pick a capture mode (RED)`. Tests
  run against an injected two-mode table:
  - `test_an_omitted_mode_is_ambiguous_with_or_without_an_age`: no age, `age=3` and `age=9`.
    Each raises, matching `r"cylinder.*plate"` and `"mode="`. This is a behaviour-level RED.
  - `test_an_omitted_mode_with_one_mode_is_unchanged`: a characterisation test.
  - `test_a_given_mode_with_no_row_names_the_existing_modes`:
    `mode="multiplant cylinder"` names `cylinder`.
  - `test_a_given_mode_for_an_uncovered_pair_fails_as_before`: pennycress with
    `mode="plate"` raises the existing no-row message.
  - `test_an_age_split_mode_without_an_age_lists_only_that_modes_windows`
  - `test_the_unverified_warning_names_the_mode`
- [ ] 2.2 GREEN — `feat(labeling): make lookup_skeleton mode-aware (GREEN)`
  - Add `mode` as a keyword-only parameter.
  - Order the checks:
    1. The pair is absent entirely: raise the existing error.
    2. A mode is given: filter to it, or raise naming the modes that exist.
    3. No mode is given and more than one mode matches: raise.
    4. Otherwise, apply the existing age logic within the chosen mode.
  - The warning names the mode. The docstring's Args and Raises cover the mode cases.

## 3. Gap report matches on mode (`Skeleton Table Mode Gap`)

This comes before the plate row lands, so no test depends on row order under the old
mode-blind `gap.py`.

- [ ] 3.1 RED — `test(inventory): pin the gap report's match on mode (RED)`
  - In `tests/test_inventory_gap.py`, every test uses an injected table built in the test:
    - `test_an_observed_mode_with_no_row_is_reported`: a 3-node plate lateral family
      against a cylinder-only lateral row.
    - `test_a_mode_with_its_own_row_is_not_a_gap`
    - `test_an_uncovered_species_is_not_a_mode_gap`: medicago plate.
    - `test_a_covered_species_whose_root_type_has_no_row_is_neither`: rice lateral plate.
    - `test_a_mode_gap_aggregates_node_counts_across_families`: 3 and 4 nodes.
    - `test_a_disagreeing_node_count_is_reported`: 8 and 7 nodes against an 8-node plate
      row.
  - Remove `test_two_capture_modes_select_one_row`, whose premise this change removes.
  - In `tests/test_inventory_emit.py`, replace
    `test_the_mode_collision_section_is_rendered` with a test that asserts the two new
    headings and their lines against the report bytes.
- [ ] 3.2 GREEN — `feat(inventory): report modes with no row and disagreeing node counts
  (GREEN)`
  - In `gap.py`, replace `ModeCollision`/`mode_collisions` with:
    - `ModeGap(species, root_type, mode, table_modes, node_counts, paths)`/`mode_gaps`
    - `NodeCountDisagreement(species, mode, root_type, row_node_counts, observed, paths)`/`node_count_disagreements`
  - In `emit.py`, render them under "Capture modes with no row" and "Node counts that
    disagree with their row".
  - Update the docstrings and comments that describe the old finding: `gap.py:1-8`, which
    drops its `skeletons.py:327` citation, and the ones near `:225`, `:271` and `:292`;
    `emit.py:119`; and `tests/test_inventory_gap.py:1-7`.

## 4. Committed rows (`Committed Skeleton Rows Carry Their Mode`)

- [ ] 4.1 RED — `test(labeling): pin the committed plate row against the scan (RED)`
  - `test_every_transcribed_row_is_cylinder`
  - `test_the_plate_row_is_unverified`
  - `test_the_plate_lookup_has_exact_bounds`: ages 1, 2, 7 and 8, with 2 and 7 giving 8
    nodes. Also check that `mode="cylinder"` gives 6.
  - `test_the_plate_row_agrees_with_the_committed_scan`:
    - Read `Path(__file__).resolve().parents[1] / "inventory" / "label-inventory.csv"` with
      `newline="", encoding="utf-8"`.
    - Fail if it is absent.
    - Keep rows where `user_instances > 0` and `node_count` is non-empty, compared with
      `int()`.
    - Assert a strict plurality for the row's count.
  - In `test_the_doc_table_is_transcribed_faithfully`, pass `mode="cylinder"`. Its docstring
    points to the Box snapshot, not the in-repo file.
  - Re-key `test_the_table_records_which_rows_are_verified` on `(species, mode, root_type)`.
- [ ] 4.2 GREEN — `feat(labeling): add the arabidopsis plate primary skeleton row (GREEN)`
  - Add `arabidopsis / plate / primary / "2, 3, 4, 5, 6, 7" / 8 / verified: false`, after
    the cylinder arabidopsis rows.
  - Correct the `skeletons.yaml` header:
    - Sources: the cylinder rows come from the command doc, the plate row from the
      committed CSV.
    - Arabidopsis plate primary is not transcribed, but it is still unverified.
    - Rice and arabidopsis plate both split by age.
    - Cite roadmap *Open roadmap decisions* rather than `:422`.
  - Record the open questions in the header: the 7-node and 6-node families, DAP versus DAG,
    and the shared skeleton name. State the evidence as the invariant the test enforces, not
    as hard-coded counts.
  - Update `SkeletonRow.age`'s "Only rice splits by age". Update the test module docstring
    (`:3-7`).

## 5. Builder uses the package mode (`Labeling Packages Use Their Own Mode`)

- [ ] 5.1 RED — `test(labeling): pin that packages look up their own mode (RED)`
  - Add a `node_counts=` parameter to `tests/conftest.py`'s `download`/`build_package_dir`,
    defaulting to today's 6 and 4, so existing callers are unchanged.
  - In `tests/test_labeling_build_package.py`:
    - `skeleton_for(..., mode="plate")` over ages 3-5 gives 8 nodes, and
      `mode="cylinder"` gives 6.
    - `test_skeleton_for_without_a_mode_is_not_possible`: `mode` is a required argument.
  - In `tests/test_labeling_package.py`:
    - An orchestrator build with `mode: plate`, `root_types=("primary",)` and 8-node
      predictions writes 8 nodes into the `.slp` and into `package_metadata.yaml`, and
      `validate_package` passes. This is a behaviour-level RED: it fails on the 6-node row.
    - A soybean `mode: "multiplant cylinder"` build raises naming `cylinder`, and neither
      the output directory nor a `*.partial-*` directory exists.
- [ ] 5.2 GREEN — `feat(labeling): build each package against its own capture mode (GREEN)`
  - `skeleton_for(species, root_type, ages, mode)` passes `mode` through, from
    `build_package.py:477` and `package.py:226`.
  - Update `skeleton_for`'s docstring: Args and Raises gain mode, and "splits rice by age"
    becomes "splits by age".

## 6. Integration test (#61)

- [ ] 6.1 `fix(tests): query the labels registry as datasets and pass each collection's mode (#61)`
  - Use `inventory.verify._LABELS_ARTIFACT_TYPE`, not `"model"`.
  - Use an explicit literal map from collection name to `(mode, age)`:
    `plate_arabidopsis_2-7DAG_primary_8nodes_labels` maps to `("plate", 2)`, and
    `cyl_arabidopsis_7-11DAG_primary_6nodes_labels` maps to `("cylinder", None)`. Any
    other collection gets `(None, None)`, so an ambiguous pair is reported rather than
    guessed.
  - The plate files name their skeleton `Skeleton-N`, so that collection is expected to be
    reported as unparseable. Say so in the docstring.
  - Extract the per-collection resolution (name, then `(mode, age)`, then the lookup, then
    the mismatch line) into a helper. Unit-test it in CI with fake names, and with
    `wandb.Api` monkeypatched to assert that `artifact_collections` receives `"dataset"`.
  - Run it locally with `SLEAP_ROOTS_LABEL_SKELETON_CHECK=1` if credentials allow, and paste
    the result into the PR, or state "not run". Its CI workflow has no `WANDB_API_KEY`, so
    a green check there is not evidence.

## 7. CI, docs, verification

- [ ] 7.1 `ci(tests): run the suite when the committed inventory changes`: add `inventory/**`
  to both path lists in `.github/workflows/ci.yml`.
- [ ] 7.2 `docs(labeling): the skeleton table's mode key`. Each of these files gets its own
  edit:
  - `README.md:137-140`: the gap is now history, and the report lists modes with no row.
  - `docs/labeling-packages.md:90-92` and `.claude/commands/build-labeling-package.md:156`:
    the key is `(species, mode, root_type)`, age splits apply to rice and arabidopsis
    plate, and the build uses `--mode`.
  - `docs/roadmap.md:235-243`: step 1 has shipped (#58) and its headline is closed. Step 2
    has an unsolved prerequisite: mode is underivable for 515 of 611 labelled families.
  - `docs/CHANGELOG.md`: add a `### Changed` first bullet with the breaking calls and the
    stale committed report. Amend `### Added`'s #58 sentence to say "since closed".
- [ ] 7.3 Run CI's gate: `uv run black --check src/sleap_roots_training tests && uv run
  ruff check src/sleap_roots_training && uv run pytest -m "not integration"
  --cov=src/sleap_roots_training --cov-fail-under=95`.
- [ ] 7.4 Run `openspec validate add-skeleton-mode --strict` on
  `npx -y @fission-ai/openspec@1.5.0` and `@1.11.0`, and paste both into the PR body.
- [ ] 7.5 Reconcile the implementation against `proposal.md` and both specs. Any deviation
  gets a `### Why N instead of M?` note in `proposal.md`.
- [ ] 7.6 At archive, which happens in its own PR, replace the new `labeling-skeletons`
  spec's placeholder Purpose. 1.11.0 `--strict` rejects the placeholder.
