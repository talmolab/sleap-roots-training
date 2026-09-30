# Change: Tested registry snapshot, retire and restore commands, and a pinned seed project

## Why

The 13 flat collections retired on 2026-09-29 (#68) can be restored only by a one-shot script.
`/review-pr` found that script's rollback untested and unsafe: any forward re-run destroys its
anchor, and a network error reads as success. This change replaces the script with tested
snapshot, retire and restore commands. It also pins the seed run's W&B entity and project, which
today are named after the working directory.

## What Changes

- **ADDED:** a `sleap-roots-training registry` command group, specified in the delta spec.
  - **`snapshot --out FILE`** (read-only). Records every production-aliased link's source, digest,
    version and full metadata.
  - **`retire --snapshot-out FILE`.** Unlinks the orphans a full `--verify` reports, after writing
    the anchor.
  - **`restore SNAPSHOT`.** Re-links recorded sources, and is idempotent.
  - **Shared rules:** `retire` and `restore` are dry runs by default and require `--execute`. All
    three check for a credential first and fail closed. The spec gives each command's exact
    write limits.
- **ADDED:** a shared absence rule. Only wandb's alias-membership not-found answer means an alias is
  absent, and every other error propagates. wandb stays lazily imported.
- **MODIFIED `Seed Run Lineage`:** the seed run is created with an explicit `entity=` and a pinned
  `project=`: `SLEAP_ROOTS_SEED_PROJECT`, default `sleap-roots-training`.
  - **Behavior change, not API-breaking:** a re-seed that publishes a changed card places its new
    source in `sleap-roots-training`. Unchanged cards are skipped by Idempotent Re-Seed as before.
    Existing sources are not moved.
- **Supersedes** `docs/migration/2026-09-29-retire-flat-collections.py` as the documented rollback.
  The 13 retired links are committed once as a snapshot, which serves as the anchor.

### Why the seed-project guard grew during review

As approved, the guard checked only the run's project after `wandb.init`. `/review-pr` on #70
found four gaps, and #70 fixed them test-first before merging (2026-09-30):

- **Entity was unchecked.** A sweep or launch context drops `entity=` as well as `project=`, so the
  guard now compares both.
- **A stray run was left behind.** A sweep or launch context is detectable before `wandb.init`,
  from `WANDB_SWEEP_ID` / `WANDB_LAUNCH`. Refusing up front creates no stray run, and the
  post-start check remains as a backstop.
- **The stray run looked like a real seed.** It was closed as successful, and an error while
  closing it could mask the refusal. It is now closed with `exit_code=1`, and a closing error
  cannot hide the refusal.
- **The message was misleading under `WANDB_MODE=disabled`**, where the run reports project
  `"dummy"`.

The value is also stripped, so a blank value means the default. The `Seed Run Lineage` delta
reflects all of this.

## Impact

- **Affected specs:** `model-registry`, with 5 ADDED requirements and 1 MODIFIED
  (`Seed Run Lineage`).
- **Depends on `update-model-card-selectors` being archived first.**
  - The new requirements use its Orphaned Collection Reporting and Registry Verification Command,
    including the orphan and legacy-shape definitions and unreadable-collection reporting.
  - This delta is **not** valid against today's main spec. Gate 0.1 enforces the order.
  - It modifies none of that change's requirements.
- **Affected code:**
  - New: `src/sleap_roots_training/registry/retire.py`.
  - `src/sleap_roots_training/cli.py`: the `registry` group, an expected-collection helper, and
    `entity=`/`project=` on the seed run.
  - `src/sleap_roots_training/registry/config.py`: `seed_project`.
  - `src/sleap_roots_training/registry/publish.py`: shared listing helpers, reused and not
    changed in behavior.
  - New: `scripts/convert_retire_record.py`, the one-time conversion.
  - `.github/workflows/ci.yml`: add `scripts/**` to its path filters, and extend black and ruff
    to `scripts/`.
- **Affected tests:**
  - New: `tests/_wandb_fakes.py`, `tests/test_registry_retire.py`.
  - `tests/test_registry_cli.py`, `tests/test_registry_config.py`, `tests/conftest.py` and
    `tests/test_scripts.py`.
- **Affected docs:**
  - `README.md`: the env-var table, usage, and a "Rolling back a retirement" subsection.
  - `docs/CHANGELOG.md`: under `[Unreleased]`.
  - New: `docs/migration/2026-09-29-retired-flat-collections-snapshot.json`.
  - The superseded script: a docstring note only.
- **Live registry:** no W&B writes anywhere in this change. The only live steps are read-only.
- **Posts:** after merge, with confirmation, comments on #68 and predict#34 pointing the rollback
  at `registry restore`.
