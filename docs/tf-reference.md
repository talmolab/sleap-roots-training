# TensorFlow reference baseline

The program roadmap grades later PyTorch (`sleap-nn`) tiers against an **established PyTorch
baseline**, and shows the old TensorFlow (`sleap-train`) numbers **for reference only** — exact
backend parity is not the bar (see [`docs/roadmap.md`](roadmap.md), "Oracle / validation
philosophy" and Tier 1). This document is that TF reference, written down durably: previously it
existed only as W&B run summaries that anyone could overwrite or delete.

The underlying run payloads are committed under
[`tests/fixtures/tf_reference/`](../tests/fixtures/tf_reference/) and locked against this document
by [`tests/test_tf_reference.py`](../tests/test_tf_reference.py), so the numbers here cannot silently
drift from the data.

## Source

- **W&B:** `eberrigan-salk-institute-for-biological-studies/sleap-roots`
- **Group:** `20250625_cyl_arabidopsis_primary_receptive_field` (run-name suffix `_training_v000`)
- **Backend:** TensorFlow `sleap-train` (`sleap_version` `1.4.1a2`)
- **Task:** *Arabidopsis* primary root, cylinder.

## This is a receptive-field sweep, not a replicate set

The seven runs vary `model.backbone.unet.max_stride` across **8, 16, 32, 64** — two runs each at
strides 16/32/64 and a single run at stride 8 (**seven runs total**). This is a **sweep** of an
architecture hyperparameter, **not** repeated runs of one fixed config.

**Do not pool or range `dist_avg` across different strides.** Differences between stride groups
reflect the architecture, not run-to-run noise; treating them as a single spread would masquerade an
architecture effect as variance and mislead the Tier-1 oracle. (An earlier characterization of this
group as "nominally identical replicates" was wrong; this document reflects the corrected reading.)

## Metrics (per stride)

Localization error is in pixels; lower `dist_*` is better, higher `vis_recall` is better.

| run id | `max_stride` | `dist_avg` | `dist_p50` | `dist_p90` | `vis_recall` |
|---|---|---|---|---|---|
| `ijn85j6w` | 8 | — | — | — | — |
| `nxe8xgsd` | 16 | 1.710 | 0.586 | 4.537 | 0.631 |
| `v7rdm7cd` | 16 | 0.989 | 0.358 | 2.638 | 0.466 |
| `qilbptpp` | 32 | 2.078 | 0.661 | 4.472 | 0.829 |
| `1tryadtu` | 32 | 1.383 | 0.543 | 3.586 | 0.829 |
| `yenwgpjq` | 64 | 1.709 | 0.754 | 4.678 | 0.884 |
| `26ryyfu2` | 64 | — | — | — | — |

## Same-config spread (report as a range, not a point)

Where the same stride has two runs, run-to-run spread is real and must be reported as a **range**,
never as a single "the TF number":

- **stride 16:** `dist_avg` **0.989–1.710** (~1.73×)
- **stride 32:** `dist_avg` **1.383–2.078** (~1.50×)

Either pair alone shows that real run-to-run variance exists even with the architecture held fixed.
Quoting one run from a pair as *the* reference — or comparing a single new run against a single old
run, as happened during onboarding (#1) — can produce spurious conclusions for exactly this reason.
Stride 64 is **not** a usable pair: its second run (`26ryyfu2`) logged no metrics. If a proper
same-config baseline range is needed for the Tier-1 oracle, it must come from these same-stride pairs
or from a fresh set of runs with identical configs varying only the seed.

## `oks_map` is excluded (broken)

`oks_map` reads far below any sensible value across **every** run with a summary — roughly
0.009–0.046 (well under ~0.05) — regardless of stride or `dist_avg`. It is **excluded** from the
reference as a broken/mis-scaled metric; do not report or compare it. Use the `dist_*` localization
metrics and `vis_recall` instead.

## Missing results

Two runs logged **no summary metrics** at all (their summaries contain only W&B bookkeeping):

- `ijn85j6w` (stride 8) — and it is the **only** stride-8 run, so **stride 8 has no usable result**.
- `26ryyfu2` (stride 64) — so stride 64 has only one usable run (`yenwgpjq`).

These are noted rather than silently dropped so the gaps are visible.

## Observability gap → per-epoch logging is required for Tier 1

These training runs logged **only final eval metrics** to W&B. `run.scan_history()` returns **zero
rows**, so there is no per-epoch loss curve and no epoch count. That is a large part of why the
Tier-0 onboarding repro (#1) could not be meaningfully compared against the original run.

The new `sleap-nn` (Tier 1) pipeline **must** log per-epoch train/val loss and the stopping epoch to
W&B. This requirement is recorded on the training-config schema in
`openspec/changes/add-config-schema/` and in [`docs/roadmap.md`](roadmap.md) Tier 1.
