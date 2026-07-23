# Config-driven training (Tier 1)

How to train and evaluate one keypoint model from a single config file on the `sleap-nn`
backend. This guide covers **config authoring, validation, emitting the sleap-nn config, and
reading results**; for the one-time backend **install** and the raw `sleap-nn` train/predict
mechanics (GPU setup, sample data, `sleap-nn track`), see
[training-backend.md](training-backend.md).

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

The eval metrics land in `metrics.val.npz` / `metrics.train.npz` next to the checkpoint:

```python
import numpy as np

m = np.load("models/cyl_arabidopsis_primary/metrics.val.npz", allow_pickle=True)
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
assert rows, "no per-epoch history was logged"
# Substantiate "per-epoch", not merely "some history": one row per epoch, carrying the losses.
epochs = [r for r in rows if "epoch" in r]
assert epochs, "history has no per-epoch rows"
assert any("train_loss" in r or "val_loss" in r for r in rows), "no per-epoch loss logged"
print(len(epochs), "per-epoch rows; last epoch:", epochs[-1].get("epoch"))
```

## PyTorch baseline

> **Reserved** — the PyTorch baseline numbers are established by the follow-up baseline PR
> (roadmap Tier 1). Until then, the legacy TensorFlow reference in
> [tf-reference.md](tf-reference.md) is shown **for context only**, as a range — same-config
> seed/replicate spread is real, so it is not a single point, and exact parity with the old
> TensorFlow backend is **not** the bar.

The baseline is 2–3 runs with the **same config but a different `trainer_config.seed` each run**
(so the range reflects real seed spread, not a fixed-seed point); that baseline — not the TF
number — becomes the reference later tiers reproduce-or-beat.
