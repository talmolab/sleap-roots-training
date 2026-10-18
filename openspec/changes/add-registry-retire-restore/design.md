# Design: registry snapshot, retire and restore

The delta spec is normative. This file records **why**.

## Context

The 2026-09-29 retirement (`update-model-card-selectors` 6.3) used a lab script. `/review-pr` on
#68 found four defects in its rollback path:

- **Anchor overwrite.** Any forward re-run, including the default dry run, overwrites the record
  holding the rollback entries, and `--rollback` then raises `KeyError`.
- **Mistyped name.** A mistyped name raises `KeyError` partway through a rollback.
- **Unchecked alias.** Rollback never checks what `:production` already points at, so it can move
  the alias.
- **Catch-all error handling.** Its `resolves()` counts a network or auth error as "not found",
  which after an unlink reads as success.

The script stays as it ran, as evidence. The same review found that the seed run passes no
`project=` (`cli.py`), so W&B names the project after the working directory.

- **The canary's source is on record.** The canary's production source is recorded under
  `migrate-model-card-selectors` in `2026-09-24-probe-6-5-metadata-refresh-record.json`.
- **The other 7 are expected, not recorded.** They were seeded by the same worktree run and are
  expected there too. Task 10.2's live snapshot records them.
- **The flat sources are recorded elsewhere.** The 13 flat sources are under
  `sleap-roots-training-talmolab`, per the 6.3 record.

Facts verified against wandb 0.28.0 and the live registry:

- **`unlink()` refuses a non-link.** `Artifact.unlink()` raises `ValueError` unless the object is a
  link.
- **`link()` re-creates a link.** `Artifact.link(target_path, aliases)` re-creates one. The 6.0(e)
  rehearsal re-linked the canary and got the identical `v0` link back.
- **`save()` on a source misses the registry.** `Artifact.save()` on a **source** artifact sends
  its alias change to the source's own collection (`deleteAliases` in 6.0(b)). It reports success
  and leaves the registry untouched. This is why nothing here calls `save()`.
- **A missing alias raises `CommError` with a fixed message.** For example, "artifact membership
  '<c>:production' not found in '<project>'" (2026-09-29). The message is the same whether the
  collection exists without the alias or does not exist at all.
- **Unlinking leaves the collection.** Unlinking a collection's only member leaves it in place,
  empty.
- **An explicit `project=` wins over `WANDB_PROJECT`** (`wandb_init.py`). Inside a sweep or launch
  context, however, wandb drops it with only a printed warning. Hence the post-init project check.
- **Importing `wandb.errors` costs about 5s.** It runs wandb's package `__init__`, measured at
  about 4.9s. `import sleap_roots_training.cli` does not load wandb today, so that has to stay true.

## Decisions

- **A `registry` group, not more `seed-registry` flags.** `seed-registry` already has four
  interacting modes, and the pending change modifies its CLI requirement. The `inventory` group is
  the precedent.
- **Retire targets what a full `--verify` calls orphaned.** It reuses the verify command's orphan
  logic, so the rule is "what the matrix no longer produces". There is no hard-coded list.
- **Unreadable means stop.** Elizabeth decided this on 2026-09-29. `--verify` only reports, so
  there an unreadable collection is advisory. For retire it could be a missed orphan, and for a
  snapshot a missing rollback entry, so both fail closed.
- **Per-target reads use `api.artifact("<project>/<c>:<alias>")`.** That is the read path whose
  not-found error was verified live. The existing `_aliased_artifact` iterates `api.artifacts(...)`
  and returns `None` on absence, so it cannot tell "absent" from a truncated or failed listing.
  Snapshot, retire and restore therefore never use it for a read they act on. Enumeration reuses
  the verify listing. Retire's precondition deliberately reuses the full verify logic, including
  `_aliased_artifact` for the expected collections. There, a false "absent" reads as missing,
  which makes retire refuse. That is the safe direction.
- **The anchor is created exclusively, before the first write, and never rewritten.** Restore only
  reads snapshots. That is what makes a re-run unable to destroy the rollback.
- **Restore is idempotent, never moves an alias, and checks the version.** Bloom's idempotency key
  hashes `(registry_id, version, weights_checksum)`, so a re-link landing at a new version must fail
  loudly. It must not be accepted just because its digest matches, whether just after linking or as
  an "already restored" skip on a re-run. The skip requires digest, version and source to match.
  Restore never unlinks, so a wrong-version link it leaves behind stays refused until an operator
  resolves it.
- **wandb stays lazy.** The `CommError` import happens inside the registry functions. A subprocess
  test pins that importing the CLI module does not load wandb.
- **Pinned entity and project.** They come from the same config that resolves the registry target.
  `sleap-roots-training` is the default. The two existing source projects hold live sources, and
  are documented as do-not-delete.
- **The 2026-09-29 record is converted into an anchor by a tested script, not by hand.** The
  conversion goes in
  `scripts/convert_retire_record.py`, following the `scripts/` and `tests/test_scripts.py`
  precedent. Its pure record-to-snapshot mapping is unit-tested in CI. Its only network access is
  read-only: the retired sources' metadata. In the converted file, `captured_utc` is the conversion
  time, when the metadata was read. The retirement time stays in the retire record it came from.

## Risks / Trade-offs

- **Concurrent writers can still race.** This is group 6's single-operator rule. The per-target
  digest re-check narrows the window.
- **A re-link might not return `v0`.** The one observation, the canary, did. The version assertion
  turns a surprise into a loud failure.
- **Tests are offline only.** The live contract rests on the facts above plus task 10.2's read-only
  checks. A live write test would itself be a registry write.

## Migration Plan

Gate 0.1, then groups 1–10. No step writes to W&B.
