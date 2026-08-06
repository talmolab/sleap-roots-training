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
`.npz` names may differ (inspect `m.files`). **Those TF W&B values are in millimeters**, written by
a lab post-processing step rather than by SLEAP — use the pixel-space table in
[tf-reference.md](tf-reference.md) for any comparison against these numbers. Do **not** report
`oks_map` as a headline number —
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
`r1..r6`). `clean_pkg.py` writes a `.sha256` sidecar next to each cleaned file (a content fingerprint captured at clean time); wiring that hash into an automated reproducibility check is still deferred to #10/#11.

**Metrics.** Read from each run's `metrics.val.0.npz` with
[`scripts/dump_val_metrics.py`](../scripts/dump_val_metrics.py): `distance_metrics.avg` →
`dist_avg`, `.p50` → `dist_p50`, `visibility_metrics.recall` → `vis_recall` (the dumper prefixes
these with the top-level `metrics.` key). Distances are in **original-image pixels** — predictions
are rescaled from the `scale: 0.5` input back to the source 1088×2048 coordinates before matching
the original-coordinate ground truth, so they are directly comparable to the TF reference's
**pixel-space** metrics (the ones SLEAP itself wrote; the TF W&B summary values are millimeters,
see [tf-reference.md](tf-reference.md)). (Verified in sleap-nn 0.2.0 source: `sleap_nn/inference/{single_instance,topdown,bottomup}.py`
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

> **Correction (2026-08-06): the "PyTorch is 20–40× worse than TF" claim was wrong, and it was a
> unit error.** The TF `dist_*` numbers previously quoted here (0.989–2.078) are **millimeters**,
> emitted by a lab post-processing step, not SLEAP's pixel metrics. SLEAP's own `metrics.val.npz`
> for those runs reports **pixels**, and in pixels the two backends are comparable. Details,
> evidence and the full per-run pixel table are in [tf-reference.md](tf-reference.md).
>
> A second finding fell out of the same check: scoring a TF run's saved predictions with
> **sleap-nn's** `Evaluator` reproduces SLEAP's own `metrics.val.npz` on all 11 metrics to every
> printed digit. The two backends' evaluators are numerically identical, and their inference
> parameters match as well (`peak_threshold` 0.2, integral refinement at patch size 5, identical
> PAF grouping constants). There is no measurement discrepancy between the backends.

| TF reference (`max_stride`) | `dist_avg` (px) | `dist_p50` (px) | `vis_recall` | instances matched |
|-----------------------------|-----------------|-----------------|--------------|-------------------|
| 8 | collapsed (0 predictions) | — | — | 0 / 44 |
| 16 | 23.72 – 39.00 | 8.21 – 8.42 | 0.50 – 0.56 | 36–40 / 44 |
| 32 | 29.85 – 30.23 | 8.61 – 9.49 | 0.78 – 0.81 | 42–43 / 44 |
| 64 | 21.65 – 21.93 | 6.87 – 8.95 | 0.87 | 42–43 / 44 |

**Read in matching units, the PyTorch baseline is competitive and wins on detection.** Its
`dist_avg` (30.1–37.8) sits inside the TF range (21.7–39.0), and its `vis_recall` (0.85–0.91 at
**44 / 44** instances detected) is **above every TF run**, the best of which reaches 0.872 on
43 / 44. The remaining honest gap is the median: TF localizes its matched keypoints tighter
(`dist_p50` 6.9–9.5) than the os4 baseline (17.7–21.2). That gap is a resolution/target-scale
effect rather than a backend one — this repo's own full-resolution `output_stride 2` runs reach
`dist_p50` 5.7–12.2, inside TF's range, but at much lower recall (0.38–0.65). So the two backends
trade off along the same curve; os4 simply sits at the high-recall end of it.

(`max_stride` is the TF sweep axis, **distinct** from the `output_stride` of the PyTorch configs, so
the two should not be conflated.) TF remains context only, not a gate.

### Finding: the `output_stride 2` collapse is a training-schedule (step-count) artifact, not the loss

The finer [`output_stride 2`](../examples/baseline_bottomup_v000_os2.yaml) config is seed-unstable at
`confmaps.sigma 2.5`. A controlled ablation (same config, same 3 seeds, **only `sigma`
changed**, [`..._os2_sigma5.yaml`](../examples/baseline_bottomup_v000_os2_sigma5.yaml)) shows the
`sigma` sensitivity:

| os2 config | seed 42 | seed 43 | seed 44 | stable? | `val/confmaps_loss` |
|------------|---------|---------|---------|:-------:|---------------------|
| **σ = 2.5** | partial: 25 / 44, recall 0.58 | **collapsed** (0, NaN) | **collapsed** (0, NaN) | ✗ | ~0.0015 (near-zero) |
| **σ = 5.0** | 43 / 44, recall 0.87 | 44 / 44, recall 0.88 | 43 / 44, recall 0.80 | ✓ | ~0.0047 (healthy) |

Runs (W&B, seeds 42 / 43 / 44): σ=2.5 [dzqfyllx](https://wandb.ai/eberrigan-salk-institute-for-biological-studies/sleap-roots-tier1-baseline/runs/dzqfyllx) / [0lx0mtlj](https://wandb.ai/eberrigan-salk-institute-for-biological-studies/sleap-roots-tier1-baseline/runs/0lx0mtlj) / [gm03okhs](https://wandb.ai/eberrigan-salk-institute-for-biological-studies/sleap-roots-tier1-baseline/runs/gm03okhs); σ=5.0 [35bxsc7a](https://wandb.ai/eberrigan-salk-institute-for-biological-studies/sleap-roots-tier1-baseline/runs/35bxsc7a) / [8zjnjpnz](https://wandb.ai/eberrigan-salk-institute-for-biological-studies/sleap-roots-tier1-baseline/runs/8zjnjpnz) / [nabcm8o4](https://wandb.ai/eberrigan-salk-institute-for-biological-studies/sleap-roots-tier1-baseline/runs/nabcm8o4).

With σ=5.0 (sleap-nn's default sigma) `output_stride 2` trains on **every** seed and detects ~all
instances; with σ=2.5 two of three seeds collapse. **The cause is too few gradient steps per epoch,
not the loss**, confirmed by a schedule-matched control. Our configs set `min_train_steps_per_epoch:
25` (one pass over the 99-frame train set), which is **8× below sleap-nn's own default of 200**
(`sleap_nn/config/trainer_config.py`; `train_steps_per_epoch` then resolves to the max of that and
the data size). At the settings that collapse (full resolution, `output_stride 2`, `sigma 2.5`, TF
architecture), all 3 seeds collapse at 25 steps/epoch; raising to 200 (sleap-nn's default, and TF's
`batches_per_epoch`, [`examples/tf_parity_v000_os2_schedmatched.yaml`](../examples/tf_parity_v000_os2_schedmatched.yaml))
trains all 3 instead (train `dist_avg` 6.3–9.7 px, `dist_p50` 2.6–4.2 px; val `dist_p50` 5.7–7.8 px,
at low recall 0.38–0.63). Both sleap-nn and legacy TF use the same unweighted `nn.MSELoss()`
(confirmed by Divya), so the loss formula is not the differentiator; the collapse was our config
under-setting the step count below sleap-nn's default of 200, which the default (or converting the TF
config, which carries `batches_per_epoch` into `min_train_steps_per_epoch`) would have avoided. `sigma 5.0` is thus one escape route (coarser targets give
a stronger gradient toward peaks) and more steps is another. **`val/confmaps_loss` is not a reliable
collapse signal:** the healthy schedule-matched runs sit at ~6e-5, at or below the collapsed runs,
because on sparse targets both an all-background and a sharp-peak prediction have tiny MSE; the
reliable signal is 0 matched instances / all-NaN. A foreground-weighted loss (sleap-nn#718) would
still help convergence and robustness, but it is an enhancement, not the fix for this collapse.
`online_hard_keypoint_mining` reweights the loss toward hard keypoints; it does not change target
density.

**os2 σ=5.0 is still not the baseline.** Its val range — `dist_avg` **31.7–36.5 px**, `dist_p50`
**18.2–23.1 px**, `vis_recall` **0.80–0.88** — is on par with or marginally worse than os4
(30.1–37.8 / 17.7–21.2 / 0.85–0.91): the higher output resolution buys **no** localization gain. That
is consistent with the arithmetic — at os4 one output cell ≈ 8 original px with sub-cell refinement,
so quantization bounds the error at only a few px, far below the observed `dist_p50` ~18–21 px and
the `dist_p90` 67–74 px tail. The error is **detection/association quality + under-fitting on a
99-frame training set**, not resolution — treat 30–38 px as this dataset/backbone's current number,
not a lower bound. `output_stride 4` remains the reported Tier 1 baseline.

> **Update (issue #36, aligned re-run done):** the "under-fitting" was real on the training set but
> does not explain the val gap. The reported os4 runs used `min_train_steps_per_epoch: 25` (one pass
> over 99 frames) vs TF's ~8× oversampling (so ~250 vs ~2000 gradient steps of early-stopping
> patience), and inherited sleap-nn's default geometric augmentation rather than TF's flip-only.
> [`examples/baseline_bottomup_v000_os4_aligned.yaml`](../examples/baseline_bottomup_v000_os4_aligned.yaml)
> fixes both. Re-running all 3 seeds, **train** error dropped sharply (seed44 train `dist_avg` 6.76 px,
> seed43 11.53) confirming the short schedule really was under-fitting, but **val** barely moved
> (aligned val `dist_avg` 28.2–32.6, `dist_p50` 14.7–16.6, `vis_recall` 0.89–0.95, vs reported
> 30.1–37.8 / 17.7–21.2 / 0.85–0.91: within noise on the mean, marginally better on the median). With
> train at ~6–12 px and val at ~28–33 px, the val gap is **small-data overfitting on 99 frames, not a
> fixable schedule artifact** (and augmentation-off to match TF likely cost some generalization). os4
> stays the reported baseline; the aligned config trains better but is not a better baseline on val.

### Hyperparameter parity vs the TF reference (issue #36)

The Tier 1 baseline is meant to be analogous to the legacy TF models, so every hyperparameter is
tracked against `tests/fixtures/tf_reference/nxe8xgsd.config.json`. "reported" is the merged os4
baseline; "aligned" is [`..._os4_aligned.yaml`](../examples/baseline_bottomup_v000_os4_aligned.yaml).

| hyperparameter | TF | os4 (reported) | os4 aligned | status |
|---|---|---|---|---|
| optimizer / lr | Adam / 1e-4 | Adam / 1e-4 | same | match |
| LR-plateau (factor/patience/cooldown/threshold/min_lr) | 0.5 / 5 / 3 / 1e-6 / 1e-8 | same | same | match |
| batch size | 4 | 4 | 4 | match |
| max_epochs | 200 | 200 | 200 | match |
| hard-mining (ratio / loss_scale / min,max) | 2 / 5 / 2,null | same | same | match |
| confmap sigma / PAF sigma·stride | 2.5 / 75·8 | same | same | match |
| confmap `output_stride` | 2 | 4 | 4 | deliberate (collapse-escape, documented) |
| input `scale` | 1.0 | 0.5 | 0.5 | deliberate (collapse-escape, documented) |
| `online_mining` | false | true | true | deliberate (collapse-escape, documented) |
| augmentation | flip only | sleap-nn default (rot ±15, scale 0.9–1.1) | **off** | #36: unintentional → aligned |
| `min_train_steps_per_epoch` | 200 | 25 | **200** | #36: unintentional → aligned |
| `early_stopping.min_delta` | 1e-6 | 1e-8 | **1e-6** | #36: unintentional → aligned |
| backbone `filters` / `filters_rate` | 24 / 1.5 | 16 / 2.0 | 16 / 2.0 | #36 item 4: divergent, decision pending |
| backbone `max_stride` | 16 | 32 | 32 | deliberate (deep backbone; revisit) |

The three "aligned" rows are the unintentional drift #36 flagged; the aligned config fixes them. The
re-run is now done (see the caveat above): fixing the schedule improved training substantially but the
val gap did not close, so this drift was not the cause of the reported accuracy. Backbone width and
`max_stride` are left as documented divergences for a joint decision (tracked in #36).
