## Rules for every group

Each behaviour lands as a **RED** commit (failing tests), then a **GREEN** commit that makes
them pass. CI must be green after every GREEN commit. RED commits stay local until their GREEN
commit exists, so push only at GREEN points.

- **Evidence in the RED commit body.** Paste the `uv run pytest -rf` failure lines: the test
  ids and the assertion. No CI run will exist for a RED commit. The squash merge keeps every
  branch commit's body, as long as the merger keeps GitHub's default concatenated message, so
  the PR body says so.
- **Fail for the intended reason.** Each RED commit includes at least one behaviour-level
  failure: a wrong species, a wrong mode, a wrong skip reason, a missing heading, or a write
  that should not have happened. Assert `species`/`mode` *before* `derived.flags` or
  `row["species_named"]`, so the first failure is never an `AttributeError` or `KeyError`.
- **Characterisation tests.** A RED commit may include tests that already pass. Its body names
  them as characterisation tests. The ones known now are listed under each task.
- **No collection errors.** A RED commit adds no new top-level imports. Every module needed
  (`json`, `discover`, `gap`, `emit`, `write_labels`, `build_share_tree`) is already imported.
  Reach `Path` as `gap.Path`. Build every family, `SkeletonRow` and tree inside the test
  function, and reach new names as attributes, so a missing name fails one test, not the module.
- **Derivation tests take no `tmp_path`.** `derive()` reads the family's whole path, and pytest
  names `tmp_path` after the test, so a temp directory can supply a species, mode or root-type
  token. On macOS even the random `/var/folders/<xx>/` segment can come out as `sr`. Groups 1
  and 2 therefore build **relative** families, with no file on disk, through one module-level
  helper added in 1.1:
  `_family(rel)`: `p = gap.Path(rel)`, `parsed = discover.parse_version(p)`,
  `discover.Family(directory=p.parent, stem=parsed.stem, suffix=parsed.suffix)`.
  Groups 3–5 need real files, so their test names and fixture directories carry no species,
  mode or root-type word (`primary`, `lateral`, `crown`, `seminal`, `sr`, `plate`, `cyl`,
  `multiplant`, `soy`) except in the fixture path where the test means it.
- **Lint.** RED commits must pass `black --check` and `ruff check`.
- **Tick as you go.** Each GREEN commit ticks its own group's boxes in this file.
- **uv only.** Every command is `uv run …`, including in subagents.

## 0. Proposal

- [x] 0.1 `docs(openspec): propose update-inventory-derivation`, as approved. The first draft
  (`refine-inventory-derivation`) was never committed, and the review round was folded into it
  before approval. The commit body lists the review's reconciliation entries.
- [x] 0.2 Once `main` has moved, rebase onto it before the first push. The branch was
  fast-forwarded to `469b3e0` on 2026-10-15, and none of #68–#77 touch `inventory/`.
- [x] 0.3 File an issue: "`derive()` tokenises path parts above the scan root". Cite the macOS
  `/var/folders/sr` and pytest `tmp_path` cases. Link it from proposal "Out of scope".

## 1. Species precedence (`Filename-First Species Derivation`)

