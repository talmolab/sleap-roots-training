## Context

Issue #8 asks for two coupled things: a real test-fixture layer, and the Tier-0 TensorFlow
reference baseline written down as committed fixtures rather than living only in mutable W&B run
summaries. The scientific subtlety is that the canonical run group
`20250625_cyl_arabidopsis_primary_receptive_field` (run name suffix `_training_v000`) is a
**receptive-field sweep**, not a replicate set — a fact an earlier version of the issue got wrong.
Getting the interpretation right is the whole point of the deliverable.

All claims below were verified by pulling the seven runs live from
`eberrigan-salk-institute-for-biological-studies/sleap-roots` and inspecting `run.config`,
`run.summary`, and `run.scan_history()` directly (not transcribed from the issue).

## Goals / Non-Goals

- **Goals:** a shared fixture layer that de-duplicates test setup without changing assertions;
  committed, provenance-stamped TF payloads; a test that locks the documented reference against the
  fixtures so the docs cannot silently drift; a correct `docs/tf-reference.md`; and the per-epoch
  logging requirement recorded for Tier 1.
- **Non-Goals:** re-running or re-training any TF model; computing new metrics; changing registry
  behavior; implementing the training-config schema itself (that is `add-config-schema`).

## Verified data (source of truth for the docs and the lock test)

| run id | `max_stride` | `dist_avg` | `dist_p50` | `dist_p90` | `vis_recall` | `oks_map` |
|---|---|---|---|---|---|---|
| `ijn85j6w` | 8 | — | — | — | — | — |
| `nxe8xgsd` | 16 | 1.7104 | 0.5859 | 4.5371 | 0.6310 | 0.00858 |
| `v7rdm7cd` | 16 | 0.9894 | 0.3575 | 2.6382 | 0.4657 | 0.01188 |
| `qilbptpp` | 32 | 2.0780 | 0.6613 | 4.4723 | 0.8294 | 0.02133 |
| `1tryadtu` | 32 | 1.3835 | 0.5434 | 3.5861 | 0.8294 | 0.04572 |
| `yenwgpjq` | 64 | 1.7085 | 0.7543 | 4.6775 | 0.8837 | 0.01461 |
| `26ryyfu2` | 64 | — | — | — | — | — |

- `max_stride` read from `config["model.backbone.unet.max_stride"]` (also nested under
  `config["model"]["backbone"]["unet"]["max_stride"]`). Confirms four distinct strides — two runs
  each at 16/32/64 and a single run at stride8 (**seven runs total**) → a **sweep**. Only stride16
  and stride32 are genuine same-stride pairs; stride64's second run (`26ryyfu2`) has no metrics, so
  stride64 is not a usable pair either.
- `ijn85j6w` and `26ryyfu2` summaries contain only the `_wandb` key — **no metrics logged**.
  `ijn85j6w` is the only stride8 run, so stride8 has no usable result.
- `oks_map` is 0.009–0.046 across every run with a summary — **broken**, excluded with a reason.
- `run.scan_history()` returns **0 rows** for a metric-bearing run (`nxe8xgsd`) → only final eval
  summaries were logged; no loss curve, no epoch count. This is the observability gap that motivates
  the Tier-1 per-epoch requirement.
- `sleap_version` is `1.4.1a2` (the TF `sleap-train` backend). Configs contain no API
  keys/tokens/secrets (verified); `config_path`/`filename` hold internal SMB UNC paths, which are
  provenance strings, not secrets.

## Decisions

- **Decision: do NOT pool or range across strides.** `dist_avg` differences between stride groups
  reflect architecture, not noise. The docs and the lock test range only *within* a stride
  (same-config): stride16 → 0.989–1.710 (~1.73×); stride32 → 1.383–2.078 (~1.50×). Rationale: a
  cross-stride "range" would masquerade architecture variation as run-to-run variance and mislead
  the Tier-1 oracle (`docs/roadmap.md` Tier 1 already codifies "report the TF reference as a range,
  not a point").
- **Decision: capability split.** Two ADDED capabilities — `test-fixtures` (the generic shared
  fixture layer) and `tf-reference` (the committed payloads + documented baseline + lock test) —
  because the fixture layer is orthogonal, reusable infra while the TF reference is a specific
  scientific artifact. Keeping them separate keeps each requirement single-purpose.
- **Decision: which registry test consumes a real payload.** The captured payloads are
  *training-run* configs; `registry/cards.py` and `registry/publish.py` operate on the *model
  artifact* side, and `registry/lineage.py` builds the *seed-run* config. The honest fit is a
  **lineage** test: `build_lineage(...)` produces keys merged into a wandb run config, so a test
  merges it onto a committed real run `config` and asserts (a) no key collision and (b) the merged
  dict is JSON-serializable — proving our lineage coexists with realistic run-config shapes instead
  of a hand-rolled `{}`. The `tf-reference` **lock test** carries the scientific weight.
- **Decision: fixtures are committed verbatim.** Store the payloads exactly as pulled (pretty-
  printed, key-sorted) so the fixture is auditable and the capture script is idempotent. Total size
  is ~112 KB across 14 files — cheap to commit.
- **Decision: per-epoch requirement lives in `add-config-schema`.** Per issue #8 ("capture that as a
  requirement when the training config schema lands (`add-config-schema`)") and roadmap Tier 1
  tracking, the requirement belongs with the training-config schema. It is added there as an ADDED
  requirement (the W&B logging config field defaults to per-epoch logging), **owned solely by
  `add-config-schema`** and only *motivated* here — this change makes no delta claim about it. It is
  committed in isolation and called out in the PR description (see Risks).

## Risks / Trade-offs

- **Fixtures drift from live W&B** → the lock test asserts against the committed files (not the
  network), and the capture script + manifest make a refresh reproducible and reviewable.
- **Touching a second change (`add-config-schema`) in one PR** slightly bends "one OpenSpec change
  per PR." Mitigation: the edit is a single additive requirement + task to an unimplemented change
  (0/13 tasks), issue #8 explicitly directs it there, it is kept in an isolated commit, and it is
  called out in the proposal Impact and the PR description.
- **Refactoring test setup could change behavior** → only genuinely-repeated setup (`tiny_matrix`,
  `stub_models_root`) is lifted; intentionally-inline bad-input literals (e.g. the malformed-YAML
  error tests) stay put; assertions are untouched; the suite must stay green.

## Migration Plan

Additive only. New files + a setup-only refactor; no consumer-facing API changes; no rollback
needed beyond reverting the branch.

## Open Questions

- None blocking. If reviewers prefer the per-epoch requirement to live in this change rather than
  `add-config-schema`, it can be moved with a one-line spec relocation.
