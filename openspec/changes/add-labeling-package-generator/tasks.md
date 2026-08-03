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

- [ ] 2.1 Copy the script in as `labeling/select_samples.py` with **behavior preserved**, adapting
      only what cannot run here (Windows path assumptions, interactive prompts, unpinned imports).
      Record every deviation as a task under section 7 — deviations are decisions, not cleanup
- [ ] 2.2 (RED) Characterization tests over a small fixture: the frames selected, their order, and
      the manifest rows produced. These pin the *ported* behavior before anything changes
- [ ] 2.3 (GREEN) Make the characterization tests pass without altering selection semantics
- [ ] 2.4 (RED) Test that selection is deterministic — the same inputs and parameters select the same
      frames in the same order across runs. **Expected GREEN against the port** (F3): the draw is
      seeded and group ordering is stable. If it passes immediately, say so rather than manufacturing
      a failure
- [ ] 2.5 Pin `total_views = 72` as a characterized assumption and decide whether an experiment with
      a different view count should fail loudly rather than mis-select (F4)
- [ ] 2.6 (RED) Test that a widened re-run is a superset of the narrower one. **Known to fail against
      the port** (F3) — `.sample(n, random_state)` re-draws rather than extends, and
      `step = 72 // views_per_plant` gives `[1,19,37,55]` for 4 views against `[1,25,49]` for 3
- [ ] 2.7 (GREEN) Make widening monotone in both dimensions — a stable ordering over an explicit key,
      the wider run taking a prefix-superset — and record it in section 7 as a deliberate deviation.
      Decision 6's recovery path depends on this; it is not a cleanup
- [ ] 2.8 (RED) Test that `sample_manifest.csv` has one row per selected frame and carries every
      required column (`scan_id`, `plant_qr_code`, `plant_age_days`, `accession_id`,
      `accession_name`, `wave_number`, `view_index`, `frame_index`, `source_scan_path`,
      `source_image`, `output_filename`)
- [ ] 2.9 (RED) **Test that `output_filename` is unique across the manifest** (F6). The counter is
      keyed by `scan_id` but the name is not, so two scans of the same `(plant_qr_code,
      plant_age_days)` collide — and every downstream layer absorbs it silently. Construct the
      fixture to contain that case; assert selection fails with an error naming the colliding rows.
      **Decided (0.8): the assertion alone — `scan_id` does NOT go in the name.** A repeat is an
      artifact of the upstream record, so the check exists to surface it, not to accommodate it; the
      error must name the colliding `scan_id`s. Filenames are unchanged, which keeps the eight
      published collections comparable. Record in section 7
- [ ] 2.10 (RED) Pin which derivation of a frame's position is authoritative (F6): the manifest's
      `frame_index` column, or `build_slp_project.py:105,136`'s sort-by-`view_index`-and-enumerate,
      which never reads that column. They agree only because `selected_views` is ascending. Make the
      builder read the manifest, or delete the unused column — not both derivations

## 3. Port the image-copy step (unblocked by 0.6)

- [ ] 3.1 Port `copy_selected_images.py` as `labeling/copy_images.py`, behavior preserved —
      including the warn-and-continue on a missing source and the exit-0 summary (F5). The fail-loud
      change is 3.4, as its own commit
- [ ] 3.2 (RED) Characterization tests: the files copied and their names; that a pre-existing
      destination is **overwritten silently** (`shutil.copy2`, `:41`); and that the reported
      `copied` count counts copy *calls*, not resulting files (`:42`)
- [ ] 3.3 (RED) **Characterize the base-directory mismatch** (F8, which supersedes F5's absolute-path
      hypothesis — see 0.9). Two fixtures, both with complete, present data: a `scan_path` in
      `bloomctl` form (`images/Wave1/Day3_.../QR`, relative to the dir holding `scans.csv`) and one in
      legacy form (`./images_downloader_output/images/...`, relative to `experiment_dir`). Pin that
      the current code resolves the legacy form and misses **every** row of the `bloomctl` form by one
      path segment, yielding an empty `images/` with exit 0. Do **not** write an absolute-path
      characterization test — 0.9 established `bloomctl` never emits one, so there is no shipped
      behavior there to preserve
- [ ] 3.4 (GREEN) Replace character-stripping with an explicit resolution rule: resolve
      `source_image` against **the directory containing the `scans.csv` it was derived from** (how
      that base reaches the copy step is 7.2 — decide it before writing this), and reject an absolute
      `source_image` outright rather than mangling it. This is producer-agnostic — it resolves both
      the `bloomctl` and legacy conventions without detecting which is in play. Make **any**
      unresolved source fail the step; an empty or partial copy is never a success. Record in
      section 7