- [x] 1.1 RED — `test(inventory): pin filename-first species derivation (RED)`. In
  `tests/test_inventory_gap.py`, add the `_family` helper and these tests. Each one calls
  `gap.derive(_family(...))`, and each line below gives what today's code returns, so the
  failure is behaviour-level:
  - `test_the_filename_beats_the_folder`: for
    `SLEAP_arabidopsis_plates/labels/primary_8nodes/labels_wheat_2-3DAG.v002.slp`, assert the
    species is `wheat` (today `arabidopsis`). Then assert `species_from == "filename"`,
    `species_named == ("wheat",)`, `folder_species == ("arabidopsis",)` and
    `flags == ("folder-species-differs",)`.
  - `test_an_alias_in_the_filename_is_read_and_compared`:
    `SLEAP_sorghum/lateral_4nodes/labels_soy_lateral_4nodes.v001.slp` gives `soybean` (today
    `sorghum`) and is flagged `folder-species-differs`.
  - `test_a_glued_only_prefix_is_read_and_a_bare_one_is_not`: under
    `generalizability/x/`, `labels_ONLYpennycress_6nodes.v000.slp` gives `pennycress` (today
    `None`). `labels_7DAP_laterals_ONLY.v007.slp` gives `None` with `flags == ()`.
  - `test_a_filename_naming_several_derives_none`:
    `SLEAP_medicago/primary_root/labels_canola_pennycress_arabidopsis.v015.slp` gives `None`
    (today `medicago`). Assert `species_named == ("arabidopsis", "canola", "pennycress")`,
    `species_from == "filename"`, and `flags == ("multi-species",)`.
  - `test_a_folder_naming_several_derives_none`:
    `SLEAP_Canola_Pennycress/primary_root/AAP_primary_root_labels.v001.slp` gives `None`
    (today `canola`). Assert `species_named == ("canola", "pennycress")`,
    `species_from == "folder"`, and `flags == ("multi-species",)`.
  - `test_an_unnamed_file_falls_back_to_the_folder`: `SLEAP_Soy/lateral/labels.v001.slp`
    gives `soybean`, `species_from == "folder"`, `species_named == ("soybean",)` and
    `flags == ()`. The species is characterisation.
  - `test_an_open_folder_word_is_kept_and_contradicts_nothing`:
    `SLEAP_packages_10-24-23/labels.v001.slp` gives `packages` (characterisation).
    `SLEAP_packages_10-24-23/labels_rice_3do.v001.slp` gives `rice` with no
    `folder-species-differs` (today `packages`).
  - `test_a_folder_naming_the_filenames_crop_among_several_contradicts_nothing`:
    `experiments/x_sorghum_soybean_canola_pennycress_rice_arabidopsis_on_y/labels_rice_3do.v001.slp`
    gives `rice` (today `sorghum`) with `flags == ()`.
  - `test_a_filename_crop_outside_a_pooled_folder_is_flagged`:
    `SLEAP_Canola_Pennycress/primary_root/labels_wheat_5DAG.v001.slp` gives `wheat` (today
    `canola`) and `flags == ("folder-species-differs",)`.
  - `test_a_pooled_nickname_file_derives_no_species`:
    `SLEAP_wheat/seminal/labels_seminal_wheat_5-14DAG_rice_3-10DAG.v005.slp` gives `None`
    (today `wheat`), `flags == ("multi-species",)` and `root_type == "crown"`.
  - Rename the existing `test_wheats_seminal_nickname_derives_the_crown_root_type` to
    `test_wheats_nickname_derives_the_third_row` and move it onto `_family`. Its `tmp_path`
    directory, `test_wheats_seminal_nickname_d0`, supplies `seminal` on its own, so today it
    cannot fail. Characterisation, now meaningful.
  - In `tests/test_labeling_skeletons.py`, add
    `test_the_plate_row_survives_filename_first_derivation`. It re-derives every committed
    CSV row's species with `gap.derive(_family(path))`, where `<ROOT>` becomes the harmless
    token `root`. It counts labelled `(arabidopsis, plate, primary)` families by node count
    and asserts `{8: 13, 6: 1, 7: 3}`, with 8 the strict plurality (today `{8: 13, 6: 5, 7: 3}`).
    `gap` and `discover` are imported inside the test, and the helper is copied locally,
    because that module imports neither.
