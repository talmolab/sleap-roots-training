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

## Metrics (per stride) — these W&B numbers are **millimeters**

> **Correction (2026-08-06).** An earlier version of this document stated that these `dist_*`
> values are pixels, reasoning from `input_scaling: 1`. That is **wrong**, and it produced a
> spurious "PyTorch is 20–40× worse than TF" comparison in [training.md](training.md).
>
> These values come from each run's W&B summary, which was written by a **lab post-processing
> step, not by SLEAP**. Each run directory on the share holds a sibling `detailed_distances.csv`
> whose single column is literally headed **`distances_mm`**; its cells reproduce the run's
> `metrics_summary.csv` (and therefore these W&B summary values) to six decimals on
> mean/p50/p90/p95/p99/std. For `nxe8xgsd`, 159 of its 252 cells are valid and 159/252 =
> 0.630952, exactly the `vis_recall` below. That post-processing step also **re-matched instances
> independently** of SLEAP (42 matched / 159 valid cells, versus SLEAP's own 40 / 134), so its
> `vis_recall` is not SLEAP's either.
>
> SLEAP's own pixel metrics are in the next section. Do **not** compare the table below against
> any pixel-space number.

Lower `dist_*` is better, higher `vis_recall` is better.

| run id | `max_stride` | `dist_avg` (mm) | `dist_p50` (mm) | `dist_p90` (mm) | `vis_recall` (mm pipeline) |
|---|---|---|---|---|---|
| `ijn85j6w` | 8 | — | — | — | — |
| `nxe8xgsd` | 16 | 1.710 | 0.586 | 4.537 | 0.631 |
| `v7rdm7cd` | 16 | 0.989 | 0.358 | 2.638 | 0.466 |
| `qilbptpp` | 32 | 2.078 | 0.661 | 4.472 | 0.829 |
| `1tryadtu` | 32 | 1.383 | 0.543 | 3.586 | 0.829 |
| `yenwgpjq` | 64 | 1.708 | 0.754 | 4.677 | 0.884 |
| `26ryyfu2` | 64 | — | — | — | — |

## Pixel-space metrics — the numbers that are comparable to the PyTorch baseline

Recovered 2026-08-06 by reading each run's own `metrics.val.npz` on the share (the file SLEAP
itself wrote; it pickles `sleap.*` classes, so it needs an unpickler that maps those names onto an
`np.ndarray` subclass). Independently reproduced by scoring each run's saved
`labels_gt.val.slp` against its `labels_pr.val.slp` with **sleap-nn's** `Evaluator`, pairing frames
by true source identity (the embedded `source_video` `.h5` basename plus `frame_idx`).

**The two evaluators agree exactly.** On `nxe8xgsd`, sleap-nn's `Evaluator` reproduces SLEAP's own
`metrics.val.npz` on all 11 metrics to every printed digit (`dist` avg/p50/p90/p95/p99,
`vis` recall/tp/fn, `mOKS`, `oks_voc` mAP/mAR, and a `dists` array of shape (40, 6) with 134 valid
cells on both sides). Every other run with a `metrics.val.npz` cross-checks exactly too. There is
**no evaluator difference between the backends**, and the inference parameters match as well
(`peak_threshold` 0.2 both sides, integral refinement at patch size 5, identical PAF grouping
constants).

Distances are original-image pixels. The v000 val split holds **44 ground-truth instances**.

| `max_stride` | run id | `dist_avg` px | `dist_p50` px | `dist_p90` px | `vis_recall` | instances matched |
|---|---|---|---|---|---|---|
| 8 | `ijn85j6w` | — | — | — | — | 0 / 44 (collapsed) |
| 16 | `v7rdm7cd` | 23.72 | 8.21 | 53.23 | 0.495 | 36 / 44 |
| 16 | `nxe8xgsd` | 39.00 | 8.42 | 120.17 | 0.558 | 40 / 44 |
| 32 | `1tryadtu` | 29.85 | 8.61 | 94.93 | 0.782 | 42 / 44 |
| 32 | `qilbptpp` | 30.23 | 9.49 | 67.14 | 0.814 | 43 / 44 |
| 64 | `26ryyfu2` | 21.65 | 6.87 | 52.24 | 0.869 | 42 / 44 |
| 64 | `yenwgpjq` | 21.93 | 8.95 | 54.33 | 0.872 | 43 / 44 |

