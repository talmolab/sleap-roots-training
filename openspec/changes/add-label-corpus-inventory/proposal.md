# Proposal: A re-runnable label-corpus inventory

## Why

No inventory reconciles the label registry, the SLEAP share, and Bloom against each other.
Every table in this program was seeded from a snapshot of *deployed* state, and each
snapshot's omissions silently became the schema — so `wandb-registry-sleap-roots-labels`
holds **8** collections against an expected corpus of roughly 25–30, and `skeletons.yaml`
cannot express at least **three** of the eight: two because it has no `mode` key, and wheat
because it has no row at all.

## Background

Three sources describe one corpus and none has been reconciled against the others. Details,
including the verified findings this rests on, are in
[`docs/superpowers/specs/2026-09-01-label-and-model-inventory-design.md`](../../../docs/superpowers/specs/2026-09-01-label-and-model-inventory-design.md),
which lands in its own `docs:` PR before this change (see Prerequisites). In brief:

- **The registry** holds 8 collections. Six carry a repair version that re-embeds images and
  in doing so drops the species metadata and records a temporary path; the original version
  holds the real source path.
- **The share** resolves all eight recorded source paths, across three prefixes, and every
  one size-matches its registry copy. `#49` currently records these paths as unusable; that
  assessment reads the repair version.
- **Bloom** is joinable, for cylinder scans, on the plant code embedded in each video path,
  and supplies the species, plant identity and age the other two sources only imply. Its
  plate schema carries no age at all, which is why plate is read from the file only.

## What Changes

**Additive. No existing capability, table, or shipped code path changes.**

Add a **label-inventory** capability: a re-runnable command that enumerates every labels file
under a walk root, resolves each promoted collection to a local file — digest-verified where
a registry artifact exists — derives per-scan facts independently from the labels file and
from Bloom, reconciles the two, and emits three artifacts.

```
sleap-roots-training inventory labels \
  --walk-root Z:/users/<owner>/SLEAP \
  --out inventory/ \
  --decisions inventory/decisions.yaml \
  --bloom-profile <profile>
```

Deriving from two sources and requiring them to agree is the point for **species**; for age
and date it is a staleness check rather than corroboration, and the spec says which is which
— see `design.md` D3.

**Two judgments belong to a person, not to the tool.** Which labels files are collections,
and which source-to-source disagreements are accepted, are recorded in a committed
`decisions.yaml` that the run **reads and never writes** (D15). The scale is measured, not
estimated: the walk root holds **18,099** labels files, of which 13,164 are inference
outputs. Excluding derived files by shape leaves ~1,450, of which **~470 carry a version
suffix** and are the real promotion candidates — against an expected ~25-30 finished
collections. A directory here routinely
holds a finished superset, the per-day inputs merged into it, files of another species, and
scratch — tiers no structural rule can separate (D8). And a disagreement between the path and
Bloom is a finding to review, not a value to pick: it withholds only the fields it touches,
marked `awaiting_adjudication`, while an unresolved scan withholds nothing (D4).

### Deliverables

It emits **evidence, not cards.** A `LabelCard` needs `registry_id` and `version`, which are
meaningless for a collection that was never registered — and the corpus holds more
unregistered collections than registered ones. `mode` and `root_type` have no source in scan
metadata either. So the aggregate carries what is evidenced, and `#49` builds cards from it,
supplying the rest from its own decision record.

- **Per-scan CSV, one per promoted collection**, in `inventory/`.
- **Aggregate YAML, one entry per enumerated labels file** — classification, species, counts,
  the observed age window with its provenance and epoch, skeleton facts, per-field
  confidence, the reconciliation tally, and the adjudication queue.
- **Skeleton-table diff** — which rows each collection verifies, contradicts, or is missing,
  including the `mode`-keying gap and any root type outside the contract vocabulary.

This PR commits **one adjudicated collection** as a worked example, so that the pinned path's
"regenerate and diff" reason is true of this PR and not only of a follow-up, and so that the
digest, the join and the redaction rule are proven against real data before merge (D11). The
remaining collections are adjudicated and committed in a follow-up PR.

## Prerequisites

- **A `docs:` PR** landing the background design doc on `main`, corrected against D4 and D14,
  so this change and the model-inventory change both cite a merged path.
- **A separate change** amending the green-every-commit rule in the **five** places it is
  written, so this capability does not carry a repo-wide convention change. It also collides
  with `#48` on `openspec/project.md`. See `design.md` Prerequisites.
- **The rebase onto `origin/main`** is a hard prerequisite of adding the dependency, not
  housekeeping: `bloomctl` is unsatisfiable against this branch's current contracts pin.

## Non-goals

- **Writing anywhere.** The Bloom data plane issues only `GET`, which forbids every table
  write and every *volatile* remote procedure — a read-only procedure may itself be served
  over `GET`, so the guarantee rests on the gateway refusing `GET` for a volatile one.
  Enforced normatively, not by convention.
- **Fixing what it finds.** `skeletons.yaml`'s missing `mode` key and absent species rows,
  `#3`'s deferred plate models, the `RootType` gap for tip models, and splitting the pooled
  multi-species files are each a separate change. This capability reports.
- **Reconciling plate scan metadata.** Bloom carries no plate age, and a plate path carries
  no key to join on. Plate collections are inventoried from the file, with age and species
  share-derived and marked as such. The `mode` keying gap still lands, because node counts are
  file-derived — see `design.md` D16.
- **The model inventory.** A second change, sharing the share walk but feeding `#3` and the
  roadmap rather than `#49`.