- [x] 1.2 GREEN — `feat(inventory): read species from the filename before the folder (GREEN)`
  - In `gap.py`:
    - `Derived` gains `species_named`, `folder_species`, `modes_named` and `flags`
      (`tuple[str, ...] = ()`), and `species_from: Optional[str] = None`. They are defaulted
      after `root_type`, so existing constructors keep working.
    - Add the constants `MULTI_SPECIES` and `FOLDER_SPECIES_DIFFERS`.
    - `_species_in(tokens)` returns the distinct `KNOWN_SPECIES` after aliasing, stripping a
      leading `only` from a longer token.
    - `_folder_species(directory)` applies the rule in the spec.
    - Split `derive()` into `_derive_species(...)` and a mode block, so that 2.2 touches only
      the mode.
    - `flags` is always `tuple(sorted(...))`.
  - Docstrings:
    - Rewrite the module docstring's "Derivation is open" paragraph: the stem is a closed
      vocabulary, and only the `SLEAP_<x>` word is open.
    - Move the misplaced comment at lines 52–54 onto `KNOWN_SPECIES`, and correct it: it now
      decides the stem.
    - Correct the `_SLEAP_DIR` comment: these folders also hold other crops and non-crops.
    - `derive()`'s docstring states the algorithm once and cites the requirement name.
  - These stay green unchanged: `test_soy_is_soybean`,
    `test_species_mode_and_root_type_are_labelled_name_derived`,
    `test_an_uncovered_species_is_not_a_mode_gap`,
    `test_mode_is_derived_from_the_whole_path_not_the_last_three_parts`, and
    `test_inventory_emit.py::test_uncovered_tokens_that_are_not_crops_are_separated`, which
    relies on the open `<x>`.

## 2. Mode tokens (`Capture Mode Derivation`, #65)

- [x] 2.1 RED — `test(inventory): pin multiplant and ambiguous mode derivation (RED)`. All
  tests use `_family`:
  - `test_the_one_plant_count_token_is_recognised`:
    `SLEAP_arabidopsis/multiplant_cylinder/primary/labels.v001.slp` (today `cylinder`, #65's
    reproduction) and `SLEAP_arabidopsis/multiplant/primary/labels.v001.slp` (today `None`)
    each give `mode == "multiplant cylinder"` and no `ambiguous-mode`.
  - `test_a_capture_word_apart_from_the_count_token_is_part_of_it`:
    `SLEAP_arabidopsis/cyl_primary/multiplant/labels.v001.slp` gives `multiplant cylinder`
    (today `cylinder`).
  - `test_look_alike_spellings_are_not_recognised`: `SLEAP_Soy/primary_multi-day/` gives
    `None`, `SLEAP_medicago_plates/multiclass_bottomup/` gives `plate`, and
    `SLEAP_multiple_species/cyl/` gives `cylinder`. **Characterisation**: all three pass today.
  - `test_two_capture_words_derive_nothing`: `plates/cyl_primary/labels.v001.slp` and
    `multiplant/plate/labels.v001.slp` each give `mode is None` (today `plate`, `plate`). Their
    `modes_named` are `("cylinder", "plate")` and `("multiplant cylinder", "plate")`, and each
    has `"ambiguous-mode" in flags`.
  - `test_a_capture_word_named_twice_is_one`:
    `SLEAP_arabidopsis_plates/plate_primary/labels.v001.slp` gives `plate` and no flag.
    **Characterisation.**
  - `test_flags_are_sorted`:
    `SLEAP_arabidopsis_plates/plates/cyl_x/labels_wheat_2-3DAG.v001.slp` gives
    `flags == ("ambiguous-mode", "folder-species-differs")`.
  - `test_the_derived_spelling_is_the_contracts`: `"multiplant cylinder" in
    chooser.MODE_VOCAB`, with `chooser` imported inside the test. **Characterisation.**
- [x] 2.2 GREEN — `feat(inventory): recognise multiplant and refuse to pick a mode (GREEN)`
  - Add `AMBIGUOUS_MODE` and `_MULTIPLANT_TOKEN = "multiplant"`.
  - The mode block collects the distinct modes. A `multiplant` token adds
    `multiplant cylinder` and drops `cylinder`. One mode gives that mode. More than one gives
    `None`, `modes_named`, and `AMBIGUOUS_MODE`.

