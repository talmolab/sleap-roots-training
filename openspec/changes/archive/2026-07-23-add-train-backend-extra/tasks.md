# Tasks

Convention: commit each failing test **together with** its implementation so `main` is green after
every commit (never a red commit), mirroring the archived registry change. `pyproject.toml` and
`uv.lock` MUST move in the **same** commit (a stale lock reds all six CI legs via `uv sync
--locked`). The docs-contract test asserts **presence only** — never spike-derived content — so the
runbook skeleton commit stays green before the manual spike backfills real findings.

## 0. Validate the scaffold

- [x] 0.1 Run `openspec validate add-train-backend-extra --strict`; fix any format issues.

## 1. Train extra + pins contract (CI-safe unit — no network)

- [x] 1.1 Add `packaging` to `[dependency-groups].dev` so the parse test has a declared dependency
      (not an undeclared transitive of pytest), satisfied on every CI leg.
- [x] 1.2 Write the failing `tests/test_train_extra.py`. Resolve `pyproject.toml` via
      `Path(__file__).resolve().parents[1] / "pyproject.toml"`; open in binary (`"rb"`) for
      `tomllib.load`; guard the `train` key with an explicit `assert ... , "<msg>"` (via `.get()`)
      so an absent extra FAILs cleanly rather than ERRORing. Assert:
      - the `train` extra is present and non-empty, and declares all of {`sleap-nn`, `sleap-io`,
        `torch`} via `packaging.utils.canonicalize_name`;
      - every entry parses as a `packaging.requirements.Requirement` with `req.url is None` and no
        `@` direct reference;
      - the `sleap-nn` specifier admits `Version("0.2.0")` and rejects `Version("0.1.0")`
        **and** rejects `Version("0.3.0")`;
      - the `sleap-io` specifier admits `Version("0.7.1")` and rejects `Version("0.8.0")`;
      - the base `[project].dependencies` contains none of {`sleap-nn`, `sleap-io`, `torch`}
        (name-normalized).
- [x] 1.3 Run the test → confirm it FAILs (the extra is absent; fails on the feature, not on a
      missing `packaging` or a KeyError). *Confirmed: 3 clean assertion FAILs, `test_base_install_
      stays_lean` already passed.*
- [x] 1.4 Add `[project.optional-dependencies].train` listing `torch>=2.5.0` **explicitly**
      alongside `sleap-nn>=0.2.0,<0.3.0` and `sleap-io>=0.7.1,<0.8.0`. Run `uv lock`; commit
      `pyproject.toml` + `uv.lock` **together**. *Deviation (Why no requires-python fix): the
      predicted `>=3.14`-fork lock failure did NOT occur — uv 0.11.30 auto-narrows the extra via
      sleap-nn's own `requires-python <3.14`, so `uv lock` resolved cleanly (sleap-nn 0.2.0,
      sleap-io 0.7.1, torch 2.13.0) with no cap or marker. Left the base `requires-python` unbounded
      and the extra marker-free; re-check if CI's uv is older than 0.11.30.*
- [x] 1.5 Run the test → green (4 passed); `uv sync --locked --group dev` passes and installs **no
      torch** (extra not selected); `uv run black --check src/sleap_roots_training tests` and
      `uv run ruff check src/sleap_roots_training` clean.

## 2. Integration-marked GPU smoke test (not in default CI)

- [x] 2.1 Write `tests/test_gpu.py`: `@pytest.mark.integration`; **no torch import at module
      scope** — `torch = pytest.importorskip("torch")` inside the test body; `if not
      torch.cuda.is_available(): pytest.skip(...)`; assert `torch.cuda.is_available()`; record
      `get_device_name(0)`, `get_device_capability()`, and `get_arch_list()` via print; assert
      `get_arch_list()` is non-empty.
- [x] 2.2 (CI-safe) Confirm the guard contract in the default environment: `pytest -m "not
      integration"` DESELECTS it (suite stays green) and a full `pytest` in the torch-less dev env
      SKIPS it (no collection error). *Confirmed on the Mac: `-m "not integration"` → 1 deselected /
      0 selected; full run → 1 skipped ("could not import 'torch'"), no collection error.*

## 3. Runbook + docs-truth corrections (docs + CI-safe contract test)

- [x] 3.1 Write the failing `tests/test_backend_docs.py`. Resolve the doc via
      `Path(__file__).resolve().parents[1] / "docs" / "training-backend.md"`; read with
      `encoding="utf-8"` and normalize `\r\n`→`\n` before all assertions (Windows CI leg). Assert
      **presence only**: the `sleap-roots-training[train]` install token, a fenced `sleap-nn` train
      command, a fenced predict command, and a compute-capability / arch section heading.
- [x] 3.2 Run the test → confirm it FAILs (doc absent).
- [x] 3.3 Write `docs/training-backend.md` — the single canonical home for install (`[train]` extra
      via `pip install ".[train]"` / `uv pip install ".[train]" --torch-backend=cu128`), the
      verified train + predict commands, a sample-dataset pointer, and the GPU/arch findings (arch
      section a clearly-marked placeholder to backfill from task 4). Keep it a **runbook, not a
      tutorial**. Add a one-line pointer next to README "Install (development)" (pointer only — do
      NOT restate the commands, DRY); add a one-line Tech-Stack note in `openspec/project.md`.