- **Train/test splits.** A split describes a training run, not a corpus.
- **Widening any vocabulary.** The reported species will include wheat, sorghum, medicago
  and alfalfa, which the model-side vocabulary does not contain. That is expected output;
  widening the label-side vocabulary is `#49`'s D5.

## Impact

- **Affected specs:** new **`label-inventory`** capability (ADDED); rationale in `design.md`
  D1.
- **Affected code:** new `src/sleap_roots_training/inventory/` — `resolve.py`, `read.py`,
  `bloom.py`, `reconcile.py`, `discover.py`, `promote.py`, `skeleton_diff.py`, `emit.py`,
  `redact.py`, and the leaf `vocab.py` the vocabulary requirement mandates — and one
  `inventory` command group in `cli.py`, placed **after the `seed-registry` command and
  before the `validate` command**, a location none of `#48`'s `cli.py` hunks touches.
- **Affected tests:** new `tests/test_inventory_*.py`, including an `integration`-marked tier
  that exercises the real share, a real manifest digest and a real Bloom read. No existing
  test changes.
- **Affected CI:** `.github/workflows/ci.yml` — add `inventory/**`, `README.md` and
  `.claude/commands/**` to both paths filters, so the committed artifacts and the doc-locks
  are actually run on the commits that can break them.
- **Affected packaging:** `pyproject.toml` and `uv.lock` — see New dependency below.
- **Affected repo config:** `.gitattributes` — pin `inventory/** text eol=lf`, since
  `* text=auto` plus `core.autocrlf=true` would otherwise check the committed artifacts out
  with CRLF on Windows and break the byte-identity guarantee.
- **Affected docs:** `README.md` (a new operator section following the `seed-registry`
  pattern, with the full option surface in a fenced command line so the doc-lock can see it,
  plus a link to the guide from the doc list, which currently omits it),
  `docs/labeling-packages.md` (all three artifact schemas and all five vocabularies),
  `openspec/project.md` (Purpose, and the source-of-record split in **Important
  Constraints**, where the constraint actually lives), `.claude/commands/review-pr.md` (which
  restates that constraint as "not Bloom" inside the reviewer prompt),
  `src/sleap_roots_training/labeling/data/skeletons.yaml`'s header (a comment naming the diff
  as what now flips `verified:`, and fixing its stale citation to a skeleton table that no
  longer exists in the command doc), `docs/roadmap.md` (Tier 2.7's stated blocker dissolves —
  node counts are readable from the labels files, so the spacing measurement no longer waits
  on `#11`'s backfill; the rest of the Tier 2 reconciliation landed in `62d1dc9`), and
  `docs/CHANGELOG.md`.
- **Not touched:** `skeletons.yaml`'s rows, `model_selection.yaml`, `chooser.py`,
  `SPECIES_VOCAB`, `registry/`, `labeling/`, and `#49`'s change directory.
- **Overlaps:** `.github/workflows/verify-skeleton-table.yml` and
  `test_the_table_agrees_with_the_published_label_collections` already diff node counts
  against the registry, by downloading `:latest` — the repair version, which is why they
  cannot see species. This capability reads the same facts from better inputs (manifest
  digests instead of gigabytes of downloads, Bloom-sourced species instead of skeleton-name
  parsing) but **does not subsume** that check: it needs only `WANDB_API_KEY` and runs
  unattended on a hosted runner, whereas this capability needs the `Z:` share and so cannot
  run in CI. Retiring the workflow is a separate change and is not implied here; the
  duplication is recorded so the two do not silently diverge.
- **New dependency: `bloomctl`.** An earlier draft declined it and reached Bloom over
  `requests` instead. That was a weight trade-off made against a read path whose shape had
  never been established: the base path, the token exchange and the header contract appear
  nowhere in this repo, and are **not** recoverable from `bloomctl` either, because it
  delegates HTTP entirely to `supabase-py`. Depending on it inherits the authenticated
  client, session refresh, the batching helper with its measured character budget, and the
  cylinder scan-export column names as an importable constant. It does **not** supply a
  filter-quoting rule — every `in_()` there filters on numeric ids, so quoting a
  ten-character string key is specified here — and its plate read path is out of scope
  (D16). `bloomctl` is a CLI, not a library: the symbols used are private module internals,
  so they are named in one adapter module behind a drift guard and the version is capped
  tightly. Pin `bloomctl>=0.1.0a5,<0.1.0b1`; a release-numbered lower bound resolves to
  nothing, since only `0.1.0aN` is published. It resolves against `main`'s
  `sleap-roots-contracts==0.1.0a8` pin (measured: +25 packages over this repo's core set) and
  is **unsatisfiable** against this branch's `==0.1.0a6`, which is why the rebase comes first.
  The cost — `supabase`, `httpx`, `realtime`, `cryptography` and compiled wheels on all six
  matrix legs — is accepted rather than paid in reimplemented production authentication.
- **Scope on the share:** only the project owner's SLEAP directory is walked. Other users'
  directories are out of scope and are not read.
- **Requires:** the `Z:` share, `WANDB_API_KEY`, and a Bloom credentials profile. The
  available credentials belong to a person and **carry write authority**; the read-only
  guarantee is therefore enforced by the `GET`-only data plane (see the
  `Only Read Operations Are Issued` requirement), not by the account's permissions. The
  registry and share are jointly required — an unreachable registry cannot be told apart from
  a collection that was never registered, and reporting an outage as `unregistered` would
  launder it into permanent provenance. Bloom absence degrades to an all-unresolved run that
  still emits the per-scan tables, the skeleton diff, and an aggregate entry per collection
  carrying its file-derived fields, with every reconciliation-derived field withheld and
  marked.