## 3. Gap report skip reasons (`Skeleton Table Mode Gap`, MODIFIED)

- [x] 3.1 RED — `test(inventory): count names that say too much by their own reason (RED)`.
  These use real files via `write_labels(tmp_path / ...)`:
  - `test_a_name_that_says_too_much_is_skipped_by_its_own_reason`: two families,
    `cyl_x/primary_x/labels_canola_pennycress.v001.slp` and
    `SLEAP_arabidopsis/plates/cyl_primary/labels.v001.slp`. Each has a node count. Assert
    `families_skipped_reasons == {"multi-species": 1, "ambiguous-mode": 1}` (today
    `{"no-species": 1, "no-mode": 1}`).
  - `test_a_crowded_capture_family_is_a_gap_not_a_match`: a 6-node
    `multiplant_cylinder/arabidopsis_primary/labels.v001.slp` against
    `_row("arabidopsis", "cylinder", "primary", 6)`. Assert exactly one `ModeGap` with
    `mode == "multiplant cylinder"` and `table_modes == ("cylinder",)`, and no node-count
    disagreement. **Characterisation after 2.2.**
  - `test_pooled_names_still_count_as_uncovered`: two families,
    `cyl_x/primary_x/labels_canola_pennycress.v001.slp` and
    `SLEAP_Canola_Pennycress/cyl_x/primary_x/labels.v001.slp`, against a table without
    pennycress. Assert `"pennycress" in uncovered_species` (today absent) and
    `families_skipped_reasons["multi-species"] == 2`.
- [x] 3.2 GREEN — `feat(inventory): skip multi-species and ambiguous-mode families by name (GREEN)`
  - In `build_report`, a `MULTI_SPECIES` flag replaces the `no-species` reason, and
    `AMBIGUOUS_MODE` replaces `no-mode`.
  - `derived_species` also takes `species_named` from multi-species families.

## 4. Table columns and report sections (`Derivation Findings Are Reported`)

- [ ] 4.1 RED — `test(inventory): pin the derivation findings in the table and report (RED)`.
  In `tests/test_inventory_emit.py`, each test builds a tree under `tmp_path / "share"` with
  `write_labels`, then runs `emit.build` and `emit.write`. Each report assertion slices the
  report from its subsection heading to the next heading. Paths are compared as `/` literals,
  never `str(Path(...))`.
  - `test_the_table_records_named_crops_and_flags`: assert the full 23-column header as a
    literal list inside the test, with `species_named, flags` right after `species_source`.
    Then the multi-species row has `species == ""`,
    `json.loads(row["species_named"]) == ["arabidopsis", "canola", "pennycress"]`, and
    `row["flags"] == "multi-species"`.
  - `test_the_report_states_the_precedence`: the "Name derivation" section says the filename
    is read before the folder.
  - `test_a_pooled_family_is_listed_not_resolved`: one family named by its filename and one
    under `SLEAP_Canola_Pennycress/`. The subsection has one line for each, with the emitted
    path, the sorted named species, and `(filename)` or `(folder)`, in path order. It also
    contains "split per species or matched to per-species files".
  - `test_folder_disagreements_are_grouped_by_directory`:
    - Directory A holds two `labels_wheat_*` families plus an unflagged `labels.v001.slp`.
    - Directory B holds one more flagged family.
    - The subsection has exactly two lines. A's starts `` - `<ROOT>/…/A` `` and contains
      `2 families` and `arabidopsis → wheat`. It also says the filename's species was used.
  - `test_two_capture_words_are_listed`: the subsection names the family and `cylinder, plate`.
  - `test_empty_derivation_findings_emit_no_subsection`: none of the three subsection headings
    appears. **Characterisation.**
  - Redaction: in each of the three subsection tests, neither `str(tmp_path)` nor
    `tmp_path.as_posix()` appears in either artifact. Every backticked path in the
    subsection must start with `<ROOT>/`.
