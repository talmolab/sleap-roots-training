## MODIFIED Requirements

### Requirement: Seed Run Lineage

The seed SHALL record run-level lineage in the wandb run config for traceability: the
`sleap-roots-training` git SHA, a dirty-working-tree flag, the **SHA256 content hash of the actually
loaded `model_selection.yaml`** (so the exact matrix used is pinned independently of git cleanliness —
the per-model SHA256 anchor now lives in that tracked file), the selection-matrix source (URL) and
verification date, the `models-downloader` snapshot date, and the `sleap-roots-training` / `wandb` /
`sleap-roots-contracts` versions. Git-SHA resolution SHALL be robust — it SHALL prefer an explicit
env override, otherwise resolve from a `.git` anchored at the installed package (never the current
working directory), otherwise fall back to the package version, and SHALL never raise or abort the
seed; tool/contract versions come from `importlib.metadata`. A dirty working tree under `--execute`
SHALL emit a warning (the recorded matrix content hash makes the exact inputs recoverable regardless).
Lineage SHALL NOT be written into per-artifact metadata (which stays exactly the selection keys).

The seed run SHALL be created with an explicit wandb entity (the configured registry entity) and
an explicit, **pinned project**. The project is resolved from `SLEAP_ROOTS_SEED_PROJECT`, stripped
of surrounding whitespace; when that is unset, empty or blank, the default is
`sleap-roots-training`. The project SHALL never be derived from the working directory or the git
checkout, because the seed run's project is where every published source artifact lives.
Existing source artifacts in other projects are not moved.

Inside a sweep or launch context, wandb drops both `entity=` and `project=`. So:

- **Before creating any run**, the seed SHALL refuse, exiting non-zero and naming the variable,
  when `WANDB_SWEEP_ID` or `WANDB_LAUNCH` is set (any value except empty, `0` or `false`).
- **After the run starts**, as a backstop, if the run reports an entity or project other than the
  resolved ones, the seed SHALL NOT publish anything. It SHALL close that run as failed
  (`exit_code=1`) and exit non-zero with a message naming both targets. An error while closing
  the run SHALL NOT mask that refusal. When wandb is disabled, the message SHALL say so rather
  than blaming a sweep.

`SLEAP_ROOTS_SEED_PROJECT` is specified here rather than under Environment-Driven Registry
Configuration on purpose. That requirement describes the registry target, which must match what
the consumer reads. The seed project is producer-only provenance that the consumer never reads.

#### Scenario: Run records producer lineage

- **WHEN** a real seed runs
- **THEN** the run config records the git SHA (or a documented fallback sentinel), the dirty flag,
  the loaded `model_selection.yaml` content hash, the selection-matrix source + date, the
  models-downloader snapshot date, and the tool/contract versions
- **AND** no per-artifact metadata carries lineage keys

#### Scenario: Git SHA resolves without a repository

- **WHEN** the git SHA is resolved from an installed package with no `.git` and no env override
- **THEN** it returns the package-version fallback (or `"unknown"`) without raising

#### Scenario: Seed run uses the default project

- **WHEN** `seed-registry --execute` starts its wandb run with `SLEAP_ROOTS_SEED_PROJECT` unset,
  empty or blank
- **THEN** the run is started with `project="sleap-roots-training"` and the configured entity

#### Scenario: Seed project is overridable

- **WHEN** `SLEAP_ROOTS_SEED_PROJECT=other` and `WANDB_ENTITY=some-entity` are set
- **THEN** the run is started with `project="other"` and `entity="some-entity"`

#### Scenario: Seed project does not depend on the working directory

- **WHEN** `seed-registry --execute` is started from two different working directories
- **THEN** both runs are started with the same project

#### Scenario: A sweep or launch context is refused before any run

- **WHEN** `WANDB_SWEEP_ID` or `WANDB_LAUNCH` is set
- **THEN** the seed exits non-zero naming the variable, without calling `wandb.init` or publishing

#### Scenario: A dropped target aborts the seed

- **WHEN** the started run reports an entity or project other than the resolved ones
- **THEN** the seed exits non-zero before publishing any card, saying nothing was published
- **AND** the run is closed with `exit_code=1`

#### Scenario: A disabled run aborts with a disabled hint

- **WHEN** wandb is disabled, so the run reports project `"dummy"`
- **THEN** the seed exits non-zero with a message naming disabled mode, not a sweep

