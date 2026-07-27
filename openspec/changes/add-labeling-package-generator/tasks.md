## 0. Obtain the source and confirm scope

**This section gates the rest.** The port is a port — nothing below starts from a description of what
the scripts do.

- [ ] 0.1 Fetch the onboarding bundle from Box
      (`Phenotyping_team_GH/sleap-roots-training/onboarding/`,
      https://salkinstitute.box.com/s/mznt60av95xcfn981dumh4qoccw420j0): the
      `/build-labeling-package` command doc, `build_slp_project.py`, `select_samples.py`, and the
      `bloomctl` setup guide. Record the copy date — the vault repo's history does not survive the
      Box copy, so the porting commit is the only place provenance can live
- [ ] 0.2 Read both scripts end to end before writing anything. Specifically establish: what
      `select_samples.py` reads to choose frames (Bloom API? a local manifest? scan directory
      listing?), whether selection is deterministic today, and what `build_slp_project.py` assumes
      about paths and platform
- [ ] 0.3 **Re-scope gate.** If the Bloom coupling is larger than "read metadata, pick frames" — e.g.
      the scripts orchestrate downloads, or carry credentials handling — stop and split it out rather
      than absorbing it silently. Record the finding either way
- [ ] 0.4 Confirm the Decision 2 placement with eberrigan on #26: embedding moves into the
      **builder**, and #10's `publish-labels` *verifies* self-containment rather than performing it.
      This departs from the issue's stated placement; the reasoning is in design.md
- [ ] 0.5 Confirm the Decision 4 dependency call: `sleap-io` in core `dependencies`, or an extra if
      `feat/add-train-backend-extra` establishes an extras convention first

## 1. Dependency and module skeleton

- [ ] 1.1 Add `sleap-io` to `pyproject.toml` per 0.5, pinned to a release; `uv lock`
- [ ] 1.2 Create `src/sleap_roots_training/labeling/` with `__init__.py`, mirroring the `registry/`
      package's shape (thin, well-bounded modules; google-style docstrings; `from __future__ import
      annotations`)
- [ ] 1.3 Add `tests/test_labeling_*.py` files matching the existing `test_registry_*.py` naming

## 2. Port `select_samples.py` faithfully

- [ ] 2.1 Copy the script in as `labeling/select_samples.py` with **behavior preserved**, adapting
      only what cannot run here (Windows path assumptions, interactive prompts, unpinned imports).
      Record every deviation as a task under section 6 — deviations are decisions, not cleanup
- [ ] 2.2 (RED) Characterization tests over a small fixture: the frames selected, their order, and
      the manifest rows produced. These pin the *ported* behavior before anything changes
- [ ] 2.3 (GREEN) Make the characterization tests pass without altering selection semantics
- [ ] 2.4 (RED) Test that selection is deterministic — the same inputs and parameters select the same
      frames in the same order across runs
- [ ] 2.5 (GREEN) If 2.4 fails, make selection deterministic (seed, or a stable sort over an
      explicitly ordered key) and record it as a deliberate deviation, not an incidental fix
- [ ] 2.6 (RED) Test that a widened re-run is a superset of the narrower one
- [ ] 2.7 (RED) Test that `sample_manifest.csv` has one row per selected frame and carries every
      required column (`scan_id`, `plant_qr_code`, `plant_age_days`, `accession_id`,
      `accession_name`, `wave_number`, `view_index`, `frame_index`, `source_scan_path`,
      `source_image`, `output_filename`)

## 3. Port `build_slp_project.py` faithfully

- [ ] 3.1 Copy the script in as `labeling/build_package.py`, behavior preserved (**including
      `embed=False` at this step** — the embed change is section 4, as its own visible commit)
- [ ] 3.2 (RED) Characterization tests over a fixture: the package directory produced, its contents,
      and the `.slp` it writes
- [ ] 3.3 (GREEN) Make them pass without changing behavior
- [ ] 3.4 (RED) Test that an unreadable/missing source scan fails the build **before** any package
      output is written — no partial directory left behind
- [ ] 3.5 (RED) Test that missing required package metadata (capture mode, skeleton name) fails the
      build with an error naming the field, before writing
- [ ] 3.6 (GREEN) Implement fail-fast ordering if the ported code writes before validating

## 4. The embed change — deliberate, isolated, tested

- [ ] 4.1 (RED) Test that a built package's `.slp` is self-contained: opened with the source scan
      paths made unreachable, it still yields its labeled frames. This test MUST fail against the
      section-3 port (which saves `embed=False`) — that failure is the point of the commit boundary
- [ ] 4.2 (GREEN) Change the builder to `save_slp(..., embed=True)` as an explicit step, with a
      comment recording *why*: six of the eight published collections carry
      `repaired_from: "v0"` / `embedded-images-repair` because the external reference broke, and the
      repair permanently caps the label set
- [ ] 4.3 (RED) Test that package validation rejects a package whose `.slp` references external
      images, so the guarantee holds for a package built by an older tool or by hand
- [ ] 4.4 Verify the embedded output against a real scan, not only a fixture — confirm the resulting
      file is a genuine `.pkg.slp` and note the size multiple observed (the eight existing
      collections run 170 MB – 1.2 GB, ~10x)

## 5. Package validation, CLI, and the workflow doc

- [ ] 5.1 Implement `labeling/validate.py` (or equivalent): the layout, manifest-column, frame-count,
      and self-containment checks as one callable that fails before any network call — this is what
      #10's `publish-labels` will call
- [ ] 5.2 (RED) Tests for each rejection path, each asserting the error names the offending piece
- [ ] 5.3 Wire the build + validate commands into `cli.py` as a `labeling` group, mirroring how
      `seed_registry_command` is exposed
- [ ] 5.4 (RED) CLI tests mirroring `tests/test_registry_cli.py`: a successful build reports the
      package path; a validation failure exits non-zero with the error and writes nothing
- [ ] 5.5 Port `/build-labeling-package` into `.claude/commands/build-labeling-package.md`, updated
      to drive the in-repo CLI rather than vault script paths
- [ ] 5.6 Document continue-labeling as **re-derive + republish** in the workflow doc: re-fetch via
      `bloomctl download --experiment-id <id>`, re-select wider, publish a new version — with the
      `save_slp` truncation reason stated, not just the instruction

## 6. Port deviations (fill in during sections 2–4)

- [ ] 6.1 Record each deviation from the vault scripts: what changed, why it could not be preserved,
      and whether it is visible to a caller. An empty section here means the port was faithful; it
      should not be empty by omission

## 7. Validation and handoff

- [ ] 7.1 `uv run openspec validate add-labeling-package-generator --strict`
- [ ] 7.2 `uv run pytest`, `uv run black --check src tests`, `uv run ruff check src tests`
- [ ] 7.3 Confirm CI passes on 3.11 and 3.12 — `sleap-io` is a new dependency and this is the first
      code in the repo that touches `.slp` files
- [ ] 7.4 Comment on #10 that the package layout is now real, naming the validate entry point
      `publish-labels` should call, so `add-label-registry` can be built against it rather than
      against a description
- [ ] 7.5 Close #26 referencing the ported modules, the embed commit, and the deviations in section 6