- [ ] 4.2 GREEN — `feat(inventory): report multi-species, folder-disagreeing and ambiguous-mode families (GREEN)`
  - In `emit.py`:
    - `COLUMNS` gains `species_named` and `flags` after `species_source`. `_JSON_COLUMNS`
      gains `species_named`.
    - `Inventory` gains `multi_species`, `folder_disagreements` and `ambiguous_modes`, as
      small frozen dataclasses. They are built in `build()` from the **same** `derived`
      object as the row, so the table and the report cannot disagree. Directories are
      rendered with `redact.emit_path(directory, root).text`.
    - `_render_report` adds "## Name derivation" after "Coverage", with its three `###`
      subsections, path-ordered with sorted inner lists.
    - Qualify the "Species with no row" prose ("Derivation is open by design") to: folder
      names are read openly.
  - Extend the module docstring's "no determination" framing to the new section. The words
    "generated", "decision", "verdict", "adjudicat", "promote" and "override" stay out of the
    report and the emit names (existing tests forbid them).

## 5. Partial scans write nothing (`Deterministic Artifacts`, MODIFIED)

- [ ] 5.1 RED — `test(inventory): refuse to write a scan that missed a directory (RED)`:
  - `test_emit.py::test_a_partially_readable_root_writes_nothing`: a tree with one real
    family. Use the existing `_blind` monkeypatch pattern on `emit.discover.walk` to add an
    unreadable subdirectory. Assert that `emit.build` raises `emit.PartialScan` (today it
    returns), and that the message names the directory as `<ROOT>/…`, not by absolute path.
  - `test_inventory_cli.py::test_a_partially_readable_root_exits_non_zero_and_overwrites_nothing`:
    pre-write sentinel `label-inventory.csv` and `.md` into `--output`, invoke the command
    with the same monkeypatch, and run with `--no-registry`. Assert a non-zero exit, both
    sentinels byte-identical, and the unreadable directory named in the output.
  - `test_inventory_cli.py::test_an_unlistable_root_is_a_clean_error`: the existing
    zero-candidate case gives a non-zero exit with no traceback (`result.exception` is a
    `SystemExit`). Today `PartialScan` escapes uncaught.
  - The existing `test_a_partial_scan_refuses_to_overwrite_the_artifacts` stays green.
    **Characterisation.**
- [ ] 5.2 GREEN — `feat(inventory): write nothing when any directory could not be read (GREEN)`
  - `emit.build` raises `PartialScan` whenever `scan.unreadable_paths` is non-empty. Its
    message lists them via `redact.emit_path(p, root).text`, sorted.
  - `cli.py` catches `PartialScan` beside `UnusableRoot` and raises `click.ClickException`.
  - Remove the now-unreachable "could not be read" warning branch after `write`. Update the
    command docstring's "Exits zero whatever it finds" and the `exit_code` docstring.

## 6. Docs and verification