#### Scenario: A failing teardown does not mask the refusal

- **WHEN** closing the mismatched run raises
- **THEN** the seed still exits non-zero with the refusal message

## ADDED Requirements

### Requirement: Registry Alias Absence Rule

When the `registry` commands read whether a collection carries the configured alias, they SHALL
treat only a wandb not-found answer **for that alias membership** as "absent". Pinned to wandb
0.28.0, that answer is a `CommError` whose message contains both `artifact membership` and
`not found`, as in "artifact membership '<collection>:<alias>' not found in '<registry project>'".
**Any other error SHALL propagate**, including a `CommError` with a different message such as a
project or entity not found, so that a misconfiguration or a network, auth or rate-limit failure can
never read as absence.

#### Scenario: Not-found reads as absent

- **WHEN** the read raises a `CommError` saying the alias membership is not found
- **THEN** the collection is treated as not carrying the alias

#### Scenario: Other errors propagate

- **WHEN** the read raises a `CommError` with any other message (including a project or entity not
  found), or any other exception
- **THEN** that exception propagates to the command, which exits non-zero

### Requirement: Registry Commands Load wandb Lazily

Importing the package's CLI module, or the module implementing the `registry` commands, SHALL NOT
import wandb. wandb is loaded only when a registry command contacts it, so that every other CLI
command keeps its current start-up cost.

#### Scenario: Importing the CLI does not load wandb

- **WHEN** a fresh interpreter imports the package's CLI module, or the registry-commands module
- **THEN** `wandb` is not in `sys.modules`

### Requirement: Registry Snapshot Command

The CLI SHALL provide `sleap-roots-training registry snapshot --out FILE`, a **read-only** command. A
snapshot is a JSON file describing every collection in the consumer's registry project that
carries the configured alias. A snapshot restricted to some collections is still a snapshot. An
**anchor** is a snapshot that a later `registry restore` will use as input.

- It SHALL check for a resolvable wandb credential before contacting wandb.
- It SHALL refuse, before contacting wandb, to write to an existing `FILE`, and SHALL create the
  file exclusively.
- It SHALL enumerate collections with the same collection listing and alias check that the orphan
  report uses.
- It SHALL read each collection under the Registry Alias Absence Rule.
- If any collection's aliases or alias-carrying artifact cannot be read, it SHALL **fail closed**:
  write no file, name the unreadable collections, and exit non-zero.

The file's top level SHALL record `captured_utc` (ISO-8601 UTC), `registry`, `alias`,
`tool_version` (the `sleap-roots-training` version) and `collections`. Each collection entry SHALL
record:

- `collection`, `version`, `aliases`, `digest`, `is_link`, `source_qualified_name` and `metadata`
  (the full metadata);
- `shape`: `selectors` when the verify command's structural shape check passes, and `legacy`
  otherwise. This is exactly the verify command's two-way determination.
- `version` is the wandb version string, for example `"v0"`.

The file SHALL be UTF-8 with LF line endings on every platform, with sorted keys and collections
sorted by name. Two snapshots of an unchanged registry written by the same tool version SHALL
therefore differ only in `captured_utc`.

#### Scenario: Snapshot records sources and metadata

- **WHEN** `registry snapshot --out snap.json` runs against a registry holding two alias-carrying
  links
- **THEN** `snap.json` records the top-level fields and, for both collections sorted by name, every
  entry field
- **AND** no wandb write method is called

#### Scenario: Snapshot classifies shape

- **WHEN** the snapshotted links carry selector-shaped metadata, legacy flat metadata, and metadata
  carrying `selectors` together with a card-level key
- **THEN** their `shape` values are `selectors`, `legacy` and `legacy` respectively

#### Scenario: Snapshot output is deterministic

- **WHEN** two snapshots of the same registry are written, including on Windows, with the capture
  time fixed
- **THEN** the files are byte-identical, UTF-8, LF-only, with sorted keys, whatever order the
  listing returned the collections in

#### Scenario: Snapshot fails closed on an unreadable collection

- **WHEN** one collection's aliases, or its alias-carrying artifact, cannot be read
- **THEN** it exits non-zero naming that collection and writes no file

#### Scenario: Snapshot refuses to overwrite

- **WHEN** `registry snapshot --out snap.json` runs and `snap.json` already exists
- **THEN** it exits non-zero without contacting wandb and the file's bytes are unchanged

#### Scenario: Snapshot requires a credential

