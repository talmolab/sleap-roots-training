# Arabidopsis plate models

Two full-plate SLEAP models for arabidopsis, published to the `sleap-roots-models` wandb registry
under the **`candidate`** alias on 2026-10-28 (#3). They are not linked to `production`, so the
production pipeline and Bloom never select them. They are here so they can be tried elsewhere, starting
with GraviScan plates.

| Collection | Version | Digest |
|---|---|---|
| `arabidopsis_plates-primary-230804_133809.multi_instance.n-606` | v0 | `fd461dffcb9b8e71e5882e3cc3f2c157` |
| `arabidopsis_plates-lateral-231130_135922.multi_instance.n-38` | v0 | `fefe41995d7480375e2de55300707aeb` |

Before publishing, both were loaded and run through sleap-roots-predict (sleap-nn 0.3.0) on one
validation image each, to check that they load and predict. The primary predicted 8 roots on a frame
with 5 labelled roots; its own TensorFlow prediction at training time had 7 there. The lateral predicted
8 where 8 are labelled, but that image is also one of its training images, so this says nothing about
accuracy. The publish record, with every archived file's SHA256, is
[docs/migration/2026-10-28-arabidopsis-plate-candidate-publish-record.json](migration/2026-10-28-arabidopsis-plate-candidate-publish-record.json).

## The models

| | primary | lateral |
|---|---|---|
| Collection | `arabidopsis_plates-primary-230804_133809.multi_instance.n-606` | `arabidopsis_plates-lateral-231130_135922.multi_instance.n-38` |
| Nodes | 8, a linear chain `R1` (base) → `R8` (tip) | 3, a linear chain `r1` (base) → `r3` (tip) |
| Selector | arabidopsis, plate, 2–7 DAG | arabidopsis, plate, 2–7 DAG |
| Training labels | 545 train / 61 val frames; 166 train and 23 val frames are from an IAA-treated set | 34 train / 4 val frames, all imaged on one day (2023-09-08) |
| Validation split | a random 10% of frames; **3 of the 61 val images are also train images** (labelled again in a second copy) | a random 10% of frames; **2 of the 4 val images are also train images** (labelled again in a second copy) |
| Ages labelled | 2–7 DAG, read from the day prefix of each image filename (the owner counts these as DAG, including the IAA set's days from transplanting); 293 of the 545 train frames are at 7; six train frames named `day4` are day 3 by folder and date | 7 DAG (owner); the `day1` in the frame names is not read as the age |
| Input | resized and padded to 1500 × 1616 (height × width), then scaled by 0.5 | resized and padded to 1500 × 1616 (height × width), scale 1.0 |
| Val roots: labelled / paired / predicted | 305 / 304 / 426 | 52 / 45 / 52 |
| Val dist p50 / p95, paired roots only | 11.9 / 118.9 px | 1.4 / 17.0 px |
| Val mOKS, paired roots only | 0.41 | 0.42 |
| Val OKS mAP / mAR | 0.04 / 0.11 | 0.07 / 0.18 |
| Trained with | SLEAP 1.3.0 (TensorFlow), bottom-up | SLEAP 1.3.2 (TensorFlow), bottom-up |

The validation numbers are read from each model's own `metrics.val.npz` and validation labels, which
SLEAP 1.3 (TensorFlow) wrote at training time. Distances are in image pixels; the labelled plate images
are 1500 × 1616 pixels (height × width), as recorded in the labels. They have not been reproduced under
sleap-nn, which is what predict runs these weights with.

- **These are not held-out results.** The split is a random sample of frames, not of plates or days,
  and some validation images are training images labelled a second time in another copy of the
  project: 3 of the primary's 61, and 2 of the lateral's 4. The numbers describe images the models
  have seen or nearly seen, not new plates.
- **"Paired" is not "found".** SLEAP's evaluation pairs predictions with labelled roots, and a pair can
  be a poor match; the distances and mOKS say how close the pairs are, and cover paired roots only. A
  labelled root with no pair never enters them, and neither does an extra prediction. The primary
  predicted 426 roots on frames with 305 labelled ones, so roughly 120 of its predictions pair with no
  labelled root (extra or split roots). The lateral left 7 of its 52 labelled roots and 7 of its 52
  predictions unpaired. The OKS mAP and mAR count both kinds of error, and both are low.
- **Base first.** The owner confirms that the first node is the base in both models: the primary's
  `R1` and the lateral's `r1`. The labels agree: in all 304 of the primary's validation roots with
  both ends labelled, `R1` lies above `R8`, by at least 179 px; in all 51 such lateral roots, `r1`
  lies above `r3`, though laterals run sideways (a median drop of 35 px, and as little as 0.3 px).

A collection id is the source model id with `/` and `=` replaced by `-`. The model ids, such as
`arabidopsis_plates/primary/230804_133809.multi_instance.n=606`, use a registry namespace taken from the
models-downloader chooser table. They are not paths on disk.

## Caveats

- **What matters is what the image shows, not its resolution.** Both models were trained on
  whole-plate images of 1500 × 1616 pixels (height × width). At prediction, both scale every input
  up or down to fit that size, keeping its aspect ratio, and pad the rest with black at the bottom
  and right; sleap-nn logs a one-time warning when it does. A whole plate framed like the training
  plates therefore comes out at the training scale, whatever its resolution. An image showing less
  than a whole plate, such as a cropped section, is scaled up, so its roots look thicker than in
  training, and an image of a different shape gets black padding the models never saw in training.
  Either may hurt accuracy. The primary model then runs at 0.5 scale; the lateral at full scale.
- **The lateral model rests on very little:** one day of imaging at 7 DAG, 38 labelled frames,
  and 4 validation frames, two of which it was trained on. Its 1.4 px median mostly measures images it
  has seen; it is not an estimate of performance on other plates, and it is served across the whole
  2–7 window.
- **The primary's training data mixes treatments.** About a third of its frames (166 of 545 train, 23 of
  61 val) come from an IAA-treated set (IAA is an auxin, which alters root growth). The metrics above
  are not separated by treatment. That set counts days from transplanting, which the owner says is
  usually the day of germination, so its ages are taken as DAG.
- **The metrics above come from each model's own validation split.** They are not comparable across the
  two models, and they are not a parity result against any other model. The primary's p95 is ten times
  its median: a minority of its points are far off. The pooled numbers also say little about ages 2–6,
  since just over half of the primary's train frames (293 of 545) are at 7, and all the lateral's are.
- **Age is clamped.** Predict serves a plate older than 7 DAG with these 2–7 cards and logs only a
  warning, although neither model was labelled at an age above 7. A plate younger than 2 DAG gets
  no model. The lateral, trained only on images from a single 7 DAG imaging day, is served across
  the whole window. The traits plate window is 7–14 today; the owner has decided it changes to 2–7
  to match these cards (talmolab/sleap-roots#281).
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
mismatch with the traits chooser) are tracked in #84. The mechanics are
in the README, under
[Publishing under a non-default alias](../README.md#publishing-under-a-non-default-alias).