These numbers are **not** locked by `tests/test_tf_reference.py`, because they are read from the
share rather than from a committed fixture. Committing them as fixtures would be a worthwhile
follow-up.

## Same-config spread (report as a range, not a point)

Where the same stride has two runs, run-to-run spread is real and must be reported as a **range**,
never as a single "the TF number":

- **stride 16:** `dist_avg` **0.989–1.710** mm (~1.73×), **23.72–39.00** px (~1.64×)
- **stride 32:** `dist_avg` **1.383–2.078** mm (~1.50×), **29.85–30.23** px (~1.01×)
- **stride 64:** `dist_avg` **21.65–21.93** px (~1.01×) — a usable pair in pixel space (see below)

Either pair alone shows that real run-to-run variance exists even with the architecture held fixed.
Quoting one run from a pair as *the* reference — or comparing a single new run against a single old
run, as happened during onboarding (#1) — can produce spurious conclusions for exactly this reason.
Note that the mm and px spreads disagree about *which* strides are noisy (stride 32 spans 1.50× in
mm but 1.01× in px), another reason not to mix the two. If a proper
same-config baseline range is needed for the Tier-1 oracle, it must come from these same-stride pairs
or from a fresh set of runs with identical configs varying only the seed.

## `oks_map` is excluded (likely mis-calibrated, not a generic bug)

`oks_map` reads far below any sensible value across **every** run with a summary — roughly
0.009–0.046 (well under ~0.05) — regardless of stride or `dist_avg`. It is **excluded** from the
reference; do not report or compare it. Use the `dist_*` localization metrics and `vis_recall`
instead.

A concrete hypothesis for *why* — worth checking before this becomes a permanent, unexamined dead
end: `vis_prec` is **exactly `1`** in every one of the five summarized runs while the OKS metrics
collapse. OKS is scored against per-keypoint sigma constants; if those sigmas were inherited from a
different keypoint domain (e.g. human/animal pose) and applied unchanged to the root skeleton, they
would depress OKS-based metrics uniformly while the `dist_*` and visibility metrics stay meaningful.
That points at a root-domain **OKS-sigma calibration** problem, not at the models being bad. This is
recorded here and tracked in #17; revisit it if OKS metrics are ever needed for Tier-1 scoring.

## Missing results

Two runs logged **no summary metrics** at all (their summaries contain only W&B bookkeeping). The
2026-08-06 pass over the run directories on the share resolved *why*, and the two cases turn out to
be completely different:

- `26ryyfu2` (stride 64) — **the metrics exist**, they just never reached W&B. Its run directory has
  a normal `metrics.val.npz` (`dist_avg` 21.65 px, `vis_recall` 0.869, 42 / 44 matched), so stride 64
  **is** a usable pair in pixel space. Only the mm post-processing and the W&B summary are missing.
- `ijn85j6w` (stride 8) — **the run collapsed.** Its `labels_pr.{train,val,test}.slp` contain
  **0 predicted instances**, so there was nothing for either evaluator to score and no metrics file
  was ever written. Stride 8 has no usable result, and the reason is model collapse, not a logging
  gap.

That second point matters beyond bookkeeping: a legacy TensorFlow run collapsed to zero predictions
on this dataset, the same failure mode as the `output_stride 2` collapse discussed in
[training.md](training.md). Collapse on this data is **not** unique to `sleap-nn`.

## Observability gap → per-epoch logging is required for Tier 1

These training runs logged **only final eval metrics** to W&B. `run.scan_history()` returns **zero
rows**, so there is no per-epoch loss curve and no epoch count. That is a large part of why the
Tier-0 onboarding repro (#1) could not be meaningfully compared against the original run.

The new `sleap-nn` (Tier 1) pipeline **must** log per-epoch train/val loss and the stopping epoch to
W&B. This requirement is recorded on the training-config schema in
`openspec/changes/add-config-schema/` and in [`docs/roadmap.md`](roadmap.md) Tier 1.