- **WHEN** no wandb credential is resolvable
- **THEN** it exits non-zero without constructing a wandb API client

### Requirement: Production Link Retirement Command

The CLI SHALL provide `sleap-roots-training registry retire --snapshot-out FILE`. It removes the
configured alias from **orphaned** collections by unlinking their registry link.

- **Mode.** It is a dry run by default. It requires `--execute` to write, and prompts for
  confirmation unless `--yes` is given. It SHALL check for a resolvable wandb credential before
  contacting wandb.
- **Targets.** The targets are the orphans, as defined by Orphaned Collection Reporting, that a
  **full** `seed-registry --verify` reports. `--only` SHALL narrow
  the targets to named orphans, and SHALL reject any name that is not one. It never narrows the
  set of expected collections, unlike `seed-registry --only`.
- **Refusals.** It SHALL refuse, exiting non-zero before writing any file or calling any wandb write
  method, while any of these holds:
  - a full `--verify` would exit non-zero, because an expected collection is missing or
    legacy-shaped;
  - any collection's aliases cannot be read. Unlike `--verify`, which treats such collections as
    advisory, retire treats them as blocking.

  When there are no orphans, it SHALL say so and exit zero without writing anything.
- **The anchor.** Under `--execute` and after confirmation, before its first write, it SHALL write
  the targets' snapshot to `FILE` as the anchor. It SHALL create the file exclusively, and refuse if
  the file exists. A dry run SHALL write nothing and list the targets.
- **Per target, in sorted order.**
  1. Re-read the alias-carrying artifact under the Registry Alias Absence Rule.
  2. Stop if it is absent, is not a link, or its digest differs from the anchor's.
  3. Call `unlink()`.
  4. Re-read it, and stop unless it is now absent.

  It SHALL print each target's outcome as it happens, and stop on the first failure with a non-zero
  exit.
- **Invariants.** It SHALL never call `save()` or `link()` on any artifact, and SHALL never delete
  a collection or artifact.

#### Scenario: Retire unlinks orphans after writing the anchor

- **WHEN** `registry retire --snapshot-out anchor.json --execute --yes` runs while every expected
  collection is present and selector-shaped, and there are two orphans
- **THEN** `anchor.json` holds both orphans and is written before the first `unlink()`
- **AND** each orphan is unlinked in sorted order and then re-read as absent
- **AND** the expected collections are untouched, and no `save()`, `link()` or delete is called

#### Scenario: Retire narrows to named orphans

- **WHEN** `--only` names one of two orphans
- **THEN** the anchor holds only that orphan, only it is unlinked, and the other keeps its alias

#### Scenario: Retire requires a credential

- **WHEN** no wandb credential is resolvable
- **THEN** retire exits non-zero without constructing a wandb API client

#### Scenario: Retire with no orphans

- **WHEN** a full verification reports no orphans
- **THEN** retire reports that and exits zero without writing any file

#### Scenario: Retire refuses while replacements are unhealthy

- **WHEN** an expected collection is missing, or is legacy-shaped
- **THEN** retire exits non-zero before writing any file or calling `unlink()`

#### Scenario: Retire fails closed on an unreadable collection

- **WHEN** any collection's aliases cannot be read
- **THEN** retire exits non-zero, listing it, before writing any file or calling `unlink()`

#### Scenario: Retire rejects a non-orphan target

- **WHEN** `--only` names a collection that is not an orphan
- **THEN** retire exits non-zero naming it and listing the orphans, before any write

#### Scenario: Retire refuses to overwrite an anchor

- **WHEN** `--snapshot-out anchor.json --execute` is given and `anchor.json` exists
- **THEN** retire exits non-zero before any wandb write, and the file's bytes are unchanged

#### Scenario: Retire stops on a changed target

- **WHEN** a target is absent on re-read, is not a link, or its re-read digest differs from the
  anchor's
- **THEN** that target is not unlinked, no later target is processed, and retire exits non-zero
  naming it

#### Scenario: Retire detects an ineffective unlink

- **WHEN** `unlink()` returns but the post-unlink read still resolves the alias
- **THEN** retire exits non-zero naming that target, and no later target is processed

#### Scenario: A transient error after unlink is not success

- **WHEN** the post-unlink read raises an error other than not-found
- **THEN** the error propagates, the target is not reported as retired, and no later target is
  processed

#### Scenario: Retire requires confirmation

