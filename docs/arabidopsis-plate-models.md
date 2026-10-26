# Arabidopsis plate models

Two full-plate SLEAP models for arabidopsis, published to the `sleap-roots-models` wandb registry under
the **`candidate`** alias (#3). They are not linked to `production`, so the production pipeline and Bloom
never select them. They are here so they can be tried elsewhere, starting with GraviScan plate sections.

## The models

| | primary | lateral |
|---|---|---|
| Collection | `arabidopsis_plates-primary-230804_133809.multi_instance.n-606` | `arabidopsis_plates-lateral-231130_135922.multi_instance.n-38` |
| Nodes | 8 (`R1`–`R8`) | 3 (`r1`–`r3`) |
| Selector | arabidopsis, plate, 2–7 DAG | arabidopsis, plate, 2–7 DAG |
| Training labels | 545 train / 61 val frames, 2–7 DAG (293 of them at 7) | 34 train / 4 val frames, one 7-DAG imaging session |
| Val dist p50 / p95 | 11.9 / 118.9 px (304 instances) | 1.4 / 17.0 px (45 instances) |
| Val mOKS | 0.41 | 0.42 |
| Trained with | SLEAP 1.3.0, bottom-up | SLEAP 1.3.2, bottom-up |

A collection id is the source model id with `/` and `=` replaced by `-`. The model ids, such as
`arabidopsis_plates/primary/230804_133809.multi_instance.n=606`, use a registry namespace taken from the
models-downloader chooser table. They are not paths on disk.

## Caveats

- **The models were trained on whole plates, not sections.** Both resize every frame to fit 1500×1616 and
  then pad it, so a smaller section image is scaled up and roots look thicker than in training. The
  primary model then runs at 0.5 scale.
- **The lateral model rests on very little:** one session, 38 labelled frames, and 4 validation frames.
- **The metrics above come from each model's own validation split.** They are not comparable across the
  two models, and they are not a parity result against any other model.
- **Age is clamped.** Predict serves a plate older than 7 DAG with these 2–7 cards and logs only a
  warning. A plate younger than 2 DAG gets no model.
- **The two models name their nodes differently** (`R…` vs `r…`). Keep that in mind when combining
  their outputs.

## Fetch a model

You need read access to the `sleap-roots-models` registry.

```python
import wandb

name = (
    "eberrigan-salk-institute-for-biological-studies-org/wandb-registry-sleap-roots-models/"
    "arabidopsis_plates-primary-230804_133809.multi_instance.n-606:candidate"
)
model_dir = wandb.Api().artifact(name).download()  # best_model.h5, training_config.json, ...
```

Each artifact also carries the model's `labels_gt.val.slp`, `labels_pr.val.slp` and `metrics.val.npz`.

## Run sleap-roots-predict on them

Set `SRP_WANDB_MODEL_ALIAS=candidate`, and leave `SRP_WANDB_ENTITY` and `SRP_WANDB_MODEL_REGISTRY` at their
defaults. Each scan needs a sidecar with `species: arabidopsis`, `mode: plate` and its `age`. Bloom does
not dispatch plate scans, so write these sidecars yourself. The `candidate` listing also includes the
wheat and sorghum cards from their earlier candidate window. They never match a plate scan.

## Promotion to production

Not planned yet. The gates (parity, plate support in traits and in Bloom dispatch, and the age-window
mismatch with the traits chooser) are tracked in the promotion issue linked from #3. The mechanics are
in the README, under
[Publishing under a non-default alias](../README.md#publishing-under-a-non-default-alias).