- [ ] 6.1 `docs(inventory): filename-first species, derivation flags, and partial scans`:
  - `labeling/data/skeletons.yaml`: replace the plate-row comment's "The inventory still calls
    them arabidopsis, because it reads species from the directory before the filename (#65)"
    with: "The inventory reads the four `labels_wheat_*` files as wheat from their filenames
    (update-inventory-derivation, #59); `day2and3 copy.slp` names no species, so it still
    derives arabidopsis from its folder — only its images say wheat." The rows do not change.
  - `README.md`: fold the inventory paragraph's "predates the mode key …" into one sentence
    that stays true on both sides of the re-scan: "The committed scan is regenerated after each
    change to how names are read; see the CHANGELOG." Add one sentence: species is read from
    the filename, else the folder, and families whose names give several species, or whose
    folder disagrees, are listed and not resolved. Add one sentence: a scan that cannot read
    every directory writes nothing and exits non-zero.
  - `docs/roadmap.md`, backfill step 1: one line saying `update-inventory-derivation` (#59,
    #65) lists multi-species files, including the pooled
    `labels_seminal_wheat_5-14DAG_rice_3-10DAG.v005.slp`, and that resolving them (#59) comes
    before step 2.
  - `docs/CHANGELOG.md` `[Unreleased]`: add one bullet at the top of `### Changed` citing #59
    and #65. It covers the values that move on the next scan, the two columns, the "Name
    derivation" section, and the BREAKING partial-scan exit. The rule itself is not restated:
    it lives in the spec.
- [ ] 6.2 `docs(openspec): reconcile update-inventory-derivation with what was built`. Re-read
  the proposal, the spec delta and this file against the implementation. Every path, flag
  spelling, column name, heading and helper named here must be the one used. Record any
  deviation as `### Why N instead of M?` in `proposal.md`.
- [ ] 6.3 Validate on both pinned CLIs, and paste both outputs into the PR body, since CI runs
  neither:
  - `npx -y @fission-ai/openspec@1.5.0 validate update-inventory-derivation --strict`
  - `npx -y @fission-ai/openspec@1.11.0 validate update-inventory-derivation --strict`
- [ ] 6.4 CI gate:
  - `uv run black --check src/sleap_roots_training tests`
  - `uv run ruff check src/sleap_roots_training`
  - `uv run pytest -m "not integration" --cov=src/sleap_roots_training --cov-fail-under=95 --cov-report=term-missing`
  - `gap.py` must show no missed lines (it is at 100% today).
- [ ] 6.5 `git diff --stat main -- inventory/` is empty. This PR does not touch the committed
  scan.

## 7. After merge: the re-scan PR, then the archive PR

These are not part of this PR. They are two follow-up PRs, merged in this order, because the
squash merge keeps "its own commit" only if the commit is its own PR. If eberrigan is away,
hand both off explicitly rather than leaving §7 unticked in an unarchived change.

- [ ] 7.1 **PR B, `chore(inventory): re-scan with filename-first species (#59, #65)`**, from a
  branch off `main`. Run the approved command exactly:
  `uv run sleap-roots-training inventory labels "Z:/users/eberrigan/SLEAP"` (read-only,
  about 40 min). Group 5 makes the command refuse a partial scan by itself.
- [ ] 7.2 Before committing, stop and report rather than commit if any of these fail:
  - The CLI exited zero and printed no `WARNING:`. An unreachable registry would flip every
    row to `not-checked`; there are 0 today.
  - `.slp files seen` is about 18,099, and candidates and families did not drop below the
    committed 850 and 656.
  - Non-empty `error` cells number ≤ 2, the committed figure.
- [ ] 7.3 Grep both artifacts for `Z:`, `users/`, `eberrigan`, `Elizabeth`, a drive-letter
  pattern `[A-Za-z]:[\\/]`, and `\`. None may appear.
- [ ] 7.4 Compare with the projection, counting rows with `user_instances > 0`:
  - `multi-species` in `flags`: 33.
  - `folder-species-differs`: 12, in 9 directories.
  - `ambiguous-mode`: 0.
  - `multiplant cylinder`: 0.
  - Arabidopsis plate primary: 13/1/3.

  Report any drift in the PR body; do not explain it away.
- [ ] 7.5 The commit holds `inventory/` only. Open PR B and require the full matrix green:
  `inventory/**` triggers CI, which runs the plurality test. Rollback is one `git revert`
  of its squash commit.
- [ ] 7.6 **PR C, `chore(openspec): archive update-inventory-derivation`**, after PR B. Tick
  §7, record any 7.4 drift as `### Why N instead of M?`, merge the delta into
  `openspec/specs/label-inventory/spec.md`, and check that its Purpose still reads true.
