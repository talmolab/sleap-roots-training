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
- Version families keyed on **(containing directory, basename minus only the `.vNNN` token,
  full suffix chain)**, because `labels.vNNN.slp` alone occurs 57 times across 23
  directories.
- Per-file facts read from the labels files themselves: skeleton and node names, node
  count, frames, user-labeled versus predicted instances, and referenced video filenames.
- Digest verification against the **per-file `ArtifactManifestEntry.digest`** where a
  registry artifact holds a matching entry, with unregistered files reported as
  unregistered — they outnumber registered ones.
- A `skeletons.yaml` keying-gap report. This is the headline finding and it needs no
  external service.
- Path emission by **whitelist**: candidate paths relative to the supplied root with the
  root as one fixed token, and referenced video paths as filenames alone.
- One table and one report under `inventory/`, in a deterministic order.

Deliberately **not** in this change, so it does not get rebuilt:

| cut | why |
|---|---|
| Bloom reconciliation entirely | Coverage was never measured — that the join key is selectable is not evidence rows come back. It costs `bloomctl` plus ~25 packages and production credentials carrying **write** authority, and the headline finding does not need it. `openspec/project.md:58` already says W&B is the system of record for labeled data and Bloom is the image source, so this is that constraint applied, not an exception to it. Its own change, after someone runs one query. |
| Species from Bloom | Follows from the above. Name-derived species is reported and labelled name-derived, and the report says plainly it is not evidence. |
| Plant counts | Only exist in scan metadata. Scan counts are file-derived and are reported instead. |
| A promotion / decision / verdict file | The governing principle below. |
| Closed vocabularies with a documented-equals-emitted lock | Generated four blocking findings on its own last time. Statuses are prose; the repo's existing subset-check precedent applies. |
| Byte identity across operating systems | A stable sort is enough. The cross-OS guarantee wanted a golden fixture and `.gitattributes` surgery, and protected nothing anyone asked for. |
| A marker-and-first-segment redaction blacklist | Replaced, not dropped — see *Review outcome*. A blacklist over arbitrary recorded strings cannot be shown complete; the root-relative whitelist is both bounded and smaller. |

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
  `src/sleap_roots_training/cli.py` placed **after `seed-registry` and before `validate`**;
  tests under `tests/`; a new `inventory/` output directory; `docs/CHANGELOG.md` and a
  `README.md` pointer; and a status-banner edit to this change's scope doc.
- **No new dependencies.** `sleap-io` resolves at 0.7.1 under a `<0.8.0` cap and `wandb` at
  0.28.0 under `<0.29.0`; every library fact the delta relies on was verified by running it
  against those resolved versions.
- **No `ci.yml` change needed.** Its paths filter covers `src/sleap_roots_training/**` and
  `tests/**` and omits `README.md`, `scripts/**` and `inventory/**`. No `.gitignore` or
  packaging change either: `inventory/` is not ignored, so the artifacts commit, and
  `uv_build` packages only `src/`.

## Scope discipline

The budget is **≤ 8 requirements, ≤ 35 scenarios, ≤ 200 spec lines, ≤ 35 tasks, one review
round**. After that round the delta is at **8 requirements, 26 scenarios, 200 lines and 34
tasks** — requirements and lines are **spent**. A finding that would need a ninth
requirement has to be answered by cutting an existing one, not by adding. That is the
intent, not an accident.

There is deliberately **no `design.md`**. The last attempt's second failure was mechanical:
four interdependent documents edited in batches with nothing checking the seams, which
produced stale counts and struck claims surviving in one file after being fixed in another.
A fourth document would reproduce it.

## Review outcome

One review round ran, across five lenses. It found two false claims and a leak, all now
fixed. Recording them because the fixes changed the design, not just the wording:

- **The redaction requirement leaked on its own attested paths.** The marker set was written
  as slash-terminated strings (`users/`, `Users/`, `home/`), and Windows SLEAP records video
  paths in the *backslash* form — so both known colleague paths passed through untouched, and
  the scenario covering them would pass or leak depending on which separator a fixture used.
  Relative and `..`-rooted paths leaked too, `pathlib` folds `\\server\share` into the anchor
  so a person-named share survived, `PurePath` means something different on the POSIX CI
  runners, and `home/` matched inside words like `genome`. The whole shape was wrong: a
  blacklist over arbitrary recorded strings cannot be shown complete. It is now a whitelist —
  emit nothing above the supplied root and nothing but a basename below — which removes the
  class instead of enumerating it, and is fewer lines than what it replaced.
- **A scenario would have required a colleague's name in a public test suite.** "The two
  known real paths are covered" was normative and depended on two unmeasurable paths, so
  implementing it meant either committing a name or using a stand-in that duplicated the
  scenarios above it. Cut.
- **A carried-forward "verified fact" was misleading.** `sleap_io` 0.7.1 has no
  `Labels.user_instances`, which is true, but it does have `Labels.n_user_instances` and
  `Labels.n_pred_instances` — and upstream's own implementation is the `LabeledFrame` sum as
  a *fallback*, with a faster path when the file is lazily loaded. The spec had reasoned from
  a true narrow fact to a false general one, and the task encoded the false one.
- **Digest verification had no join key**, so it was undecidable whether its own mismatch
  scenario was reachable. It now states the key, and that multiple matches are all reported
  with none crowned.
- **A `file://` reference logged with `checksum=False` carries an MD5 of the path**, which is
  shape-identical to a content hash and would have produced a confident false mismatch. The
  discriminator is the reference scheme, not whether a reference is set.
- **Three scenarios had no test task** — their assertions had been misfiled into
  implementation tasks. **Fixtures are now built first**, since every other section's tests
  consume them, and must live in `tmp_path`: `.gitignore` swallows `*.slp`, so committed
  fixtures would pass locally and fail CI.
- **Deleting the scope doc was incoherent**, because the proposal cites it as where the
  reasoning lives. It now gets a superseded banner instead — the same treatment, for the same
  reason, that the v1 design doc got.

## Decisions carried forward

This change emits **evidence, not `LabelCard`s** — `registry_id` and `version` are
meaningless for unregistered collections, which outnumber registered ones. Card eligibility
is #49's, including flagging a multi-species file for splitting, because name-derived species
is not evidence here. Wheat's `seminal`/`sr` maps to the `crown` row and `RootType` gains no
member. The unit is the labels file, not the folder, and not the scan.

## Follow-ups this unblocks

- **#49** has a live question this output gives the evidence for: whether
  `wheat_5-14DAG_seminal_6nodes_labels` is the wheat half of the pooled wheat+rice file —
  frame and instance counts are that evidence. #49's §2 is the manual version of this command.
- **`docs/roadmap.md` on `main` says nothing about a label inventory.** PR #56 (open) *adds*
  a Tier 2 block describing it as Bloom-joined via `bloomctl`, citing the abandoned change id
  `add-label-corpus-inventory`, and promising a per-scan CSV plus a per-field-confidence YAML
  — all superseded here. Because #56 has not merged, that text is amended in #56 before it
  lands rather than corrected afterwards by this change, which keeps this change free of a
  merge-order dependency. An earlier draft of this section claimed the stale text was already
  on `main`; it was not.
- **#48** touches `cli.py` and rewrites `openspec/project.md:44-51`. The new command group's
  placement is clear of all four of #48's hunks and the module import merges clean in either
  position (tested both merge directions). If #48's rewritten `main()` docstring enumerates
  subcommands, adding `inventory` there is a separate one-line edit.
