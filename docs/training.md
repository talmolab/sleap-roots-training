# Config-driven training (Tier 1)

How to train and evaluate one keypoint model from a single config file on the `sleap-nn`
backend. This guide covers **config authoring, validation, emitting the sleap-nn config, and
reading results**; for the one-time backend **install** and the raw `sleap-nn` train/predict
mechanics (GPU setup, sample data, `sleap-nn track`), see
[training-backend.md](training-backend.md).

> **Status: verified end-to-end on the RTX A5000 (2026-07-23).** `validate → emit → sleap-nn
> train` on the Tier-0.5 sample: the raw config (carrying `experiment`) is rejected by sleap-nn
> (`ConfigKeyError: Key 'experiment' not in 'TrainingJobConfig'`), so `emit` is required; the
> emitted config trains + runs eval (writing `metrics.*.npz`) with no post-fit `preprocessing`
> crash; and a short `use_wandb=true` run's `run.scan_history()` returned per-epoch rows carrying
> `epoch` + `loss` (the legacy TF runs returned zero) — closing the observability gap.

## The config file

An experiment is one YAML file: `sleap-nn`'s own `data_config` / `model_config` /
`trainer_config` (consumed as-is — see the runbook for their shape), **plus** a repo-owned
`experiment` block recording the domain identity `sleap-nn` has no concept of:

```yaml
experiment:
  species: arabidopsis      # a known species (registry/chooser.py SPECIES_VOCAB)
  mode: cylinder            # a known mode (MODE_VOCAB)
  root_type: primary        # primary | lateral | crown
  dataset:
    name: cyl_arabidopsis_primary
    path: data/arabidopsis_primary_cylinder.train.pkg.slp
```

A complete, seeded, ready-to-run example is committed at
[`examples/arabidopsis_primary_cylinder.yaml`](../examples/arabidopsis_primary_cylinder.yaml) —
copy it and edit the `experiment` block, the dataset paths, and the model/trainer knobs rather
than writing a config from scratch.

Two repo rules the schema enforces, both closing real `sleap-nn` 0.2.0 gaps:

- **`trainer_config.seed` is required.** 0.2.0 ships no default seed. Pinning a seed makes the
  *config* reproducible (bitwise GPU determinism additionally depends on `sleap-nn`/Lightning
  flags this wrapper does not set). For the Tier-1 baseline you then **vary the seed across the
  2–3 runs** (fixed within a run, different between runs) so the spread is real — see below.
- **`data_config.preprocessing` is required.** 0.2.0's `run_training` reads it *after* the fit
  loop and crashes with `ConfigAttributeError` if it is absent, so `validate` requires it up
  front (the example ships a `preprocessing` block).

Two things this wrapper does **not** capture yet (deferred to Tier 2, tracked in #10/#11): run
provenance (a config hash / git commit) and a dataset content checksum. A config names its dataset
by path, not by a verified hash, so do not assume a run is fully reproducible from the config alone
today.

## 1. Validate

```bash
sleap-roots-training validate examples/arabidopsis_primary_cylinder.yaml
```

This checks the `experiment` metadata (species / mode / root_type vocab), the required integer
seed, the required `preprocessing` block, and the W&B-enablement pairing. With the `[train]`
extra installed it additionally delegates to `sleap-nn`'s own validation (a backbone and a head
must be set); without it, that deep check is skipped with a note. Exit `0` means the config
conforms; a non-zero exit prints the offending field.

## 2. Emit the sleap-nn config

`sleap-nn`'s struct-mode config rejects the repo-owned `experiment` key, so strip it into a
sleap-nn-native config before training:

```bash
sleap-roots-training emit examples/arabidopsis_primary_cylinder.yaml -o resolved.yaml
```

`emit` validates first, then writes the config with the `experiment` block removed (the
`preprocessing` block is carried through). It is base-install safe, so you can author + validate
+ emit on one machine and train on another (the Mac-authors / A5000-trains workflow).

## 3. Train (with built-in eval)

