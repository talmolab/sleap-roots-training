## 0. Obtain the source and confirm scope

**This section gates the rest.** The port is a port — nothing below starts from a description of what
the scripts do.

- [x] 0.1 Fetch the onboarding bundle from Box
      (`Phenotyping_team_GH/sleap-roots-training/onboarding/`,
      https://salkinstitute.box.com/s/mznt60av95xcfn981dumh4qoccw420j0): the
      `/build-labeling-package` command doc, `build_slp_project.py`, `select_samples.py`, and the
      `bloomctl` setup guide. Record the copy date — the vault repo's history does not survive the
      Box copy, so the porting commit is the only place provenance can live.
      **Obtained 2026-07-29; `copy_selected_images.py` and `generate_readme.py` added to the same
      share and obtained 2026-08-03. All four workflow scripts are now in hand — record both copy
      dates in the porting commit.**
- [x] 0.2 Read all four scripts end to end before writing anything. Specifically establish: what
      `select_samples.py` reads to choose frames (Bloom API? a local manifest? scan directory
      listing?), whether selection is deterministic today, and what `build_slp_project.py` assumes
      about paths and platform.
      **Findings (design.md F1–F7):** reads two CSVs, no network; selection is deterministic for
      identical inputs but **widening is not monotone** (F3); no *structured* package metadata is
      written and `total_views = 72` is hardcoded (F4); the copy step also tolerates missing sources
      and exits 0, and `lstrip("./")` mis-resolves an absolute `source_image` (F5); `output_filename`
      omits `scan_id` so it is not guaranteed unique, and `shutil.copy2` overwrites silently (F6);
      the `LabelCard` metadata already exists as hand-edited prose in `generate_readme.py`,
      duplicating constants in `build_slp_project.py` (F7); all four scripts are soybean-WEEP-only
      despite the doc's `--crop` (Decision 7).
- [x] 0.3 **Re-scope gate.** If the Bloom coupling is larger than "read metadata, pick frames" — e.g.
      the scripts orchestrate downloads, or carry credentials handling — stop and split it out rather
      than absorbing it silently. Record the finding either way.
      **Finding (F2): does not fire for the scripts, fires for the workflow.** `select_samples.py`
      makes no network calls. Phase 0 of the doc runs `bloom cyl download` and a `psql` against the
      Bloom production DB with credentials from a local `.env`. **Split out:** `--accession-names`
      stays caller-supplied (the script already falls back to the numeric id), and the DB lookup
      stays a documented manual prerequisite.
- [x] 0.4 Confirm the Decision 2 placement with eberrigan on #26: embedding moves into the
      **builder**, and #10's `publish-labels` *verifies* self-containment rather than performing it.
      This departs from the issue's stated placement; the reasoning is in design.md.
      **Confirmed 2026-08-03 — move it a layer earlier, as proposed.** Decision 2 stands as written;
      section 5 is unblocked and #26's stated placement is superseded. Note the deviation in the
      porting commit so the issue and the change do not read as contradicting each other.
- [x] 0.5 Confirm the Decision 4 dependency call: `sleap-io` in core `dependencies`, or an extra if
      `feat/add-train-backend-extra` establishes an extras convention first.
      **Confirmed 2026-08-03 — core `dependencies`.** No extras guard, no import-time hint; 1.1
      proceeds as a plain runtime dependency. `feat/add-train-backend-extra` does not bind this.
- [x] 0.6 ~~**BLOCKER** — obtain `copy_selected_images.py` from the vault.~~ **Resolved 2026-08-03**:
      `copy_selected_images.py` and `generate_readme.py` both obtained from the same Box share and
      read. Sections 3 and 4 are unblocked; section 3 is rewritten against the actual script rather
      than against its expected shape.
- [x] 0.7 Ask eberrigan whether Phase 2 has grown any script since `build-labeling-package.md` was
      written. The doc names exactly four and we now have four, so this is confirmation rather than
      a blocker — but the vault, not Box, is the source of truth
      (`build-labeling-package.md:58`, `:140`), and the bundle was assembled for #10, not for this
      port. **Confirmed 2026-08-03 — no.** Four scripts is the whole of Phase 2; the Box bundle is
      complete with respect to the vault. Nothing further to fetch.
- [x] 0.8 Resolve the F6 collision question: can a single `(plant_qr_code, plant_age_days)` pair
      carry two `scan_id`s in practice? **Answered 2026-08-03 — no.** Two scans of the same plant at
      the same age is an *artifact* of the record, not a legitimate replicate; it does not occur in
      real data. **Consequences:** (a) `scan_id` stays **out** of `output_filename` — adding it would
      change every curated filename and break comparability with the eight published collections,
      to accommodate a state that should not exist; (b) the uniqueness assertion in 2.9 is therefore
      a **data-integrity check on the upstream record**, not a naming fix — on collision it must fail
      loudly and name the offending `scan_id`s rather than disambiguate them; (c) no retroactive
      audit of published collections is owed, so this does not become an #11 work item.
- [x] 0.9 Resolve the F5 path question: is `scan_path` in `scans.csv` relative or absolute in
      practice? **Answered 2026-08-03 by reading `bloomctl` — always relative, never absolute, and
      never `./`-prefixed.** `cyl/download.py:47-51` derives it as
      `f"images/Wave{n}/Day{age}_{date}/{qr}"`, pinned by
      `tests/test_download_metadata.py:44`. See design.md F8 — this answers the question as asked and
      surfaces a *different*, live defect in its place.

## 1. Dependency and module skeleton

- [x] 1.1 Add `sleap-io` to `pyproject.toml` per 0.5, pinned to a release; `uv lock`
      **Done 2026-08-03: `sleap-io>=0.7.1,<0.8.0` in core `dependencies`.** The cap deliberately
      matches the `train` extra's pre-mask line, and sleap-io is now declared in **both** places on
      purpose: the extra's cap is bound to `sleap-nn` compatibility, the core one to what the builder
      needs, and uv intersects them — so widening the core pin alone cannot drag the backend onto the
      unverified mask line. `uv lock` resolved with **no version churn** (sleap-io stays 0.7.1; the
      only lock delta is the new core edge).
      **Pre-existing test inverted:** `tests/test_train_extra.py::test_base_install_stays_lean`
      asserted sleap-io must *not* be a base dependency. Decision 4 reverses that, so the leanness
      check now guards `sleap-nn`/`torch` only — "lean" protects the heavy, platform-specific
      backends — and a new `test_sleap_io_is_a_core_dependency_on_the_same_capped_line` pins the
      core declaration and its cap, making the deliberate duplication load-bearing rather than drift.
      **Open, for section 2:** `select_samples.py` imports `pandas` directly. It is available today
      only *transitively* via sleap-io. Declaring it as a direct dependency is a section-2 call, not
      absorbed here
- [x] 1.2 Create `src/sleap_roots_training/labeling/` with `__init__.py`, mirroring the `registry/`
      package's shape (thin, well-bounded modules; google-style docstrings; `from __future__ import
      annotations`)
      **Done 2026-08-03 — `__init__.py` only.** The subpackage docstring states the two load-bearing
      properties (monotone widening, embedded output) and why, mirroring `registry/__init__.py`.
      Module files are created with their ports in sections 2–6 rather than stubbed empty here
- [x] 1.3 Add `tests/test_labeling_*.py` files matching the existing `test_registry_*.py` naming
      **Done 2026-08-03 — `tests/test_labeling_smoke.py`,** mirroring `test_registry_smoke.py`: a
      default install (no `train` extra) imports sleap-io and the subpackage, and `save_slp` exposes
      the `embed` parameter — which also pins that the library default is `embed=False`, the behavior
      4.1 ports and 5.2 changes. The per-module `test_labeling_*.py` files land with their modules;
      committing them empty now would add collected-but-empty files and no coverage

## 2. Port `select_samples.py` faithfully

- [x] 2.1 Copy the script in as `labeling/select_samples.py` with **behavior preserved**, adapting
      only what cannot run here (Windows path assumptions, interactive prompts, unpinned imports).
      Record every deviation as a task under section 7 — deviations are decisions, not cleanup
      **Done 2026-08-03.** Ported as `labeling/select_samples.py`. Adaptations forced by the move
      into a library: the PEP-723 `# /// script` header and the `argparse`/`__main__` block are
      dropped (the CLI is 8.4's job, and a second entry point would be a second place the defaults
      live); `print` becomes `logging` on a module logger, matching `registry/publish.py`.
      **`pandas` is now a direct dependency** — the 1.1 open item. The port imports it, and it was
      importable only *transitively* via sleap-io; a direct import of a transitive dependency breaks
      the day the intermediary drops it. Declared `pandas>=2.2.0,<4.0.0`, deliberately wide: the API
      used is `read_csv`/`groupby`/`to_csv`, and 2.7 removed the one version-sensitive behavior, so
      pandas' RNG can no longer move which frames a package labels. `uv lock`: **no version churn**
- [x] 2.2 (RED) Characterization tests over a small fixture: the frames selected, their order, and
      the manifest rows produced. These pin the *ported* behavior before anything changes
- [x] 2.3 (GREEN) Make the characterization tests pass without altering selection semantics
      **Done 2026-08-03 — 13 characterization tests GREEN against the faithful port**, before any
      behavior change, which is the commit Decision 1 asks for. The port reproduces the original
      exactly, including the view formula (`[1,25,49]` / `[1,19,37,55]` / `[1,13,25,37,49,61]`) and
      the manifest row order. Two tests written in the same pass failed — **both are defects in the
      original, not port errors**: see F9 (the glob branch) and F10 (row-order determinism)
- [x] 2.4 (RED) Test that selection is deterministic — the same inputs and parameters select the same
      frames in the same order across runs. **Expected GREEN against the port** (F3): the draw is
      seeded and group ordering is stable. If it passes immediately, say so rather than manufacturing
      a failure
      **Done 2026-08-03 — GREEN immediately, as predicted; no failure manufactured.** But the
      property is narrower than Decision 5 needs: it holds for identical *bytes*, not identical
      *content*. `.sample()` draws by position, so re-exporting `scans.csv` with the same rows in a
      different order selects different plants (**F10**). Since Decision 6's recovery path re-fetches
      `scans.csv` from Bloom, a re-download that reorders rows silently changes the label set. The
      2.7 fix closes it
- [x] 2.5 Pin `total_views = 72` as a characterized assumption and decide whether an experiment with
      a different view count should fail loudly rather than mis-select (F4)
      **Done 2026-08-03 — fail loudly.** `TOTAL_VIEWS = 72` is now a documented default parameter
      rather than a constant, and selection rejects `views_per_plant` outside `1..total_views`
      instead of computing a `step` of 0 and mis-selecting. **Scope boundary:** selection reads two
      CSVs and never touches the filesystem (F2), so it cannot check the count against what a scan
      actually holds — that check belongs to the copy step, the first stage that sees the images.
      **Obligation on 3.x:** verify the on-disk view count. **Obligation on 8.3:** record
      `total_views` in the package metadata, since it is a selection parameter a consumer needs and
      the manifest's enumerated columns do not carry it
- [x] 2.6 (RED) Test that a widened re-run is a superset of the narrower one. **Known to fail against
      the port** (F3) — `.sample(n, random_state)` re-draws rather than extends, and
      `step = 72 // views_per_plant` gives `[1,19,37,55]` for 4 views against `[1,25,49]` for 3
      **Done 2026-08-03 — RED against the port exactly as predicted, in both dimensions**
- [x] 2.7 (GREEN) Make widening monotone in both dimensions — a stable ordering over an explicit key,
      the wider run taking a prefix-superset — and record it in section 7 as a deliberate deviation.
      Decision 6's recovery path depends on this; it is not a cleanup
      **Done 2026-08-03.** *Plants:* ordered by `sha256(f"{seed}:{barcode}")`, prefix taken. Nested
      by construction, and — unlike `.sample()` — independent of `scans.csv` row order and of pandas'
      RNG, which closes F10 as well. *Views:* greedy farthest-point dispersion, nested by
      construction; verified nested for **every** count 1..72, not just the sampled ones. Distance is
      measured **circularly**, because view 72 and view 1 are adjacent angles on a cylinder — the
      linear formula treated them as opposite extremes, so a nested-but-linear scheme would have
      paired two near-identical views. Four views are unchanged from the original (`[1,19,37,55]`);
      three become `[1,19,37]` instead of `[1,25,49]`. **Consequence recorded in design.md:**
      monotonicity is a guarantee *from this port forward*; the eight pre-port collections cannot be
      re-derived as supersets, so widening one is a new label set rather than a v2
- [x] 2.8 (RED) Test that `sample_manifest.csv` has one row per selected frame and carries every
      required column (`scan_id`, `plant_qr_code`, `plant_age_days`, `accession_id`,
      `accession_name`, `wave_number`, `view_index`, `frame_index`, `source_scan_path`,
      `source_image`, `output_filename`)
      **Done 2026-08-03.** Column set and order pinned against `MANIFEST_COLUMNS`, which is asserted
      against Decision 3's enumeration so the contract and the code cannot drift apart silently
- [x] 2.9 (RED) **Test that `output_filename` is unique across the manifest** (F6). The counter is
      keyed by `scan_id` but the name is not, so two scans of the same `(plant_qr_code,
      plant_age_days)` collide — and every downstream layer absorbs it silently. Construct the
      fixture to contain that case; assert selection fails with an error naming the colliding rows.
      **Decided (0.8): the assertion alone — `scan_id` does NOT go in the name.** A repeat is an
      artifact of the upstream record, so the check exists to surface it, not to accommodate it; the
      error must name the colliding `scan_id`s. Filenames are unchanged, which keeps the eight
      published collections comparable. Record in section 7
      **Done 2026-08-03 as decided.** The fixture manufactures the colliding rescan; the error names
      the filename and both `scan_id`s and points at the upstream record. Also asserted: **no
      manifest is written on collision**, so a failed run cannot leave a file a later stage mistakes
      for a good one. Filenames are unchanged
- [x] 2.10 (RED) Pin which derivation of a frame's position is authoritative (F6): the manifest's
      `frame_index` column, or `build_slp_project.py:105,136`'s sort-by-`view_index`-and-enumerate,
      which never reads that column. They agree only because `selected_views` is ascending. Make the
      builder read the manifest, or delete the unused column — not both derivations
      **Done 2026-08-03 — `frame_index` is authoritative; the column stays** (Decision 3 and the
      spec both require it, so deleting it was not open). The test pins it as the within-scan rank
      and proves the sort-and-enumerate derivation agrees, so the builder can switch without a
      behavior change. **Obligation on 4.1: the builder reads `frame_index` and does not re-derive
      position.** Until it does, the two derivations still both exist

## 3. Port the image-copy step (unblocked by 0.6)

- [x] 3.1 Port `copy_selected_images.py` as `labeling/copy_images.py`, behavior preserved —
      including the warn-and-continue on a missing source and the exit-0 summary (F5). The fail-loud
      change is 3.4, as its own commit
      **Done 2026-08-04.** Same adaptations section 2 made: PEP-723 header and `argparse`/`__main__`
      dropped (the CLI is 8.4), `print` to `logging`. One further adaptation: the summary counts
      become a **return value** `(copied, missing)` rather than stdout, because 3.4's fail-loud rule
      has to act on them and parsing log text would make the deviation commit turn on string
      matching. Recorded in section 7
- [x] 3.2 (RED) Characterization tests: the files copied and their names; that a pre-existing
      destination is **overwritten silently** (`shutil.copy2`, `:41`); and that the reported
      `copied` count counts copy *calls*, not resulting files (`:42`)
      **Done 2026-08-04 — GREEN against the faithful port**, which is the Decision 1 commit. Both
      defects reproduce exactly: a duplicate `output_filename` yields 2 files while `copied` reports
      3, and a missing source returns normally with a partially populated directory
- [x] 3.3 (RED) **Characterize the base-directory mismatch** (F8, which supersedes F5's absolute-path
      hypothesis — see 0.9). Two fixtures, both with complete, present data: a `scan_path` in
      `bloomctl` form (`images/Wave1/Day3_.../QR`, relative to the dir holding `scans.csv`) and one in
      legacy form (`./images_downloader_output/images/...`, relative to `experiment_dir`). Pin that
      the current code resolves the legacy form and misses **every** row of the `bloomctl` form by one
      path segment, yielding an empty `images/` with exit 0. Do **not** write an absolute-path
      characterization test — 0.9 established `bloomctl` never emits one, so there is no shipped
      behavior there to preserve
      **Done 2026-08-04 — F8 reproduces exactly as design.md predicts.** The `bloomctl` fixture
      misses all three rows and leaves an empty `images/`, with correct and present data; the same
      manifest resolves when handed the download dir instead. A parametrized test pins that
      **neither** convention resolves against the other's base, so 3.4 cannot fix this by detecting
      which producer wrote the manifest — it has to be told
- [x] 3.4 (GREEN) Replace character-stripping with an explicit resolution rule: resolve
      `source_image` against **the directory containing the `scans.csv` it was derived from** (how
      that base reaches the copy step is 7.2 — decide it before writing this), and reject an absolute
      `source_image` outright rather than mangling it. This is producer-agnostic — it resolves both
      the `bloomctl` and legacy conventions without detecting which is in play. Make **any**
      unresolved source fail the step; an empty or partial copy is never a success. Record in
      section 7
      **Done 2026-08-04, per the 7.2 decision below.** The step now takes `scans_csv` in place of
      `experiment_dir` and resolves against its parent; a parametrized test proves both producers'
      manifests resolve with no detection of which wrote them. The step is **all-or-nothing**: every
      row is resolved before a single file is written, so a failure leaves no `images/` at all rather
      than a partial one. Absolute paths are rejected by name instead of stripped
- [x] 3.5 (RED) Test that a duplicate `output_filename` in the manifest is rejected rather than
      silently overwritten (F6). Pairs with 2.9, which is where the duplicate should be caught
      first — this is the second line of defence, since a hand-edited manifest can reach the copy
      step directly
      **Done 2026-08-04.** `_assert_unique_output_filenames` became public
      `assert_unique_output_filenames` and both stages call it, so the two lines of defence are one
      rule rather than two that can drift. Asserted: nothing is written when it fires
- [x] 3.5a (RED) **Obligation from 2.5:** verify the scan's actual view count against the
      `total_views` selection assumed. Selection reads only CSVs, so it cannot check it; the copy
      step is the first stage that sees the images. A scan holding fewer views than assumed produces
      manifest rows pointing at `.jpg` files that do not exist — which 3.4's fail-loud rule catches
      per-row, but reports as N unrelated missing files rather than as the one wrong parameter that
      caused them. Name the assumption in the error
      **Done 2026-08-04, and it fails in *both* directions.** Too few views and the manifest names
      files that do not exist; too many and the selected indices are the wrong angles — either way
      the parameter is wrong, so the check is agreement rather than the number 72. The error reports
      what the scan holds, what selection assumed, and the value to re-run with. Only `<int>.jpg`
      counts as a view, so download sidecars do not perturb it. A test pins that this stage's default
      is the same 72 selection defaults to, since drift between them would re-open the gap
- [x] 3.6 Decide whether the copy step remains a separate stage or folds into the builder once
      `embed=True` lands (5.5). Keep them separate through section 5 so the characterization tests
      stay meaningful; revisit after
      **Revisited 2026-08-04 after section 5 — they stay separate.** 5.5 keeps `images/` in the
      package, so the copy step produces a *shipped artifact* rather than a temporary staging
      directory, which settles most of it. The rest is coupling: the copy step is the only stage
      that knows about Bloom's download layout — `scans.csv`, the base-directory rule, the view-count
      assumption — and the builder knows nothing beyond the manifest and a directory of curated
      names. Folding them would drag that layout into the builder and make the copy step's five
      distinct failure modes report as build failures

## 4. Port `build_slp_project.py` faithfully

- [x] 4.1 Copy the script in as `labeling/build_package.py`, behavior preserved (**including
      `embed=False` at this step** — the embed change is section 5, as its own visible commit)
      **Obligation from 2.10:** the builder reads `frame_index` from the manifest instead of
      re-deriving position by sorting on `view_index` and enumerating. 2.10 pinned `frame_index` as
      authoritative and proved the two derivations currently agree, so this is a swap with no
      behavior change — but until it happens, both derivations still exist and F6 is only half
      closed. Do it in the port rather than deferring it, and note it in section 7
      **Done 2026-08-04, obligation included.** Same adaptations as sections 2–3 (PEP-723 header and
      `argparse`/`__main__` dropped, `print` to `logging`). `frame_index` is now the only derivation
      of a frame's position, and the scan's video is ordered by it too — a position that indexed a
      differently-ordered video would be a wrong package, so the two had to move together. One new
      check the swap forces: `frame_index` must be a contiguous rank from zero within a scan, since
      it indexes into that scan's video. Recorded in section 7
- [x] 4.2 (RED) Characterization tests over a fixture: the package directory produced, its contents,
      and the `.slp` it writes
- [x] 4.3 (GREEN) Make them pass without changing behavior
      **Done 2026-08-04 — 14 tests GREEN against the faithful port**, the Decision 1 commit. Pinned:
      both versioned `soybean_weep_*` outputs, one `Video` per scan holding only the selected views,
      the 1-based-view to 0-based-rotation translation (the fixture encodes each prediction's view in
      its x coordinate, so an off-by-one would put another angle's landmarks on the frame), the
      single canonical skeleton, the hardcoded 6/4-node soybean pair, per-root-type scan inclusion,
      the multiple-prediction-file warning, and **`embed=False`** — the last is what 5.1 must break.
      A shared 447-byte `TINY_JPEG` constant lives in `conftest.py` rather than generating images
      with `imageio`, which is importable here only transitively via sleap-io (the 2.1 trap)
- [x] 4.4 (RED) **Characterize the silent-empty-package failure before fixing it** (F1): with an
      unpopulated `images_dir`, the port warns per scan, writes both `.slp` files, and exits 0. Pin
      that, then make it fail loudly — an empty selection is never a successful build
      **Done 2026-08-04, characterized then broken in the following commit.** Two ways an empty
      selection can arise, both now fatal: no curated images (the copy step never ran), and a
      requested root type that ends up with no frames. The second is why `root_types` is *declared*
      rather than inferred — a primary-only package now says so instead of shipping an empty lateral
      `.slp`. A scan absent from every prediction file also fails, since the selection cannot be
      honored; a scan predicted for only *some* requested root types stays legitimate and warns,
      because a model finding no laterals is a result rather than a defect
- [x] 4.5 (RED) Test that an unreadable/missing source scan fails the build **before** any package
      output is written — no partial directory left behind
      **Done 2026-08-04.** Every curated image across every scan is checked before a single video is
      opened, so the report is "6 of 6 images missing" rather than the first scan that failed.
      `output_dir` is created only after both projects are fully assembled, and a test asserts a
      failed build leaves no directory at all
- [x] 4.6 (RED) Test that missing required package metadata (capture mode, skeleton name) fails the
      build with an error naming the field, before writing
      **Done 2026-08-04 — new `labeling/metadata.py`.** `PackageMetadata` carries the fields the
      *builder* requires — `species`, `mode`, `root_types` — validated on construction against the
      repo's existing `SPECIES_VOCAB`/`MODE_VOCAB` and the contract's `RootType` literal rather than
      a new vocabulary. **Scope boundary:** this is the required-at-build subset, so the check can
      exist before the on-disk format is settled; 8.3 extends the same type with
      `bloom_experiment_id`, the accession map, and the selection parameters, and defines the file.
      The skeleton comes from `skeleton_for(species, root_type)`, which still holds only the vault
      script's hardcoded soybean pair and **raises** for anything else — giving another species
      soybean's node counts would produce a package that looks fine and cannot be combined with
      anything. Section 6.6 replaces that lookup with the committed table
- [x] 4.7 (GREEN) Implement fail-fast ordering if the ported code writes before validating
      **Done 2026-08-04.** Order is: metadata and skeletons (no file access, so a wrong species is
      not reported as a data problem) -> manifest `frame_index` ranks -> every curated image ->
      predictions -> non-empty root types -> `mkdir` -> write. Nothing touches the output path until
      the last two steps

## 5. The embed change — deliberate, isolated, tested

- [x] 5.1 (RED) Test that a built package's `.slp` is self-contained: opened with the source scan
      paths made unreachable, it still yields its labeled frames. This test MUST fail against the
      section-4 port (which saves `embed=False`) — that failure is the point of the commit boundary
      **Done 2026-08-04 — RED against the section-4 port exactly as required**, in
      `tests/test_labeling_embed.py`. The assertions reach the **pixels**, not the frame count: a
      broken reference still lists its frames, so a count-only test passes against a package a
      labeler cannot open. Three tests were red (self-containment, the validator's verdict, a moved
      package); the three that exercise the *rejection* path were green from the start
- [x] 5.2 (GREEN) Change the builder to `save_slp(..., embed=True)` as an explicit step, with a
      comment recording *why*: six of the eight published collections carry
      `repaired_from: "v0"` / `embedded-images-repair` because the external reference broke, and the
      repair permanently caps the label set
      **Done 2026-08-04.** The comment is at the call site, stating the one-way-repair reason.
      Three section-4 tests moved with it: they asserted through `video.filename`, which an embedded
      video sets to the `.slp` itself. They now assert through `video.source_video`, which retains
      the original paths as *provenance* — nothing opens it — so the port's frame-ordering and
      one-video-per-scan guarantees stay pinned
- [x] 5.3 (RED) Test that package validation rejects a package whose `.slp` references external
      images, so the guarantee holds for a package built by an older tool or by hand
      **Done 2026-08-04 — new `labeling/validate.py`.** `slp_is_self_contained` /
      `assert_slp_is_self_contained` read the file with `open_videos=False`, so an already-broken
      package is diagnosable rather than raising on the very dependency being checked. This is the
      entry point Decision 2 hands to #10's `publish-labels`; 8.1 composes the layout, column, and
      count checks around it
- [x] 5.4 Verify the embedded output against a real scan, not only a fixture — confirm the resulting
      file is a genuine `.pkg.slp` and note the size multiple observed (the eight existing
      collections run 170 MB – 1.2 GB, ~10x)
      **Done 2026-08-04 against the real WEEP package** (`~/data/weep`: 255 curated JPEGs, 349 MB,
      the shipped manifest, and v000–v013). Drove the real builder over 71 scans / 213 frames:
      **185.6 MB**, `HDF5Video`-backed, self-contained by 5.3's check, pixels readable (1080x2048)
      after the source directory was deleted, `source_video` provenance intact. That is **1195x**
      the shipped external-reference `.slp` (155 kB) and **0.61x** the source JPEG bytes, and it
      lands inside the 170 MB – 1.2 GB band of the eight published collections. **Surfaced F11** —
      the shipped manifest has nine columns and a different filename scheme, so the Box copy of
      `select_samples.py` is a *later* revision than the one that built the published collections.
      See design.md; it weakens (but does not overturn) the comparability argument in 0.8
- [x] 5.5 Decide whether `images/` still ships in the package once the `.slp` embeds them, or becomes
      redundant. It is what the labeler browses today; dropping it is a delivery change, not a
      correctness one
      **Decided 2026-08-04 — `images/` stays, and the cost is now measured rather than assumed.**
      Dropping it would cut the package to ~38% of its size (185.6 MB embedded vs 304.5 MB of
      source JPEGs alongside it, on the 5.4 sample). Three reasons it stays: the spec's
      curated-images requirement includes a validation scenario comparing the image count against
      the manifest row count, so dropping the directory would delete a specified check; the manifest's
      `output_filename` column becomes unresolvable against anything; and a reviewer can inspect what
      was labeled without installing SLEAP. **Not decided here:** whether the *published* artifact
      should carry it. That is a W&B storage question with a real number attached now, and it belongs
      to #10's publish path rather than inside a port — recorded for 9.4 to hand over

## 6. Per-crop skeletons (Decision 7 — new code, not a port)

- [ ] 6.1 Create `labeling/data/skeletons.yaml`, keyed by `(species, root_type)`, mirroring
      `registry/data/model_selection.yaml`'s provenance-stamped shape (source, snapshot date,
      validated on load with row-numbered errors)
- [ ] 6.2 Transcribe the doc's table (`build-labeling-package.md:45-51`) with a header stating it is
      **advisory and unverified**, and that these are **native** skeletons — explicitly not Tier
      2.7's unified node count (`docs/roadmap.md:422`)
- [ ] 6.3 (RED) Loader test: a missing `(species, root_type)` fails loudly rather than defaulting.
      **Pennycress has no row** — the table ships incomplete on purpose
- [ ] 6.4 (RED) Cross-check test against `model_selection.yaml`: the rice age split (young 2–5
      primary + crown, old 6–10 crown only) must agree between the two tables
- [ ] 6.5 (RED) **Verification test against the published collections** — read the eight
      `wandb-registry-sleap-roots-labels` artifacts and fail on any node-count or node-name
      disagreement with the table. This is what converts the table from hypothesis to record; mark
      it `@pytest.mark.integration` if the download makes it unfit for default CI
- [ ] 6.6 Parameterize `build_package.py` by `(species, root_type)` off the table, replacing the
      hardcoded `make_primary_skeleton` / `make_lateral_skeleton` and the `soybean_weep_*` output
      names. Record in section 7 — the original had no such parameterization to port

## 7. Port deviations (fill in during sections 2–6)

- [ ] 7.1 Record each deviation from the vault scripts: what changed, why it could not be preserved,
      and whether it is visible to a caller. An empty section here means the port was faithful; it
      should not be empty by omission.
      **Known before starting:** (a) monotone widening (2.7, F3); (b) fail-loud on an empty
      selection (4.4, F1); (c) crop parameterization (6.6, Decision 7); (d) `embed=True` (5.2);
      (e) `total_views` validation (2.5, F4); (f) explicit `source_image` resolution replacing
      `lstrip("./")`, and fail-loud on a missing source in the copy step (3.4, F5/F8);
      (g) `output_filename` uniqueness enforced by assertion, filenames unchanged — the collision
      fails the run rather than being disambiguated (2.9, F6, per 0.8); (h) a single authoritative
      frame-position derivation
      (2.10, F6); (i) the README rendered from structured metadata instead of hardcoded prose
      (8.3a, F7); (j) POSIX-normalized separators in `source_scan_path`/`source_image` so a manifest
      written on the vault machine resolves here (F5)

      **Recorded from section 2 (`select_samples.py`, 2026-08-03).** Caller-visible unless noted:
      1. **Plant draw** — `.sample(n, random_state=seed)` to a prefix of a `sha256(seed:barcode)`
         ordering (2.7, F3/F10). Widening is now monotone, and selection no longer depends on
         `scans.csv` row order or on pandas' RNG. **A given seed selects different plants than the
         vault script did** — this is the deviation with the widest blast radius in the change.
      2. **View indices** — `step = total_views // views_per_plant` to circular farthest-point
         dispersion (2.7, F3). Nested for every count; four views unchanged (`[1,19,37,55]`), three
         change to `[1,19,37]` from `[1,25,49]`.
      3. **`total_views`** — hardcoded constant to a validated default parameter; an out-of-range
         `views_per_plant` now raises rather than mis-selecting (2.5, F4).
      4. **`output_filename` uniqueness** — now asserted before the manifest is written; a collision
         raises and names the offending `scan_id`s, and no manifest is written (2.9, F6, per 0.8).
         Filenames themselves are unchanged.
      5. **Glob branch** — anchored at the last wildcard-free component, so a wildcard in a
         *directory* component resolves (F9). The vault version raised `FileNotFoundError` for the
         layout QC actually writes. **Makes `build-labeling-package.md`'s Phase 1 manual `pd.concat`
         unnecessary — 8.6 should drop that step when it ports the doc.**
      6. **POSIX separators** — `Path` to `PurePosixPath` with backslash normalization, so a manifest
         written on the vault's Windows machine resolves here (7j, F5).
      7. **Not caller-visible:** PEP-723 header and `argparse`/`__main__` block dropped (the CLI is
         8.4); `print` to `logging`; `pandas` declared as a direct dependency rather than relied on
         transitively via sleap-io (2.1, the open item from 1.1).

      **Recorded from section 3 (`copy_selected_images.py`, 2026-08-04).** All caller-visible:
      1. **Base directory** — the step takes `scans_csv` in place of `experiment_dir` and resolves
         `source_image` against its parent (3.4, F8, per the 7.2 decision). This is what makes a
         `bloomctl` export work at all: the vault rule missed **every** row by exactly one path
         segment and reported success. Producer-agnostic — nothing detects which CLI wrote the
         manifest. The manifest contract is unchanged.
      2. **Wrong-`scans.csv` check** — every manifest row's `(scan_id, source_scan_path)` must be
         described by the `scans.csv` it was handed, so the base cannot be silently wrong (3.4).
         New behavior; the vault script had no equivalent because it had nothing to check against.
      3. **Fail-loud, all-or-nothing** — every row resolves before anything is written, and any
         unresolved source raises (3.4, F5). Replaces warn-per-row-and-return; the destination
         directory is no longer created on a failed run, so a partial `images/` cannot be mistaken
         for a complete one. The error names the rows and the paths, capped at ten with a count.
      4. **Absolute paths rejected** — replaces `lstrip("./")`, a character-set strip that ate a
         leading separator and resolved nowhere (3.4, F5, per 0.9). No shipped behavior was
         preserved here because Bloom never emits one; the strip guarded a trap it also created.
      5. **Duplicate `output_filename` rejected** — the same rule 2.9 applies at selection, now
         enforced here too for a hand-edited manifest (3.5, F6). `_assert_unique_output_filenames`
         became public `assert_unique_output_filenames` so both stages share one rule rather than
         two that can drift.
      6. **View-count check** — a scan whose image count contradicts `total_views` fails, naming the
         assumption and the value to re-run with (3.5a, the obligation from 2.5). Fails in both
         directions: too few and the manifest names absent files, too many and the selected indices
         are the wrong angles.
      7. **Return value** — `(copied, missing)` from 3.1's port collapses to `copied`, since a
         missing source is now an exception. The vault script returned `None` and printed the
         summary; the counts are a return value because 3.4's rule acts on them and log-text
         matching would be a poor foundation for it.
      8. **Preserved deliberately:** `shutil.copy2` still overwrites, which keeps re-running the
         step idempotent. Only the *silent* half of that behavior was a defect, and 3.5 removes it
         at its source rather than by refusing to overwrite.

      **Recorded from sections 4–5 (`build_slp_project.py`, 2026-08-04).** All caller-visible:
      1. **`embed=True`** — the change #26 exists for (5.2). The vault script wrote an
         external-reference `.slp`; six of the eight published collections were hand-repaired into
         packages afterwards, which caps their label set permanently. Per Decision 2 this happens in
         the *builder*, not in #10's `publish-labels`, so the on-disk package is already complete.
         **Consequence:** an embedded video's `filename` is the `.slp` itself, and the source image
         paths survive as `source_video` provenance rather than as a dependency.
      2. **`frame_index` is the only frame-position derivation** (4.1, the 2.10 obligation, F6). The
         scan's video is ordered by it too, since a position indexing a differently-ordered video
         would be a wrong package. Forces one new check: `frame_index` must be a contiguous rank
         from zero within a scan.
      3. **Required package metadata** — the builder takes a validated `PackageMetadata` (species,
         capture mode, root types) and fails naming the field (4.6, F4). New design, not a port:
         nothing in the vault emitted structured metadata. `root_types` is *declared*, not inferred,
         which is what makes "no frames for a requested root type" a failure rather than an empty
         file.
      4. **Fail-loud, all-or-nothing build** — a missing curated image, a scan with no predictions
         at all, or a requested root type with no frames each fail the build, and `output_dir` is
         created only after both projects are assembled (4.4, 4.5, 4.7, F1). Replaces warn-per-scan-
         and-write-anyway. **Preserved deliberately:** a scan predicted for only *some* requested
         root types still contributes and warns — a model finding no laterals is a result.
      5. **Skeleton lookup fails for unported crops** — `skeleton_for(species, root_type)` raises
         outside the hardcoded soybean pair rather than handing another species soybean's node
         counts (4.6). Section 6.6 replaces it with the committed table.
      6. **Return value** — the builder returned `None`; it now returns the path written per root
         type, which is what 8.4's CLI reports and 8.1's validation checks.
      7. **`load_predictions_for_scan` sorts its glob** — the vault script took `list(glob)[0]` when
         several prediction files matched, making "the first" depend on filesystem iteration order.
         Sorting makes the warning's "using first" mean something. Not caller-visible in the
         single-match case, which is every documented case.
- [x] 7.2 ~~**Open, decide during section 3:**~~ **Decided 2026-08-04 — neither (a) nor (b): the copy
      step takes the `scans.csv` itself.** 3.4 resolves `source_image` against the directory holding
      the `scans.csv` it came from. That base has to reach the copy step somehow, and the two options
      originally weighed were:
      (a) **carry it as a manifest column** — self-describing and immune to a wrong CLI argument, but
      it adds a column, so Decision 3's enumerated contract, task 2.8, the spec's manifest
      requirement, and #10's `LabelCard` consumer all move with it; or
      (b) **pass it as a CLI argument** to the copy step, replacing `experiment_dir` — no contract
      change, but a caller can still point it at the wrong directory, which is exactly the F8 failure
      re-opened one layer up.
      The lean was (a), on the grounds that only it removes the caller's assumption. **A third option
      removes the assumption at (b)'s blast radius, so it wins on the stated criterion.** The step
      takes the `scans.csv` path in place of `experiment_dir` and derives the base as its parent —
      and then *checks* it, requiring every manifest row's `(scan_id, source_scan_path)` pair to be
      described by that file. A caller who points at the wrong `scans.csv` now gets an error naming
      the scan rather than an empty copy, which is the failure (a) was chosen to prevent.
      **Why not (a), concretely.** The base is an absolute path on the producing machine, so writing
      it into an artifact that ships publicly (i) records a path that is wrong the moment the package
      moves or the download dir is renamed — the caller must override it anyway, which is (b)'s
      failure mode with an extra column — and (ii) puts local filesystem structure inside a published
      artifact, against Decision 3's "no dependency on the machine that produced it". The manifest
      contract stays as Decision 3 enumerates it; 2.8, the spec, and #10's consumer do not move.
      **Consequence for 8.4:** the CLI's copy step takes `--scans-csv`, not an experiment directory.

## 8. Package validation, CLI, and the workflow doc

- [ ] 8.1 Implement `labeling/validate.py` (or equivalent): the layout, manifest-column, frame-count,
      and self-containment checks as one callable that fails before any network call — this is what
      #10's `publish-labels` will call
- [ ] 8.2 (RED) Tests for each rejection path, each asserting the error names the offending piece
- [ ] 8.3 Define and write the package metadata file — **new design, not ported** (F4): nothing in
      the vault scripts emits capture mode, skeleton name, or `bloom_experiment_id` in a parseable
      form. Source its *values* from where they live today (F7): `bloom_experiment_id` from
      `generate_readme.py:66`, the accession map from `:85-89`, the skeleton from `skeletons.yaml`
      per Decision 7. Each of those has two hand-synced copies today; this file is what makes it one.
      **Obligation from 2.5:** also record the selection parameters — `seed`, `plants_per_group`,
      `views_per_plant`, and `total_views`. They determine which frames the package holds, and the
      manifest's enumerated columns carry none of them, so without this the selection is not
      reproducible from the artifact alone (Decision 5) even though it is deterministic
- [ ] 8.3a Port `generate_readme.py` as `labeling/render_readme.py`, rendering the README **from the
      8.3 metadata file and the manifest** rather than from hardcoded prose. The labeler-facing
      content (SLEAP install, Notion guide, `v000`/`v001` versioning convention) stays as-is — it is
      good documentation and is not crop-specific
- [ ] 8.3b (RED) Test that the rendered README's counts agree with `sample_manifest.csv` (F7).
      `generate_readme.py:91` globs `images/*.jpg` while the manifest is the record of what should
      be there, so today the README silently reports the post-F5/F6 reduced number. Assert a
      mismatch is an error, not prose. Include `:96`'s `len(rows) // plant_count` integer division,
      which misreports whenever views per plant are unequal
- [ ] 8.3c (RED) Test that the README's skeleton description matches the skeleton actually written
      into the `.slp` — the node counts at `generate_readme.py:58-60` are prose duplicating
      `build_slp_project.py:43-58`, and this is the test that stops them drifting again
- [ ] 8.4 Wire the build + validate commands into `cli.py` as a `labeling` group, mirroring how
      `seed_registry_command` is exposed
- [ ] 8.5 (RED) CLI tests mirroring `tests/test_registry_cli.py`: a successful build reports the
      package path; a validation failure exits non-zero with the error and writes nothing
- [ ] 8.6 Port `/build-labeling-package` into `.claude/commands/build-labeling-package.md`, updated
      to drive the in-repo CLI rather than vault script paths, and to record the Bloom
      accession-name lookup as a manual prerequisite (F2) rather than an in-repo step.
      **Obligation from F9:** drop Phase 1 step 4's manual `pd.concat` of the per-age-group QC files
      (`build-labeling-package.md:128-133`). It existed only because the script's glob branch could
      not resolve a wildcard directory; the port fixes that, so the CLI now takes
      `<qc_out>/*/10_final_data.csv` directly. Leaving the step in would keep a workaround for a bug
      that no longer exists
- [ ] 8.7 Document continue-labeling as **re-derive + republish** in the workflow doc: re-fetch via
      `bloomctl download --experiment-id <id>`, re-select wider, publish a new version — with the
      `save_slp` truncation reason stated, not just the instruction

## 9. Validation and handoff

- [ ] 9.1 `uv run openspec validate add-labeling-package-generator --strict`
- [ ] 9.2 `uv run pytest`, `uv run black --check src tests`, `uv run ruff check src tests`
- [ ] 9.3 Confirm CI passes on 3.11 and 3.12 — `sleap-io` is a new dependency and this is the first
      code in the repo that touches `.slp` files
- [ ] 9.4 Comment on #10 that the package layout is now real, naming the validate entry point
      `publish-labels` should call, so `add-label-registry` can be built against it rather than
      against a description
- [ ] 9.5 Close #26 referencing the ported modules, the embed commit, and the deviations in section 7
