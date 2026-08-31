# Proposal: Add a combined `run` command (validate → emit → `sleap-nn train`)

## Why

On a host that has both this package and the `[train]` extra — the GPU box — training one config is
three manual commands plus an intermediate file the operator manages by hand, and that file is a
*detached copy*: edit the source config, forget to re-emit, and you train the previous config while
believing you trained the edited one. Issue #34 asks for one command that chains the three steps for
that co-installed case.

This reverses `add-config-schema`'s non-goal of "training/predict **orchestration** beyond
`validate`", which was set before there was a host with both installed. That non-goal stays in force
for everything except this one composition.

## What Changes

- Add `sleap-roots-training run <config.yaml>`, which in order: **gates** on the `sleap-nn` console
  script being resolvable, **validates** the config with the existing `validate` checks, **writes**
  its provenance artifacts, and **shells out** to `sleap-nn train --config <path>`.
- **Gate, don't degrade.** The console script is located in the running interpreter's
  console-script directory (`sysconfig.get_path("scripts")`) first, then beside the interpreter,
  then on `PATH`; if none yields it, `run` fails with the install command before writing anything.
  The resolved absolute path is echoed before the run starts — the only diagnostic for a
  wrong-environment pick. Note the gate does **not** guarantee `sleap_nn` is *importable* here, so
  deep validation can still be skipped; `run` reports that note rather than pretending otherwise.
- **Write the two artifacts the backend cannot.** Verified against `sleap-nn` 0.2.0
  (`training/model_trainer.py:1269,1313`), the backend already writes `initial_config.yaml` and
  `training_config.yaml` into `<ckpt_dir>/<run_name>/` — but only after trainer construction, and
  never carrying the repo-owned `experiment` block, which is stripped by construction. So `run`
  writes `source_config.yaml` (the input config, `experiment` block intact — the identity no
  sleap-nn artifact records) and `emitted_config.yaml` (the emitted config, on disk *before* the
  backend starts, so a run that dies during setup still has a record). Both LF-normalized and
  written atomically.
- **Refuse to reuse a run directory.** The backend auto-suffixes to `<run_name>-1` when
  `<ckpt_dir>/<run_name>/best.ckpt` exists (`model_trainer.py:522`), which would strand our
  artifacts beside a *different* run's checkpoint. `run` therefore fails when the run directory
  already holds a `best.ckpt` or a `training_config.yaml`, telling the operator to change
  `trainer_config.run_name`. **There is no `--force`:** overwriting a completed run's provenance is
  never the desired outcome, and a name collision's correct remedy is a new name.
- **Require a usable `run_name`.** With none, the backend generates `<timestamp>.<model_type>.n=<N>`
  (`model_trainer.py:513`) — a directory `run` cannot predict, so it refuses rather than dropping
  artifacts one level above the real run. `ckpt_dir` defaults to `"."`, matching the backend.
- **Refuse an in-config W&B credential.** `registry/publish.py:42` uploads the *whole* model
  directory (`artifact.add_dir`), and the backend deliberately masks `trainer_config.wandb.api_key`
  in the configs it writes there (`model_trainer.py:997`). Persisting an unmasked copy would publish
  the key, so `run` refuses one and names `WANDB_API_KEY` / `wandb login` instead. When W&B is
  enabled, `run` also reuses the existing credential check *before* starting a multi-hour run.
- **Surface the backend's own result.** Streams are inherited (live progress, nothing buffered);
  the exit status is propagated verbatim; signal termination becomes `128 + N` where the platform
  expresses it that way; an operator interrupt is handed to the backend rather than killing it, so
  Lightning can shut down gracefully. No success line for a failed run, and a failed run keeps its
  artifacts as the record of what was attempted.
- **`emit` writes LF too** (one line in `cli.py`). Today it inherits `newline=None` and produces
  CRLF on Windows — the documented GPU box — which would make `run`'s artifact and `emit -o`'s
  output differ byte-wise on the one host that matters, and would defeat the config hashing #10/#11
  will want. **This is the one behavior change to an existing command in this proposal.**
- Docs: a one-command section in `docs/training.md` (with the run-directory file inventory and the
  `uv run --no-sync` caveat), the guide's contract test extended so the shortcut cannot silently
  replace the canonical path, a `docs/CHANGELOG.md` entry, the `README.md` pointer paragraph, and
  `openspec/project.md`'s architecture line updated for the new backend-consumption mode.

