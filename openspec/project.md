# Project Context

## Purpose
`sleap-roots-training` is a config-driven pipeline for **training and evaluating SLEAP root
models** on the modern `sleap-nn` (PyTorch) backend. It replaces the notebook-based
`eberrigan/sleap-roots-training` workflow with a reproducible, tested package.

Goals (built out tier by tier; see the program roadmap):
- Finish the **generalist** (multi-species) keypoint models and compare them against
  **per-crop / per-root-type specialist** models.
- Unify per-species skeletons to a common, performance-validated node count before combining
  datasets.
- Extend to SLEAP's **segmentation-mask** outputs (SAM-predict → review/correct → train).
- Keep experiments reproducible via OmegaConf configs + Weights & Biases artifact lineage.

## Tech Stack
- Python ≥ 3.11, packaged with **uv** + `uv_build`.
- **OmegaConf** for configuration (experiments are config files, not notebooks).
- **`sleap-nn`** (PyTorch) training/inference backend; **`sleap-io`** for `.slp` data. Installed
  via the optional `train` extra — see [docs/training-backend.md](../docs/training-backend.md).
- **Weights & Biases** for experiment tracking + the `sleap-roots-labels` / `sleap-roots-models`
  registries; **Run:AI** GPU cluster for compute.
- **click** CLI; **pytest** tests; **ruff** (pydocstyle/google) + **black** (line length 88).

## Project Conventions

### Code Style
- `black` (line length 88) + `ruff` with the `D` (pydocstyle, google convention) ruleset.
- `src/` layout; public modules/functions/classes require google-style docstrings (tests exempt).
- Repo name uses hyphens (`sleap-roots-training`); the importable package uses underscores
  (`sleap_roots_training`).

### Architecture Patterns
- Config-driven: an experiment is a config file — a thin, repo-owned `experiment` block composed
  over `sleap-nn`'s own `TrainingJobConfig` (validation delegated, not reimplemented); the
  `validate` CLI checks configs.
- Thin, well-bounded modules with clear interfaces; mirror `sleap-roots-analyze` structure.
- `sleap-nn` / `sleap-io` are consumed as libraries (pinned to tagged releases; commit pins only as
  a documented last-resort stopgap) — we do not modify their internals.

### Testing Strategy
- TDD. Unit tests are fast and run in CI across OS × Python (3.11/3.12). Slow tests that run real
  training/inference are marked `@pytest.mark.integration` and skipped in the default CI run.
- Keep `main` green: `black --check`, `ruff check`, and `pytest` must pass before every commit.

### Git Workflow
- Trunk-based on `main`; feature branches → PRs with CI. One **OpenSpec change per PR**, archived
  with the code on merge. Conventional, descriptive commit messages.

## Domain Context
SLEAP root skeletons are linear chains of evenly-spaced nodes (base = `r1` … tip = last node).
Different crops/root types use different node counts, so combining datasets requires skeleton
unification (resampling to a common node count) — node count affects model accuracy and is chosen
empirically. Models are graded **reproduce-or-beat** against an established PyTorch baseline (the
old TensorFlow `sleap-train` numbers are reference only, since backends differ).

## Important Constraints
- **W&B is the system of record** for labeled data + model versioning (not Bloom; Bloom is the
  image source, Box is delivery).
- Mask training/inference features are now released (`sleap-nn` v0.3.0, `sleap-io` 0.8.0/0.9.1), so
  Phase 2 pins to those tagged releases; Phase 1 stays capped below them until the Tier 6 re-verify.

## External Dependencies
- `talmolab/sleap-nn`, `talmolab/sleap-io` (backends / data layer).
- Weights & Biases (experiment tracking + model/label registries), Run:AI (GPU compute).
- `talmolab/sleap-app` (#155 mask-review GUI) — coordinated, contributed-to, not owned here.
