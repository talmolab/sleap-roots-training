# Config-driven training (Tier 1)

How to train and evaluate one keypoint model from a single config file on the `sleap-nn`
backend. This guide covers **config authoring, validation, and reading results**; for the
one-time backend **install** and the raw `sleap-nn` train/predict mechanics (GPU setup,
sample data, `sleap-nn track`), see [training-backend.md](training-backend.md).

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

- **`trainer_config.seed` is required.** 0.2.0 ships no default seed, and the Tier-1 baseline
  is built from multiple same-config runs — an unseeded spread cannot be told from signal.
- **`data_config.preprocessing` is materialized on emission,** so `sleap-nn train` never hits
  the post-fit `ConfigAttributeError` a config that omits `preprocessing` triggers on 0.2.0.

## 1. Validate

```bash
sleap-roots-training validate examples/arabidopsis_primary_cylinder.yaml
```

This checks the `experiment` metadata (species / mode / root_type vocab), the required integer
seed, and the W&B-enablement pairing. With the `[train]` extra installed it additionally
delegates to `sleap-nn`'s own validation (a backbone and a head must be set); without it, that
deep check is skipped with a note. Exit `0` means the config conforms; a non-zero exit prints
the offending field.

## 2. Train (with built-in eval)

```bash
sleap-nn train --config examples/arabidopsis_primary_cylinder.yaml
```

`sleap-nn train` runs train → inference → eval in one call, writing the checkpoint plus
`labels_pr.*.slp` and `metrics.*.npz` into `<ckpt_dir>/<run_name>`. (Needs the `[train]` extra;
see the runbook.)

## 3. Read the metrics

The eval metrics land in `metrics.val.npz` / `metrics.train.npz` next to the checkpoint:

```python
import numpy as np

m = np.load("models/cyl_arabidopsis_primary/metrics.val.npz", allow_pickle=True)
print(m.files)  # the available metric arrays (localization distance, OKS, PCK, ...)
```

Report the localization error (`dist_avg`, PCK) as the accuracy headline. Do **not** report
`oks_map` as a headline number — it is mis-calibrated for the root domain (see
[tf-reference.md](tf-reference.md)).

## 4. Confirm per-epoch W&B logging

Roadmap Tier 1 requires per-epoch metrics in W&B (the legacy TF runs logged only final
summaries, so `scan_history()` returned zero rows and there was no loss curve). Per-epoch
logging is `sleap-nn` / Lightning's **default** — this repo adds no config field to "enable"
it — so it is verified empirically. Set `trainer_config.use_wandb: true` and fill
`trainer_config.wandb.entity` / `project`, then after a run confirm the curve is recoverable:

```python
import wandb

run = wandb.Api().run("<entity>/<project>/<run_id>")
rows = list(run.scan_history())
assert rows, "no per-epoch history was logged"
print(len(rows), "per-epoch rows")
```

## PyTorch baseline

> **Reserved** — the PyTorch baseline numbers are established by the follow-up baseline PR
> (roadmap Tier 1). Until then, the legacy TensorFlow reference in
> [tf-reference.md](tf-reference.md) is shown **for context only**, as a range — same-config
> seed/replicate spread is real, so it is not a single point, and exact parity with the old
> TensorFlow backend is **not** the bar.

The baseline is 2–3 **same-config** seeded runs on held-out data; that baseline — not the TF
number — becomes the reference later tiers reproduce-or-beat.