```bash
sleap-nn train --config resolved.yaml
```

`sleap-nn train` runs train → inference → eval in one call, writing the checkpoint plus
`labels_pr.*.slp` and `metrics.*.npz` into `<ckpt_dir>/<run_name>`. (Needs the `[train]` extra;
see the runbook.)

## 4. Read the metrics

The eval metrics land in `metrics.val.0.npz` / `metrics.train.0.npz` next to the checkpoint (the
`.0.` is sleap-nn's per-eval-dataset index):

```python
import numpy as np

m = np.load("models/cyl_arabidopsis_primary/metrics.val.0.npz", allow_pickle=True)
print(m.files)  # the exact metric arrays sleap-nn wrote (localization distance, OKS, PCK, ...)
```

Report the localization error and PCK as the accuracy headline. Note the legacy TF reference
uses the W&B keys `dist_avg` / `oks_map` (see [tf-reference.md](tf-reference.md)); `sleap-nn`'s
`.npz` names may differ (inspect `m.files`). Do **not** report `oks_map` as a headline number —
in the TF reference it reads implausibly low and is treated as a mis-calibration hypothesis for
the root domain (tracked in #17), not an established result.

## 5. Confirm per-epoch W&B logging

Roadmap Tier 1 requires per-epoch metrics in W&B (the legacy TF runs logged only final
summaries, so `scan_history()` returned zero rows and there was no loss curve). Per-epoch
logging is expected to be `sleap-nn` / Lightning's default — this repo adds no config field to
"enable" it — so it is confirmed empirically. Set `trainer_config.use_wandb: true` and fill
`trainer_config.wandb.entity` / `project`, then after a run check the history:

```python
import wandb

run = wandb.Api().run("<entity>/<project>/<run_id>")
rows = list(run.scan_history())
assert rows, "no history was logged"  # the legacy TF runs returned zero rows here
# Each row carries its epoch + loss, so the per-epoch curve is recoverable:
assert all("epoch" in r for r in rows), "history rows are missing 'epoch'"
assert any("loss" in key for r in rows for key in r), "no loss logged"
print(len(rows), "rows; keys:", list(rows[0].keys()))
```

Verified on the A5000 (2026-07-23): a 3-epoch `use_wandb=true` run returned **906 `scan_history()`
rows, all carrying `epoch` + `loss`** (keys: `loss`, `epoch`, `trainer/global_step`, `_step`, …) —
versus zero rows for the legacy TF runs. Val loss (`val/loss`) is logged on the epoch-boundary rows.

## PyTorch baseline

**Established (2026-07-29) on the RTX A5000.** The Tier 1 PyTorch-native baseline is
Arabidopsis primary-root, multi-plant cylinder, bottom-up keypoints on the **exact original v000
held-out split** (99 train / 21 val frames, 6-node skeleton `r1..r6`), evaluated on
`val.pkg.slp`. It is reported as a **range across 3 same-config runs varying only
`trainer_config.seed`** (42 / 43 / 44) — that range, not TF parity, is what later tiers
reproduce-or-beat.

**Data provenance.** The three v000 files were made self-contained for the offline GPU box with
[`scripts/clean_pkg.py`](../scripts/clean_pkg.py) (drops the `source_video` share pointer and a
frame-less stray video, re-embeds frames); the labeled-frame set is unchanged (99 train / 21 val,
`r1..r6`). Dataset content is identified by path, not yet a verified hash (deferred to #10/#11).

**Metrics.** Read from each run's `metrics.val.0.npz` with
[`scripts/dump_val_metrics.py`](../scripts/dump_val_metrics.py): `distance_metrics.avg` →
`dist_avg`, `.p50` → `dist_p50`, `visibility_metrics.recall` → `vis_recall` (the dumper prefixes
these with the top-level `metrics.` key). Distances are in **original-image pixels** — predictions
are rescaled from the `scale: 0.5` input back to the source 1088×2048 coordinates before matching
the original-coordinate ground truth, so they are directly comparable to the TF reference's native
pixels. (Verified in sleap-nn 0.2.0 source: `sleap_nn/inference/{single_instance,topdown,bottomup}.py`
divide predicted peaks by `input_scale` then `eff_scale`, and `sleap_nn/training/lightning_modules.py`'s
`validation_step` transforms predictions **and** GT back to original-image space before
`sleap_nn/evaluation.py` — which itself does no rescaling — computes the distances.) `oks_map` is
excluded (mis-calibrated for this domain, #17); PCK is present in the npz but not used as the headline.

Two output resolutions were run (see the collapse finding below); the reported baseline is the
stable **`output_stride 4`** config, [`examples/baseline_bottomup_v000_os4.yaml`](../examples/baseline_bottomup_v000_os4.yaml).
Reproduce a single run with:

```bash
sleap-roots-training validate examples/baseline_bottomup_v000_os4.yaml
sleap-roots-training emit     examples/baseline_bottomup_v000_os4.yaml -o resolved.yaml
sleap-nn train --config resolved.yaml
```

Key hyperparameters, all pinned in the config file above: UNet `filters 16`, `filters_rate 2.0`,
`max_stride 32`, `output_stride 4`; bottom-up head confmaps `sigma 2.5` / `output_stride 4`, PAFs
`sigma 75` / `output_stride 8`; input `scale 0.5` (net sees 544×1024); Adam `lr 1e-4`, `batch_size
4`, `reduce_lr_on_plateau`, `max_epochs 200` with early stopping (`patience 10`);
`online_hard_keypoint_mining` on. The optimizer / batch size / LR schedule / early-stopping values
were sleap-nn 0.2.0 defaults the runs used, now pinned explicitly in the config so the baseline is
reconstructable regardless of backend default changes. (These explicit pins were committed **after**
the six reported runs; each value is byte-equal to the 0.2.0 default the runs actually used —
checked against the saved `Training Config` — so a re-run from this config reproduces the numbers.)

### Baseline range — `output_stride 4` (val)

| seed | `dist_avg` (px) | `dist_p50` (px) | `dist_p90` (px) | `vis_recall` | instances detected | W&B |
|------|-----------------|-----------------|-----------------|--------------|--------------------|-----|
| 42   | 30.09 | 18.62 | 72.36 | 0.912 | 44 / 44 | [p297iqwv](https://wandb.ai/eberrigan-salk-institute-for-biological-studies/sleap-roots-tier1-baseline/runs/p297iqwv) |
| 43   | 37.79 | 21.23 | 73.63 | 0.850 | 44 / 44 | [u1vhk114](https://wandb.ai/eberrigan-salk-institute-for-biological-studies/sleap-roots-tier1-baseline/runs/u1vhk114) |
| 44   | 30.55 | 17.73 | 66.75 | 0.885 | 44 / 44 | [67sjzrus](https://wandb.ai/eberrigan-salk-institute-for-biological-studies/sleap-roots-tier1-baseline/runs/67sjzrus) |
| **range** | **30.1 – 37.8** | **17.7 – 21.2** | 66.8 – 73.6 | **0.85 – 0.91** | all detected | — |

All three seeds converged and detected every ground-truth instance (Unmatched GT = 0), so the
"instances detected" column is 44/44. `vis_recall` is a **separate**, keypoint-level metric — the
fraction of visible ground-truth keypoints recalled among the matched instances — not an
instance-detection rate. The three os4 seeds early-stopped at epochs **83 / 105 / 118** (42/43/44),
i.e. each ran the full early-stopping regime. The seed-42 point is the detection smoke run
(`baseline_smoke_v000_os4_seed42`): it uses the identical `output_stride 4` config — only the
`run_name` differs from `examples/baseline_bottomup_v000_os4.yaml`, verifiable from the run's logged
config in W&B ([p297iqwv](https://wandb.ai/eberrigan-salk-institute-for-biological-studies/sleap-roots-tier1-baseline/runs/p297iqwv)).
Per-epoch train/val loss is recoverable via `run.scan_history()` for every run (confirmed:
thousands of rows carrying `epoch`), closing the observability gap the legacy TF runs left — the
[W&B project](https://wandb.ai/eberrigan-salk-institute-for-biological-studies/sleap-roots-tier1-baseline)
holds the loss curves.

### TensorFlow reference — context only, not a gate

The legacy TensorFlow `sleap-train` runs (see [tf-reference.md](tf-reference.md)) are shown as a
range, per run-to-run spread, and are **not** a pass/fail bar (`docs/roadmap.md`, "Oracle /
validation philosophy" — exact backend parity is the wrong bar):

| TF reference (`max_stride`) | `dist_avg` (px) | `vis_recall` |
|-----------------------------|-----------------|--------------|
| 16 | 0.989 – 1.710 | 0.47 – 0.63 |
| 32 | 1.383 – 2.078 | 0.83 |

**Read the two columns together — the comparison is recall-confounded.** The PyTorch baseline's
`dist_avg` is ~20–40× the TF `dist_avg`, but its `vis_recall` (0.85–0.91) is **higher than every TF
run** (0.47–0.83): the PyTorch model detects *more* keypoints and localizes them *looser*, whereas
TF localized a smaller, higher-confidence subset very tightly. Because each backend's `dist_*` is
measured over a different population, the raw `dist` ratio overstates the gap — report both
directions, not "20–40× worse." (`max_stride` is the TF sweep axis, **distinct** from the
`output_stride` of the PyTorch configs; `tf-reference.md` warns against conflating them.) TF remains
context only, not a gate.

### Finding: `output_stride 2` is seed-unstable and collapses

The higher-resolution [`output_stride 2`](../examples/baseline_bottomup_v000_os2.yaml) config
(sibling of the os4 baseline) was run across the same 3 seeds:

| seed | `output_stride 2` result (val) |
|------|--------------------------------|
| 42 | partial — **25 / 44 instances detected**; on those, `dist_avg` 29.13 px, `dist_p50` 16.63 px, `vis_recall` 0.58 |
| 43 | **collapsed** — 0 predicted instances, all metrics NaN |
| 44 | **collapsed** — 0 predicted instances, all metrics NaN |

Only 1 of 3 os2 seeds produced numbers, and that one missed ~43% of instances, so os2 has no usable
range and is **not** the baseline — `output_stride 4` is. What the collapse *means* is deliberately
stated cautiously here, because two candidate causes are not yet separated:

- **Mechanism inferred from source, not ablated.** The likely driver is that sleap-nn 0.2.0's
  bottom-up confmap loss is a plain per-pixel `nn.MSELoss()` with no foreground weighting
  (`sleap_nn/training/lightning_modules.py`, read from source): with a tiny foreground fraction the
  loss is minimized by predicting ~0 everywhere → no peaks → no instances (the collapsed os2 runs
  have near-zero `val/confmaps_loss` — the collapse signature). **But** os2 also uses
  `confmaps.sigma 2.5` (half sleap-nn's default) at a finer `output_stride`, shrinking each target to
  roughly sub-cell support — a tighter-target effect that could cause the same collapse independently
  of the loss. A single os2 run at `sigma 5.0` would discriminate the two; it is noted as follow-up
  and raised upstream with sleap-nn. (`online_hard_keypoint_mining` *reweights* the loss toward hard
  keypoints — it does not change target density.)
- **This is not a proven resolution ceiling.** At `output_stride 4` + `scale 0.5` one output cell ≈ 8
  original pixels and peak refinement is sub-cell, so output-stride quantization bounds the error at
  only a few px — far below the observed `dist_p50` 17.7–21.2 px. The heavy tail (`dist_p90`
  67–74 px ≈ 8–9 output cells) points to **detection/association quality and under-fitting on a
  99-frame training set**, not to resolution. Treat 30–38 px as this config's current number, not as
  a lower bound for the backend/dataset.