- [ ] 3.5 (RED) Test that a duplicate `output_filename` in the manifest is rejected rather than
      silently overwritten (F6). Pairs with 2.9, which is where the duplicate should be caught
      first — this is the second line of defence, since a hand-edited manifest can reach the copy
      step directly
- [ ] 3.6 Decide whether the copy step remains a separate stage or folds into the builder once
      `embed=True` lands (5.5). Keep them separate through section 5 so the characterization tests
      stay meaningful; revisit after

## 4. Port `build_slp_project.py` faithfully

- [ ] 4.1 Copy the script in as `labeling/build_package.py`, behavior preserved (**including
      `embed=False` at this step** — the embed change is section 5, as its own visible commit)
- [ ] 4.2 (RED) Characterization tests over a fixture: the package directory produced, its contents,
      and the `.slp` it writes
- [ ] 4.3 (GREEN) Make them pass without changing behavior
- [ ] 4.4 (RED) **Characterize the silent-empty-package failure before fixing it** (F1): with an
      unpopulated `images_dir`, the port warns per scan, writes both `.slp` files, and exits 0. Pin
      that, then make it fail loudly — an empty selection is never a successful build
- [ ] 4.5 (RED) Test that an unreadable/missing source scan fails the build **before** any package
      output is written — no partial directory left behind
- [ ] 4.6 (RED) Test that missing required package metadata (capture mode, skeleton name) fails the
      build with an error naming the field, before writing
- [ ] 4.7 (GREEN) Implement fail-fast ordering if the ported code writes before validating

## 5. The embed change — deliberate, isolated, tested

- [ ] 5.1 (RED) Test that a built package's `.slp` is self-contained: opened with the source scan
      paths made unreachable, it still yields its labeled frames. This test MUST fail against the
      section-4 port (which saves `embed=False`) — that failure is the point of the commit boundary
- [ ] 5.2 (GREEN) Change the builder to `save_slp(..., embed=True)` as an explicit step, with a
      comment recording *why*: six of the eight published collections carry
      `repaired_from: "v0"` / `embedded-images-repair` because the external reference broke, and the
      repair permanently caps the label set
- [ ] 5.3 (RED) Test that package validation rejects a package whose `.slp` references external
      images, so the guarantee holds for a package built by an older tool or by hand
- [ ] 5.4 Verify the embedded output against a real scan, not only a fixture — confirm the resulting
      file is a genuine `.pkg.slp` and note the size multiple observed (the eight existing
      collections run 170 MB – 1.2 GB, ~10x)
- [ ] 5.5 Decide whether `images/` still ships in the package once the `.slp` embeds them, or becomes
      redundant. It is what the labeler browses today; dropping it is a delivery change, not a
      correctness one

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

- [ ] 7.2 **Open, decide during section 3:** 3.4 resolves `source_image` against the directory
      holding the `scans.csv` it came from. That base has to reach the copy step somehow, and the two
      options are not equivalent in blast radius:
      (a) **carry it as a manifest column** — self-describing and immune to a wrong CLI argument, but
      it adds a column, so Decision 3's enumerated contract, task 2.8, the spec's manifest
      requirement, and #10's `LabelCard` consumer all move with it; or
      (b) **pass it as a CLI argument** to the copy step, replacing `experiment_dir` — no contract
      change, but a caller can still point it at the wrong directory, which is exactly the F8 failure
      re-opened one layer up.
      Lean (a): F8 is a mismatch between what the manifest *means* and what the caller *assumes*, and
      only (a) removes the assumption. But it changes a contract two changes read, so it is a
      decision to take deliberately rather than absorb inside 3.4

## 8. Package validation, CLI, and the workflow doc

- [ ] 8.1 Implement `labeling/validate.py` (or equivalent): the layout, manifest-column, frame-count,
      and self-containment checks as one callable that fails before any network call — this is what
      #10's `publish-labels` will call
- [ ] 8.2 (RED) Tests for each rejection path, each asserting the error names the offending piece
- [ ] 8.3 Define and write the package metadata file — **new design, not ported** (F4): nothing in
      the vault scripts emits capture mode, skeleton name, or `bloom_experiment_id` in a parseable
      form. Source its *values* from where they live today (F7): `bloom_experiment_id` from
      `generate_readme.py:66`, the accession map from `:85-89`, the skeleton from `skeletons.yaml`
      per Decision 7. Each of those has two hand-synced copies today; this file is what makes it one
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
      accession-name lookup as a manual prerequisite (F2) rather than an in-repo step
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
