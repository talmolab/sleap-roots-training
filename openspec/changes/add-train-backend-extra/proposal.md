# Proposal: Add optional `train` backend extra + verified keypoint train/predict runbook

## Why

Roadmap **Tier 0.5** (issue #9) is a week-1 prerequisite that gates Tier 1's config-driven training
work. Before we design a config schema against the `sleap-nn` backend, we must prove that backend
installs, trains, and predicts keypoints end-to-end on real hardware, and lock the Phase-1
dependency pins to tagged releases. Today `sleap-nn`, `sleap-io`, and `torch` are absent from
`pyproject.toml` entirely, so this de-risks Tier 1 by establishing a known-good, release-pinned
backend path that later training tiers build on.

## What Changes

- Add an optional **`[project.optional-dependencies].train` extra** declaring the `sleap-nn`
  backend (`sleap-nn`, `sleap-io`, and `torch` listed explicitly) with PEP 440 release specifiers
  (no commit-hash pins), capped below the unverified v0.3.0 / sleap-io 0.8.0 mask line
  (`sleap-nn>=0.2.0,<0.3.0`, `sleap-io>=0.7.1,<0.8.0`). The base install stays lean so the
  cross-platform CI matrix is unaffected. The caps are the sole mechanism stopping a silent upgrade
  to the unverified mask line, so a test asserts them, not just the floor.
- Add a canonical **`docs/training-backend.md` runbook** with the install command, the exact
  verified `sleap-nn` keypoint train + predict commands run against a sample dataset, and the
  recorded GPU compute-capability / `torch.cuda.get_arch_list()` findings.
- Add an **integration-marked GPU smoke test** (`tests/test_gpu.py`) that asserts CUDA availability
  and records arch/capability, self-skips when torch/GPU are absent, and is excluded from the
  default `-m "not integration"` CI run.
- Add a **CI-safe pyproject parse test** asserting the `train` extra declares all three backends
  with release specifiers only, that the floor and both caps hold, and that the base install stays
  lean; plus a **docs-contract test** asserting the runbook's structural completeness.
- **Correct now-false upstream facts** that the change's own research disproves: `sleap-nn` v0.3.0
  and `sleap-io` 0.8.0/0.9.1 are already released, so `openspec/project.md` "Important Constraints"
  and `docs/roadmap.md` "Upstream version pins" are updated (with a dated roadmap revision-log
  entry) to reflect that Phase 2 can pin to released tags — no upstream cut needs coordinating.
- Regenerate and commit **`uv.lock`**; add a `docs/CHANGELOG.md` entry.

## Impact

- **Affected specs:** `training-backend` (ADDED).
- **Affected code:** `pyproject.toml` (add `train` extra; add `packaging` to `dev`; cap
  `requires-python` or marker-gate the extra to match sleap-nn's `<3.14`); `uv.lock` (regenerated);
  `tests/test_train_extra.py`, `tests/test_gpu.py`, `tests/test_backend_docs.py` (new);
  `docs/training-backend.md` (new); `README.md` (one-line pointer); `openspec/project.md`
  (Tech-Stack note + "Important Constraints" fact correction); `docs/roadmap.md` ("Upstream version
  pins" correction + a dated revision-log entry); `docs/CHANGELOG.md`.
- **No workflow change:** the `integration` marker and the `-m "not integration"` CI filter already
  exist, so `.github/workflows/` is untouched.
- **Breaking changes:** none (additive optional extra; the base install is unchanged).