- **WHEN** `--execute` is given without `--yes` and the operator declines
- **THEN** retire exits without writing the anchor or calling `unlink()`

#### Scenario: Retire dry run writes nothing

- **WHEN** retire runs without `--execute`
- **THEN** it lists the targets, calls no wandb write method, and creates no file

### Requirement: Production Link Restore Command

The CLI SHALL provide `sleap-roots-training registry restore SNAPSHOT`, which re-links each recorded
source artifact into its registry collection with the configured alias. It is the documented
rollback for a retirement, and it accepts any snapshot, full or restricted.

- **Mode.** It is a dry run by default. It requires `--execute` to write, and prompts for
  confirmation unless `--yes` is given. It SHALL check for a resolvable wandb credential before
  contacting wandb.
- **Validation, before any wandb write.** It SHALL validate that:
  - the snapshot's `registry` and `alias` equal the resolved configuration;
  - every `--only` name is in the snapshot, listing the valid names otherwise;
  - every selected entry carries `source_qualified_name`, `digest` and `version`.
- **Per entry, in sorted order, under the Registry Alias Absence Rule.**
  - If the alias already resolves to a link whose digest, version and `source_qualified_name` all
    equal the snapshot's, the entry is skipped as already restored.
  - If the alias resolves to anything else, restore SHALL refuse and stop. That includes a link with
    the recorded digest but another version or source, such as one left by an earlier restore
    whose post-link check failed. Restore never unlinks, so that state needs an operator.
  - Otherwise it SHALL read the recorded source, and stop unless its digest equals the snapshot's.
    It SHALL then call `link(<registry project>/<collection>, aliases=[alias])` on that source.
  - After linking, it SHALL re-read the alias and stop unless the result is a link whose digest,
    version and `source_qualified_name` equal the snapshot's. The version matters because
    downstream idempotency keys hash it.
- **Output.** It SHALL print each entry's outcome as it happens, and stop on the first failure with
  a non-zero exit.
- **Invariants.** It SHALL never call `save()` or `unlink()` on any artifact, SHALL never delete
  anything, and SHALL never modify the snapshot file.

#### Scenario: Restore re-links a retired collection

- **WHEN** `registry restore anchor.json --execute --yes` runs for an entry whose alias is absent
- **THEN** the recorded source's `link` is called with the registry target and the configured
  alias
- **AND** the re-read link's digest, version and source equal the snapshot
- **AND** no `save()` or `unlink()` is called, and `anchor.json`'s bytes are unchanged

#### Scenario: Restore is idempotent

- **WHEN** restore runs again after a full restore
- **THEN** every entry is reported as already restored and `link` is not called

#### Scenario: Restore refuses to move an alias

- **WHEN** an entry's alias resolves to a digest other than the snapshot's, or to a non-link
- **THEN** restore exits non-zero without calling `link` for that entry or any later entry

#### Scenario: A mismatched earlier restore is not skipped

- **WHEN** an entry's alias resolves to a link with the recorded digest but a different version or
  source
- **THEN** restore does not report it as already restored, and exits non-zero naming the mismatch

#### Scenario: Restore requires a credential

- **WHEN** no wandb credential is resolvable
- **THEN** restore exits non-zero without constructing a wandb API client

#### Scenario: A transient error during restore propagates

- **WHEN** the alias read or the source read raises an error other than the alias not-found answer
- **THEN** the error propagates, `link` is not called for that entry, and no later entry is
  processed

#### Scenario: Restore validates before writing

- **WHEN** `--only` names a collection not in the snapshot, or a selected entry lacks
  `source_qualified_name`, `digest` or `version`, or the snapshot's registry or alias differs from
  the configuration
- **THEN** restore exits non-zero naming the problem, before any wandb write

#### Scenario: Restore stops on a changed source

- **WHEN** the recorded source's digest differs from the snapshot's
- **THEN** restore exits non-zero without calling `link`

#### Scenario: Restore detects a mismatched link

- **WHEN** the re-read link's version, digest or source differs from the snapshot's
- **THEN** restore exits non-zero naming the mismatch, and no later entry is processed

#### Scenario: Restore requires confirmation

- **WHEN** `--execute` is given without `--yes` and the operator declines
- **THEN** restore exits without calling `link`

#### Scenario: Restore dry run writes nothing

- **WHEN** restore runs without `--execute`
- **THEN** it lists each entry and whether it is already restored, and calls no wandb write method
