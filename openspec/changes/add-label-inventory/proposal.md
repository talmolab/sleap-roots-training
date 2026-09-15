## Why

Nobody knows what labeled data exists. `wandb-registry-sleap-roots-labels` holds 8
collections against an expected 25–30, and `skeletons.yaml` cannot express the corpus it
claims to describe: `lookup_skeleton` is keyed `(species, root_type, age)` with no `mode`,
so a 6-node cylinder arabidopsis primary family and an 8-node plate one both select the
same row. Everything downstream — #11/#49's card backfill, Tier 2.2's dataset
identification — is waiting on an enumeration that has never been run.

This change adds the enumeration, and stops there. A person reads the output and decides
what matters.

## What Changes

- A re-runnable `sleap-roots-training inventory labels <root>` command group that walks a
  supplied root, enumerates candidate labels files, and excludes derived files by filename
  shape as well as by directory.
- Version families keyed on **(containing directory, basename minus version, extension)**,
  because `labels.vNNN.slp` alone occurs 57 times across 23 directories.
- Per-file facts read from the labels files themselves: skeleton and node names, node
  count, frames, and user-labeled versus predicted instances.
- Digest verification against the **per-file `ArtifactManifestEntry.digest`** where a
  registry artifact exists, with unregistered files reported as unregistered — they
  outnumber registered ones.
- A `skeletons.yaml` keying-gap report. This is the headline finding and it needs no
  external service.
- Redaction of person-identifying path segments, by a case-insensitive marker set **and** a
  first-segment rule for drive-rooted and UNC paths.
- One table and one report under `inventory/`, in a deterministic order.

Deliberately **not** in this change, so it does not get rebuilt:

| cut | why |
|---|---|
| Bloom reconciliation entirely | Coverage was never measured — that the join key is selectable is not evidence rows come back. It costs `bloomctl` plus ~25 packages and production credentials carrying **write** authority, and the headline finding does not need it. Its own change, after someone runs one query. |
| Species from Bloom | Follows from the above. Name-derived species is reported and labelled name-derived, and the report says plainly it is not evidence. |
| Plant counts | Only exist in scan metadata. Scan counts are file-derived and are reported instead. |
| A promotion / decision / verdict file | The governing principle below. |
| Closed vocabularies with a documented-equals-emitted lock | Generated four blocking findings on its own last time. Statuses are prose; the repo's existing subset-check precedent applies. |
| Byte identity across operating systems | A stable sort is enough. The cross-OS guarantee wanted a golden fixture and `.gitattributes` surgery, and protected nothing anyone asked for. |

## The governing principle

> **When the tool cannot decide something, print it and stop. Do not build a mechanism to
> capture the answer.**

eberrigan, 2026-09-15: *"i don't mind being a human in the loop for this to avoid
unnecessary complications."*

The previous attempt grew from 15 to 19 requirements and 68 to 145 scenarios over seven
review rounds, almost entirely by building infrastructure to avoid asking a person: a
committed decision file, an identifier scheme, merge semantics, verdict forms,
stale-verdict detection. Each round found real defects and each was answered by specifying
more; round 6 produced 17 findings of which 14 were newly introduced. `Requirement: No
Decision Capture` in the delta exists to keep that from regrowing.

## Impact

- **Affected specs:** `label-inventory` (new capability, ADDED only — no live spec covers
  label provenance).
- **Affected code:** a new `src/sleap_roots_training/inventory/` module; a command group in
  `src/sleap_roots_training/cli.py` placed **after `seed-registry` and before `validate`**,
  which is clear of all four of #48's `cli.py` hunks; a new `inventory/` output directory;
  tests under `tests/`.
- **No new dependencies.** `sleap-io` 0.7.1 and `wandb` 0.28.0 are already pinned, and both
  facts this change relies on were verified against those exact versions.
- **No `ci.yml` change needed.** Its paths filter omits `README.md`, `scripts/**` and
  `inventory/**`; this change touches `src/**` and `tests/**`, which are covered, and the
  tests use fixtures rather than the committed `inventory/` artifacts.

## Scope discipline

The budget from the scope doc is **≤ 8 requirements, ≤ 35 scenarios, ≤ 200 spec lines, ≤ 35
tasks, one review round**. The delta is at 8 requirements, 29 scenarios and 197 lines — the
requirement and line budgets are effectively **spent**. A review finding that would need a
ninth requirement has to be answered by cutting an existing one, not by adding. That is the
intent, not an accident.

There is deliberately **no `design.md`**. The reasoning lives in
`docs/superpowers/specs/2026-09-15-label-inventory-v2-scope.md`, committed alongside this
change. The last attempt's second failure was mechanical: four interdependent documents
edited in batches with nothing checking the seams, which produced stale counts and struck
claims surviving in one file after being fixed in another. A fourth document would
reproduce it.

## Assumptions

- **Exit status.** A successful scan exits zero regardless of what it finds — digest
  mismatches and unregistered files are findings for a person to read, not tool failures.
  Only an unusable root is a non-zero exit. Flagged because it would matter if this is ever
  wanted as a CI gate; nothing in scope asks for that.
- **Discovery root.** Scoped to the project owner's SLEAP directory, supplied as an
  argument rather than hardcoded.

## Follow-ups this unblocks

- **#49** has a live question this output answers: whether
  `wheat_5-14DAG_seminal_6nodes_labels` is the wheat half of the pooled wheat+rice file.
  #49's §2 is the manual version of this command.
- **`docs/roadmap.md`** Tier 2 still describes the inventory as Bloom-joined and cites the
  abandoned change id `add-label-corpus-inventory`; both are corrected in this change's
  tasks. (#56 knowingly left them stale, as they were not decidable there.)
