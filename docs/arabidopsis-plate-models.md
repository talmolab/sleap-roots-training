# Arabidopsis plate models

Two full-plate SLEAP models for arabidopsis, to be published to the `sleap-roots-models` wandb registry
under the **`candidate`** alias (#3) once this change merges. This page is updated with each
artifact's version and digest when they are. They are never linked to `production`, so the production
pipeline and Bloom never select them. They are here so they can be tried elsewhere, starting with
GraviScan plate sections.

## The models

| | primary | lateral |
|---|---|---|
| Collection | `arabidopsis_plates-primary-230804_133809.multi_instance.n-606` | `arabidopsis_plates-lateral-231130_135922.multi_instance.n-38` |
| Nodes | 8, a linear chain `R1` (base) → `R8` (tip) | 3, a linear chain `r1` (base) → `r3` (tip) |
| Selector | arabidopsis, plate, 2–7 DAG | arabidopsis, plate, 2–7 DAG |
| Training labels | 545 train / 61 val frames | 34 train / 4 val frames, all from one imaging session (2023-09-08) |
| Validation split | a random 10% of frames, not held out by plate or session | a random 10% of frames, from the same session |
| Ages labelled | 2–7 DAG, inferred from the day prefix of each image filename; 293 of the 545 train frames are at 7 | **unconfirmed**: 7 DAG is inferred from the folder and prediction names, but the frame names say `day1` |
| Input | resized and padded to 1500×1616, then scaled by 0.5 | resized and padded to 1500×1616, scale 1.0 |
| Val roots: labelled / matched / predicted | 305 / 304 / 426 | 52 / 45 / 52 |
| Val dist p50 / p95, matched roots only | 11.9 / 118.9 px | 1.4 / 17.0 px |
| Val mOKS, matched roots only | 0.41 | 0.42 |
| Val OKS mAP / mAR | 0.04 / 0.11 | 0.07 / 0.18 |
| Trained with | SLEAP 1.3.0 (TensorFlow), bottom-up | SLEAP 1.3.2 (TensorFlow), bottom-up |

The validation numbers are read from each model's own `metrics.val.npz` and validation labels, which
SLEAP 1.3 (TensorFlow) wrote at training time. Distances are in image pixels; the labelled plate images
are 1616 × 1500 pixels (width × height). They have not been reproduced under sleap-nn, which is what
predict runs these weights with.

- **The distances and mOKS cover matched roots only.** A labelled root the model missed never enters
  them. The primary matched 304 of its 305 labelled validation roots but predicted 426 roots on those
  61 frames, so roughly 120 of its predictions match no labelled root (extra or split roots). The
  lateral missed 7 of 52. The OKS mAP and mAR count both kinds of error, and both are low.
- **The split is by frame, not by plate.** Nearby days of one plate can sit on both sides of it, so
  these numbers describe images like the training images, not new plates.
- **Base first.** The owner confirms `R1` is the base. In every validation root with both ends labelled
  (304 primary, 51 lateral), the first node lies above the last in the image, as a base does.

A collection id is the source model id with `/` and `=` replaced by `-`. The model ids, such as
`arabidopsis_plates/primary/230804_133809.multi_instance.n=606`, use a registry namespace taken from the
models-downloader chooser table. They are not paths on disk.

## Caveats

- **The models were trained on whole plates, not sections.** Both resize every frame to fit 1500×1616 and
  then pad it, so a smaller section image is scaled up and roots look thicker than in training. The
  primary model then runs at 0.5 scale; the lateral at full scale.
- **The lateral model rests on very little:** one session of unconfirmed age, 38 labelled frames, and 4
  validation frames. Its 1.4 px median is not an estimate of performance on other plates, and it is
  served across the whole 2–7 window.
- **The metrics above come from each model's own validation split.** They are not comparable across the
  two models, and they are not a parity result against any other model. The primary's p95 is ten times
  its median: a minority of its points are far off. The pooled numbers also say little about ages 2–6,
  since most of its labels are at 7.
- **Age is clamped.** Predict serves a plate older than 7 DAG with these 2–7 cards and logs only a
  warning, although neither model saw a plate older than 7. Sections at 8–14 DAG (the traits window)
  would all be scored that way. A plate younger than 2 DAG gets no model. The lateral, whose labels may
  be from day 1, is served across the whole window.
- **The window is not the old chooser table's.** The models-downloader table listed an arabidopsis plate
  row at 7–14 under the same `arabidopsis_plates/` namespace. These two runs were chosen from the
  owner's own training directories; no lineage to whatever that table once served is claimed.
- **Node names differ.** The primary emits `R1`–`R8` (upper case), unlike the lateral (`r1`–`r3`) and
  the published plate label collection (`r1`–`r8`). Match node names case-insensitively before merging
  its predictions with labels; the order is the same, base first.

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
