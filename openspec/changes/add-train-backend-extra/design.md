## Context

Roadmap **Tier 0.5** (issue #9) mandates: verify `sleap-nn` keypoint training works end-to-end on a
sample dataset, document the exact train/predict commands, and lock the Phase-1 release pins. The
roadmap's "Upstream version pins (releases first)" section requires Phase 1 to pin to a released
`sleap-nn` (v0.2.0+) and its released `sleap-io` — **no commit-hash pins** (those are reserved as a
documented stopgap for the still-unreleased mask features).

Exploration established the true starting point: `sleap-nn`, `sleap-io`, and `torch` are **absent
from `pyproject.toml`** (confirmed against `uv.lock`). So this is a first-time dependency addition,
not a pin edit. The package currently ships only the model-registry (`seed-registry`) surface plus
the OmegaConf CLI scaffold; there is no training/predict code (that is Tier 1,
`openspec/changes/add-config-schema/`).

The real training run is **manual, on a remote Windows desktop with an RTX A5000** (Ampere,
compute capability `sm_86`), reached over SSH. CI has **no GPU runner** and its six legs
(ubuntu/windows/mac × py3.11/3.12) install only `--group dev` and run `pytest -m "not integration"`
(`.github/workflows/ci.yml`). So the end-to-end train/predict is not a CI step; its evidence is
recorded in docs. The roadmap's "Oracle / validation philosophy" is explicit that exact numeric
parity with the legacy TensorFlow backend is **not** the bar — the point here is that the path
works, not that the model is good.

Research (PyPI / GitHub / the v0.2.0 `pyproject.toml`, cited in the PR) confirmed: `sleap-nn==0.2.0`
is a published pure-Python wheel depending on `sleap-io>=0.7.0,<0.8.0` (latest in range: `0.7.1`)
and unpinned `torch` (via `torchvision>=0.20.0`, `lightning`); it supports Python `>=3.11,<3.14`.
The A5000 needs the CUDA 12.8 (`cu128`) torch wheel, whose `get_arch_list()` includes `sm_86`
natively (no PTX-JIT fallback for this card — to be confirmed empirically at the spike).

## Goals / Non-Goals

- **Goals:** an installable, release-pinned `train` backend extra; a documented, real-run-verified
  keypoint train/predict path plus the recorded GPU arch findings; an integration-marked GPU smoke
  test; CI-safe tests that lock the pins-declaration contract; a CHANGELOG entry.
- **Non-Goals:** running training in CI; commit-hash pins; any training/predict *code* or config
  schema (Tier 1); mask features (`sleap-nn` v0.3.0 / `sleap-io` 0.8.0, Phase 2); editing the
  roadmap tier narrative (append-only, tracked via issues + CHANGELOG).

## Decisions

### D1 — Optional extra, not core dependencies

Backend deps go under `[project.optional-dependencies].train`, so `pip install
sleap-roots-training` stays lean and cross-platform and `pip install sleap-roots-training[train]`
opts into the heavy backend. Alternatives: (a) core `[project.dependencies]` — **rejected**: it
bloats every install with torch (~GB) and risks universal-resolution failure across all six CI legs
for a backend CI never exercises; (b) a `[dependency-groups]` group like `dev` — **rejected**:
dependency-groups are developer-facing and not exposed to end users / Run:AI, whereas an extra is
the standard `pkg[train]` install surface consumers need.

### D2 — Release specifiers with next-minor caps

`sleap-nn>=0.2.0,<0.3.0`, `sleap-io>=0.7.1,<0.8.0`, and a `torch` floor. Capping the next minor
mirrors the repo's existing `wandb>=0.28.0,<0.29.0` convention (archived change, D10): it keeps the
pins on tagged releases (the lock freezes exact versions) while stopping `uv lock --upgrade` from
silently pulling the **unverified** v0.3.0 mask line / sleap-io 0.8.0. Raising the caps is gated by
the Tier 6 mask re-verify. Because the caps — not the floor — are the load-bearing safety property,
the parse test asserts them directly (rejects `sleap-nn` 0.3.0 and `sleap-io` 0.8.0), and `torch` is
listed **explicitly** in the extra so the requirement's "declares sleap-nn, sleap-io, and torch"
prose is literally true (resolving the earlier open question). Alternatives: unpinned (**rejected** —
non-reproducible); commit-hash pin (**rejected** — the roadmap says releases-first, and both
releases exist on PyPI).

### D3 — CI-safe verification is a pyproject *parse* test, not an install test

Installing the `train` extra in CI would pull torch across six legs — exactly what D1 avoids — and
needs network. So the CI-safe test **parses** `pyproject.toml` (stdlib `tomllib` + `packaging`) and
asserts the declaration *shape*: the `train` extra exists, every entry is a PEP 440 release
specifier with no VCS/URL/commit reference, `sleap-nn` admits `0.2.0` and rejects `0.1.0`, and the
base deps are lean. Real installability is the manual spike, recorded in the runbook. `packaging` is
added to `dev` (task 1.1) so the test's dependency is declared, not an undeclared pytest transitive.

### D4 — GPU test: marker + self-skip (two independent guards)

`@pytest.mark.integration` keeps the GPU test out of the default `-m "not integration"` CI run;
`torch = pytest.importorskip("torch")` (inside the test body, never at module scope) plus a
`pytest.skip` when `not torch.cuda.is_available()` keep it from *erroring* when collected on a
torch-less/GPU-less host. Mirrors `talmolab/sleap-roots-predict/tests/test_gpu.py`, extended to
record `get_device_capability()` and `get_arch_list()`. A separate CI-safe assertion (task 2.2)
proves the deselect/skip behavior itself.

### D5 — Regenerate and commit `uv.lock` with pyproject

Adding an extra changes uv's universal resolution, and both CI jobs run `uv sync --locked`, which
fails on a stale lock. So `uv lock` runs and `uv.lock` is committed in the same commit as the
pyproject edit. `uv sync --group dev` still does not fetch the extra's packages, so CI stays lean —
confirmed at the spike (task 4.4). `uv.lock` is already in the CI `paths` filter, so this change
triggers CI.

### D6 — One canonical doc home + a README pointer (DRY)

`docs/training-backend.md` is the single home for the install/train/predict/arch content, scoped as
a **runbook, not a tutorial**; `README.md` gets a one-line pointer next to "Install (development)"
(not a duplicated install block) and `openspec/project.md` gets a one-line Tech-Stack note. The
runbook and README have a clean boundary — README = dev setup + pointer; runbook = the `[train]`
extra install + train/predict + arch — so neither restates the other.

### D7 — Correct the now-false upstream facts (not "no roadmap edit")

An earlier draft deferred all roadmap/`project.md` edits on an "append-only, matches the archived
change" rationale. That was wrong on both counts: the roadmap's *body* is revised in place (the
2026-07-13 revision edited live tier content) and only the **dated revision log** is append-only;
and the archived change skipped the roadmap because it was *non-tiered adjacent work*, whereas this
change directly executes **Tier 0.5 (#9)**. Because the change's own research establishes that
`sleap-nn` v0.3.0 and `sleap-io` 0.8.0/0.9.1 are already released, two source-of-truth docs now
assert the opposite of what we proved, and the roadmap is mirrored to the team's Notion tracker.
**Decision:** correct the facts in this PR — rewrite `openspec/project.md` "Important Constraints"
(masks no longer pending an unreleased cut) and `docs/roadmap.md` "Upstream version pins" (Phase 2
pins to released tags; the "coordinate the cut" action downgrades to "confirm at Tier 6"), and
append a dated **Roadmap revision (2026-07-21)** log entry recording the correction. We do **not**
mark Tier 0.5 "done" (completion is tracked by #9 + the CHANGELOG per the JIT policy) and do **not**
edit prior dated log entries — so this corrects forward-looking facts without touching history.

## Risks / Trade-offs

- **Unbounded `requires-python = ">=3.11"` × sleap-nn's `<3.14` cap.** *Resolved empirically:* the
  predicted `>=3.14`-fork failure did **not** occur — uv 0.11.30 auto-narrows the extra via
  sleap-nn's own `requires-python <3.14`, so `uv lock` resolved the whole universal space cleanly
  with no `requires-python` cap and no marker (task 1.4 / 4.4). Residual risk: an *older* CI uv that
  does not auto-narrow could fail `uv lock`/`--locked`; `astral-sh/setup-uv@v6` installs a current
  uv, so this is low. Fallback if it ever bites: cap `requires-python` to `>=3.11,<3.14` or
  marker-gate the extra with `python_version < "3.14"`.
- **Cross-platform `uv lock` resolution** of torch/torchvision/opencv/skia-python across the
  universal marker space (linux/win/mac-arm64 × py3.11/3.12/3.13) could fail on a leg. Surfaced at
  `uv lock` time on the Mac (the spike), not in CI. Mitigation: environment markers or a narrower
  platform set; this is exactly the kind of risk Tier 0.5 exists to find early.
- **`uv.lock` does not reproduce the GPU box.** `--torch-backend=cu128` is a `uv pip install`
  feature that bypasses the lock, so the committed lock governs only CI's lean resolution; the
  training environment is a fresh PyPI-name resolution (torch redirected to the cu128 index) that
  still honors the pyproject caps but resolves different exact transitive pins. Stated explicitly in
  the runbook so no one assumes the lock reproduces the box.
- **The pinned torch wheel could lack native `sm_86` kernels** (PTX-JIT fallback). Mitigation: the
  GPU test records `get_arch_list()`; the runbook states the native-vs-JIT verdict for the A5000.
- **`uv lock --upgrade` pulling the unverified v0.3.0 / sleap-io 0.8.0 mask line.** Mitigation: the
  `<0.3.0` / `<0.8.0` caps (D2); raising them is gated by the Tier 6 re-verify.
- **Install-command drift** between the README and the runbook. Mitigation: single canonical home +
  a pointer (D6).
- **The "verified against a real run" scenario is observable, not CI-testable.** It is labeled a
  manual task (task 4); its evidence lives in the runbook + PR body and is never faked as a passing
  CI test.

## Migration Plan

Additive and reversible, in five commits + a manual spike + a follow-up archive:

1. `build(deps): add optional train backend extra + regenerate lock` — `pyproject.toml` (extra +
   `packaging` in dev + the requires-python fix), `uv.lock`, `tests/test_train_extra.py`, and the
   `openspec/changes/**` scaffold. pyproject + lock move **together** (a stale lock reds all six
   legs). CI: green.
2. `test: add integration-marked GPU smoke test` — `tests/test_gpu.py`. CI: green (deselected;
   importorskip in body → no collection error).
3. `docs: add training-backend runbook skeleton + docs-contract test` — `docs/training-backend.md`
   (arch = placeholder), `tests/test_backend_docs.py` (presence-only), README pointer,
   `openspec/project.md` note + constraint fix, `docs/roadmap.md` correction + revision entry. CI:
   green.
4. `docs: record train extra + runbook + GPU test in CHANGELOG` — `docs/CHANGELOG.md`. CI: green.

Then **push and open a draft PR** so the 6-leg matrix validates commits 1–4 while the spike runs in
parallel. On the A5000 over SSH: pull the same branch, `uv pip install ".[train]"
--torch-backend=cu128`, run the torch introspection + the sample train/predict + the integration GPU
test, and report the outputs back.

5. `docs: backfill A5000 arch findings + verified commands` — `docs/training-backend.md` filled in;
   the docs-contract check is extended to require a concrete `sm_\d+`/`get_arch_list` token and no
   `TODO`/`TBD`. Mark the PR ready → `/pre-merge-check` → merge.

The OpenSpec change is archived in a **separate follow-up PR** (`cleanup-merged`), per the #4 → #5
precedent; the archive move is under `openspec/**`, outside the CI paths filter. Rollback: the extra
is additive/optional and `git revert` of commit 1 restores the lean base install **and** a
consistent lock in one shot (they moved together); commits 2–5 are tests/docs with no runtime impact.

## Open Questions

- `torch` is now listed **explicitly** in the extra (resolving the earlier transitive-vs-explicit
  question, so the requirement prose holds); its exact floor (whether a `>=2.8.0` floor is needed to
  guarantee cp312/Windows `cu128` wheels) is confirmed at the lock/spike step.
- The unbounded-`requires-python` question is *closed*: uv 0.11.30 auto-narrowed the extra at
  `uv lock`, so neither a `<3.14` cap nor a marker was needed (task 1.4 / 4.4). `torch` is pinned
  `>=2.5.0` (the effective floor from `torchvision>=0.20.0`); the lock froze torch 2.13.0.
- Whether the Windows host runs native Windows or WSL2 (changes the install shell and whether the
  `windows-latest` CI leg is representative) — confirmed with the operator before the spike.
- Phase 2 is **no longer blocked on an unreleased upstream**: `sleap-nn` v0.3.0 and `sleap-io`
  0.8.0/0.9.1 are already tagged/published. So the roadmap's "coordinate the v0.3.0 / sleap-io 0.8.0
  cut" action downgrades to "confirm Phase 2 can pin to the released tags at Tier 6" — recorded in
  the PR, no upstream release needs to be cut.
- **Cross-platform install coverage (PR #15 review).** Installing the `train` extra is exercised
  only by the macOS universal-lock resolution plus one real Windows/A5000 install — **not** by CI
  (CI never installs the extra, by design, to stay lean). This is an accepted, reviewer-acknowledged
  risk, not a claim of full matrix coverage.
- **Deferred to Tier 1: pin strength vs a re-verification gate.** The GPU-box install bypasses
  `uv.lock` (via `--torch-backend`), so a future `sleap-nn` 0.2.x *patch* could change behavior with
  no automatic re-verify before results feed W&B lineage. Decide before Tier 1 records training
  results: exact-pin `sleap-nn` (vs the current minor-cap) or add a patch-release re-verification
  gate.