- [x] 3.4 Run the test → green; lint clean.
- [x] 3.5 Correct now-false upstream facts (the change's own research proves `sleap-nn` v0.3.0 and
      `sleap-io` 0.8.0/0.9.1 are already released):
      - `openspec/project.md` "Important Constraints": rewrite the "mask features … pending the
        v0.3.0 / sleap-io 0.8.0 releases" line to state those releases exist, so Phase 2 pins to
        tagged releases (drop the "commit pins only … for unreleased mask features" framing where it
        implies they are unreleased).
      - `docs/roadmap.md` "Upstream version pins": update the Phase-2 bullet + the "Action" line
        (masks are no longer pending an unreleased cut → confirm Phase-2 pins against the released
        tags at Tier 6), and append a new dated **Roadmap revision (2026-07-21)** log entry
        recording the correction and citing Tier 0.5 / #9 as the source. Do NOT mark Tier 0.5 "done"
        (completion is tracked by #9 + CHANGELOG per the JIT policy); do NOT edit prior dated log
        entries.

## 4. Manual verification spike (remote Windows RTX A5000; NOT CI, NOT a merge gate)

- [x] 4.1 On the training host, install from the **checkout**: `uv pip install ".[train]"
      --torch-backend=auto`. *Done on the A5000 (native Windows): resolved sleap-nn 0.2.0 /
      sleap-io 0.7.1 / torch 2.8.0+cu129; `torch.cuda.is_available()` True. Trained the BermanFlies
      sample (2 epochs, ~49 s) via `sleap-nn train --config config.yaml`; the run also produced
      predictions (`labels_pr.val.0.slp`) + metrics (val mOKS 0.186, avg dist 4.15 px). Standalone
      inference verified via `sleap-nn track` (0.2.0's checkpoint-inference CLI). Two 0.2.0 caveats
      recorded in the runbook: input config needs `data_config.preprocessing`; `predict` is
      ONNX-export (use `track`).*
- [x] 4.2 Run `pytest -m integration tests/test_gpu.py` on that host; capture the compute capability
      and `torch.cuda.get_arch_list()` output; record whether kernels are native or PTX-JIT for
      `sm_86`. *Done: 1 passed; capability `(8,6)`; arch list
      `['sm_70','sm_75','sm_80','sm_86','sm_90','sm_100','sm_120']` → `sm_86` native, no PTX-JIT.*
- [x] 4.3 Backfill the exact commands + arch findings into `docs/training-backend.md` as an
      **explicit commit** (`docs: backfill A5000 arch findings + verified commands`); paste the
      console output into the PR description. Extend the docs-contract check so it now asserts a
      concrete arch token (regex `sm_\d+` or literal `get_arch_list`) is present and no `TODO`/`TBD`
      placeholder remains — so scenario "verified against a real run" cannot merge unmet.
- [x] 4.4 Confirm the `train` extra resolved in `uv.lock` across all matrix platform tags at
      `uv lock` time. *Done on the Mac: `uv lock` resolved the full universal space (212 packages)
      without error and `uv sync --locked --group dev` stays consistent + torch-free. The
      unbounded-`requires-python` × sleap-nn `<3.14` concern did not bite (uv 0.11.30 auto-narrows —
      see 1.4).* Note in the runbook that `--torch-backend` bypasses `uv.lock`, so the committed
      lock governs only CI's lean resolution, not the GPU box's exact torch pins (runbook task 3.3).

## 5. Changelog + verification

- [x] 5.1 Append to the existing `## [Unreleased]` / `### Added` in `docs/CHANGELOG.md` (do not
      create a second `### Added`): the optional `train` backend extra, the verified keypoint
      runbook, and the integration GPU smoke test. (Do not duplicate the install command or restate
      the upstream-release fact here — those live in the runbook and the roadmap correction.)
- [x] 5.2 Verify with CI's exact invocations: `uv sync --locked --group dev`; `uv run pytest -m
      "not integration" tests/` green; `uv run pytest tests/` (no marker filter) confirms
      `test_gpu.py` is SKIPPED (not errored) in the torch-less env; `uv run black --check
      src/sleap_roots_training tests`; `uv run ruff check src/sleap_roots_training`; `uv build`
      (wheel builds — the extra is metadata); confirm the GPU test is deselected in the default run.

## 6. Git / PR flow (CI-safety notes)

- [x] 6.1 Push the branch and open a **draft PR** — a feature-branch push alone does not trigger CI
      (the `push` trigger is `branches: [main]` only); `pull_request: opened` fires the 6-leg matrix
      so commits 1–4 validate while the spike (task 4) runs in parallel on the A5000 (which pulls
      the same branch). *Done: PR #15 (opened by the operator); the 6-leg matrix ran green.*
- [x] 6.2 After the backfill commit (4.3), mark the PR ready and run `/pre-merge-check`. *Done: CI
      7/7 pass; reviewed by 3 reviewers (2 approvals); review feedback addressed in commit 89373ac;
      squash-merged as e8e410f (closes #9).*
- [x] 6.3 Archive the OpenSpec change in a **separate follow-up PR** (via `cleanup-merged`),
      following the #4 → #5 precedent; the archive move lives under `openspec/**`, outside the CI
      paths filter, so it never triggers CI. *In progress: this archive branch/PR.*