**Additive, not a replacement.** `validate` and `emit` keep their behavior and stay base-install
safe, because the real workflow authors and validates on a Mac and trains on an isolated Windows GPU
box. `run` is a shortcut for when all three would run on one host.

## Non-Goals

- Replacing `validate` or `emit`, or making either require the `train` extra.
- Proxying `sleap-nn train`'s flags or Hydra-style overrides. `run` passes one config and nothing
  else; anything more is the three-command path.
- Closing the provenance gap `docs/training.md` already documents. `run` records **no** config hash,
  git commit, or dataset checksum — those stay deferred to Tier 2 (#10/#11). It makes a run
  directory self-describing as to *which experiment* it was, not *which bytes* it consumed.
- A `--dry-run` mode, and any `--force`-style override of the run-directory refusal.

## Open Questions For Review

The "one artifact or two" question is **closed** — see `design.md` D3. The emitted config must be on
disk for `sleap-nn train --config` to be invoked at all, and #34 explicitly rules out a throwaway
temp file, so it stays in the run directory beside `source_config.yaml`. That was spec-shaping, so it
is decided here rather than deferred.

Three questions remain, none of which change spec text whichever way they go — full context in
`design.md`:

1. **Is refusing a reused run directory too strict**, given the backend would happily suffix?
2. **Is `run` the right verb** next to `sleap-nn train`? (Recommendation: yes — `train` would create
   two near-identical invocations taking *different* inputs.)
3. **Is refusing an in-config `wandb.api_key` acceptable**, or should `run` mask it instead?

## Impact

- **Affected specs:**
  - `training-run` (ADDED — new capability: the command, its provenance artifacts, the invocation
    and exit-status contract, credential safety, and the documentation requirement). Filed as its
    own capability rather than split across `training-backend` (which owns packaging and the
    runbook) and `training-config` (which owns the config schema and `validate`/`emit`).
  - `training-config` (MODIFIED — `Config Validation CLI` gains the guarantee that train-gated
    commands do not compromise base-install safety; `Reproducible, Backend-Safe sleap-nn Config`
    gains the LF-newline requirement on emitted files).
- **Affected code:** `src/sleap_roots_training/backend.py` (new — resolve the executable, stage the
  artifacts, build the argv, run the backend, translate its status); `src/sleap_roots_training/cli.py`
  (new `run` subcommand; one-line `newline="\n"` fix to `emit`; group docstring);
  `tests/test_backend_invoke.py` and `tests/test_cli_run.py` (new); `docs/training.md`,
  `tests/test_training_docs.py`, `docs/CHANGELOG.md`, `README.md`, `openspec/project.md`.
  `src/sleap_roots_training/config.py` is unchanged, and so is `tests/conftest.py` — its existing
  `write_config(overrides=...)` factory already covers pointing `ckpt_dir` at `tmp_path`.
- **Not affected:** `pyproject.toml` (no new dependency — `subprocess`, `shutil`, `sysconfig` are
  stdlib; the `train` extra is unchanged; and `uv_build` needs no configuration for a new module —
  verified against the built wheel, which already ships a *non*-Python file,
  `registry/data/model_selection.yaml`, with no `[tool.uv.build-backend]` section present),
  `.github/workflows/ci.yml` (`src/sleap_roots_training/**`, `tests/**`, `docs/**` are already in
  the paths filter — note `README.md` is *not*, so it must land in the same commit as the `docs/`
  changes to get CI), `docs/training-backend.md` (documents the raw Tier-0.5 sample config, which
  has no `experiment` block and so is not a `run` input), `docs/roadmap.md` (no tier or open
  decision becomes false), and the six `examples/*.yaml` headers. That last one is a **judgment
  call, not an oversight**: those headers document the *cross-machine* path, which is exactly the
  case `run` does not serve, so adding it would put six copies of a co-installed-only shortcut on
  the configs most likely to be copied to another host. Adding one line to
  `examples/arabidopsis_primary_cylinder.yaml` alone — the file the guide tells users to copy — is
  the reasonable middle ground if reviewers want `run` discoverable from an example.
- **Breaking changes:** none to any documented contract. The one behavior change is `emit -o`'s line
  endings on Windows (CRLF → LF), called out above and in the CHANGELOG entry.
- **Concurrent work:** `update-model-card-selectors` (#39) is in flight on branch
  `openspec/shared-model-registration` — `model-registry` capability, `registry/` code. No overlap.
