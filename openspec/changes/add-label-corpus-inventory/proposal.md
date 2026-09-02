# Proposal: A re-runnable label-corpus inventory

## Why

No inventory reconciles the label registry, the SLEAP share, and Bloom against each other.
Every table in this program was seeded from a snapshot of *deployed* state, and each
snapshot's omissions silently became the schema — so `wandb-registry-sleap-roots-labels`
holds **8** collections against an expected corpus of roughly 25–30, and `skeletons.yaml`
cannot express two of the eight because it has no `mode` key.

## Background

Three sources describe one corpus and none has been reconciled against the others. Details,
including the verified findings this rests on, are in
[`docs/superpowers/specs/2026-09-01-label-and-model-inventory-design.md`](../../../docs/superpowers/specs/2026-09-01-label-and-model-inventory-design.md).
In brief:

- **The registry** holds 8 collections. Six carry a repair version that re-embeds images and
  in doing so drops the species metadata and records a temporary path; the original version
  holds the real source path.
- **The share** resolves all eight recorded source paths, across three prefixes, and every
  one size-matches its registry copy. `#49` currently records these paths as unusable; that
  assessment reads the repair version.
- **Bloom** is joinable on the QR code embedded in each video path, and supplies
  `species_name`, `plant_id` and `plant_age_days` per scan — the facts the other two sources
  only imply.

## What Changes

**Additive. No existing capability, table, or shipped code path changes.**

Add a **label-inventory** capability: a re-runnable command that resolves each collection to
a digest-verified local file, derives per-scan facts independently from the labels file and
from Bloom, reconciles the two, and emits three artifacts.

```
sleap-roots-training inventory labels --out inventory/
```

Deriving from two sources and requiring them to agree is the point — see `design.md` D3.

### Deliverables

It emits **evidence, not cards.** A `LabelCard` needs `registry_id` and `version`, which are
meaningless for a collection that was never registered — and the corpus holds more
unregistered collections than registered ones. `mode` and `root_type` have no source in scan
metadata either. So the aggregate carries what is evidenced, and `#49` builds cards from it,
supplying the rest from its own decision record.

- **Per-scan CSV, one per collection**, committed to `inventory/`.
- **Aggregate YAML, all collections** — species, counts, the observed age window with its
  epoch, skeleton facts, per-field confidence, and the reconciliation tally.
- **Skeleton-table diff** — which rows each collection verifies, contradicts, or is missing,
  including the `mode`-keying gap.

## Non-goals

- **Writing anywhere.** The Bloom client issues only `GET`, which forbids every table write
  and every remote procedure call by construction. Enforced normatively, not by convention.
- **Fixing what it finds.** `skeletons.yaml`'s missing `mode` key and absent species rows,
  `#3`'s deferred plate models, and the `RootType` gap for tip models are each a separate
  change. This capability reports.
- **The model inventory.** A second change, sharing the share walk but feeding `#3` and the
  roadmap rather than `#49`.
- **Train/test splits.** The unit is the superset labels file per collection.
- **Widening any vocabulary.** The reported species will include wheat, sorghum, medicago
  and alfalfa, which the model-side vocabulary does not contain. That is expected output;
  widening the label-side vocabulary is `#49`'s D5.

## Impact

- **Affected specs:** new **`label-inventory`** capability (ADDED); rationale in `design.md`
  D1.
- **Affected code:** new `src/sleap_roots_training/inventory/` — `resolve.py`, `read.py`,
  `bloom.py`, `reconcile.py`, `discover.py`, `skeleton_diff.py`, `emit.py`, `redact.py` —
  and one `inventory` command group in `cli.py`, placed **before** the existing `labeling`
  group rather than appended at end of file, so it does not collide with `#48`'s
  end-of-file append.
- **Affected tests:** new `tests/test_inventory_*.py`. No existing test changes.
- **Affected packaging:** `pyproject.toml` and `uv.lock` — see New dependency below.
- **Affected docs:** `README.md` (a new operator section, following the
  `seed-registry` pattern), `docs/labeling-packages.md` (artifact schemas and vocabularies),
  `openspec/project.md` (Purpose, and the system-of-record split), `docs/roadmap.md`
  (placement, and its relationship to `#23`'s inventory), `docs/CHANGELOG.md`.
- **Not touched:** `skeletons.yaml`, `model_selection.yaml`, `chooser.py`, `SPECIES_VOCAB`,
  `registry/`, `labeling/`, and `#49`'s change directory.
- **Overlaps:** `.github/workflows/verify-skeleton-table.yml` and
  `test_the_table_agrees_with_the_published_label_collections` already diff node counts
  against the registry, by downloading `:latest` — the repair version, which is why they
  cannot see species. This capability subsumes that check from better inputs (manifest
  digests instead of gigabytes of downloads, Bloom-sourced species instead of skeleton-name
  parsing). Retiring the workflow is deliberately deferred so this change stays additive;
  the duplication is recorded here so the two do not silently diverge.
- **New dependency: `bloomctl`.** An earlier draft declined it to save ~40 transitive
  packages and reached Bloom over `requests` instead. That was a weight trade-off made
  against a read path whose shape had never been established: the base path, the token
  exchange and the header contract appear nowhere in this repo, and are **not** recoverable
  from `bloomctl` either, because it delegates HTTP entirely to `supabase-py`. Depending on
  it instead inherits the authenticated client, session refresh, the batching helper with its
  measured character budget, the filter-quoting rule, the scan-export column names as an
  importable constant, and a **plate** read path — four of which the earlier draft promised
  to specify here and one of which it could not. It resolves cleanly against `main`'s
  contracts pin. The cost is real (`supabase`, `httpx`, `realtime`, `cryptography` and the
  rest) and is accepted rather than paid in reimplemented production authentication.
- **Scope on the share:** only the project owner's SLEAP directory is walked. Other users'
  directories are out of scope and are not read.
- **Requires:** the `Z:` share, `WANDB_API_KEY`, and a Bloom credentials profile. The
  available credentials belong to a person and **carry write authority**; the read-only
  guarantee is therefore enforced by the `GET`-only client (see the
  `Only Read Operations Are Issued` requirement), not by the account's permissions. The
  registry and share are jointly required; Bloom absence degrades to an all-unresolved run
  that emits per-scan output and no aggregate.
