# sleap-nn training backend runbook

Tier 0.5 (#9) verification runbook: the exact, reproducible commands to install the
`sleap-nn` keypoint backend, train and predict on a small sample dataset, and check the
GPU. It de-risks Tier 1 by proving the released backend works end to end before any
config-driven training is built on it. For the config-driven train/eval workflow built on top of
this backend (authoring a config, `validate`, reading results), see [training.md](training.md).

The backend ships as an optional extra so the base install and CI stay lean:

- Phase-1 pins (in `pyproject.toml`): `sleap-nn>=0.2.0,<0.3.0`, `sleap-io>=0.7.1,<0.8.0`,
  `torch>=2.5.0`. Capped below the v0.3.0 / sleap-io 0.8.0 mask line (Phase 2); raise at
  the Tier 6 mask re-verify.
- The end-user install target is `sleap-roots-training[train]` (works once the package is
  published); from a source checkout, install the extra from the working tree (below).

> **Status: verified end-to-end on the RTX A5000 (2026-07-21).** Install, GPU/arch check, and a
> keypoint train → predict → evaluate run on the BermanFlies sample all completed on `sleap-nn`
> 0.2.0. Two 0.2.0-specific gotchas are documented inline (the input config must include
> `data_config.preprocessing`, and checkpoint inference is `sleap-nn track` — `sleap-nn predict` is
> the ONNX-export path); see "sleap-nn 0.2.0 caveats".

## 1. Install the training backend

`sleap-nn` pulls `torch`; CUDA support is selected **at install time** on the GPU box (it is
**not** baked into `uv.lock`, so the committed lock governs only CI's lean resolution, not
the box's exact torch build).

### Target GPU box — NVIDIA RTX A5000, native Windows (PowerShell)

The A5000 is Ampere, compute capability **`sm_86`**. The installed driver (`nvidia-smi`:
552.22) supports **CUDA 12.4**, so let uv match the driver:

```powershell
# from the repo checkout
uv venv --python 3.11
uv pip install ".[train]" --torch-backend=auto
```

`--torch-backend` requires the `uv pip` interface (not `uv sync`). **Verified on the box
(2026-07-21):** `--torch-backend=auto` installed a **CUDA 12.9** torch build
(`torch==2.8.0+cu129`, `torchvision==0.23.0+cu129`) that runs fine on the **12.4** driver via
CUDA minor-version forward-compatibility — no driver update was needed, and
`torch.cuda.is_available()` is `True` on the A5000. If `auto` ever picks a build your driver
can't run, pin an older CUDA line explicitly, e.g. `--torch-backend=cu124` (matches the 12.4
driver) or `cu126`.

Plain-pip fallback (no uv):

```powershell
pip install ".[train]" --extra-index-url https://download.pytorch.org/whl/cu124
```

### Dev machine (macOS / no CUDA)

```bash
uv pip install ".[train]"   # resolves the CPU/MPS torch build
```

## 2. Check the GPU

```python
import torch

print(torch.__version__, torch.version.cuda)
print(torch.cuda.get_arch_list())        # does it include sm_86 (Ampere)?
print(torch.cuda.get_device_capability())
print(torch.cuda.is_available(), torch.cuda.get_device_name(0))
```

The packaged smoke test asserts the same and records the arch list:

```bash
uv run pytest -m integration tests/test_gpu.py -s
```

## 3. Train a keypoint model

Fetch a small labeled sample — the SLEAP BermanFlies sample (single-instance keypoints); the
point is that the path works, not that the model is good:

```powershell
curl.exe -L -o train.pkg.slp https://storage.googleapis.com/sleap-data/datasets/BermanFlies/random_split1/train.pkg.slp
curl.exe -L -o val.pkg.slp   https://storage.googleapis.com/sleap-data/datasets/BermanFlies/random_split1/val.pkg.slp
```

Write this `config.yaml` (tiny run — a couple of epochs is enough to prove the path). The
`data_config.preprocessing` block is **required on 0.2.0** — see the caveats below:

```yaml
data_config:
  train_labels_path:
    - train.pkg.slp
  val_labels_path:
    - val.pkg.slp
  preprocessing:
    ensure_rgb: false
    ensure_grayscale: false
    max_height: 192
    max_width: 192
    scale: 1.0
    crop_size: null
    min_crop_size: 100
    crop_padding: null
model_config:
  backbone_config:
    unet:
      filters: 32
      max_stride: 16
  head_configs:
    single_instance:
      confmaps:
        sigma: 5.0
trainer_config:
  max_epochs: 2
  save_ckpt: true
  ckpt_dir: models
  run_name: my_first_model
```

Train:

```bash
uv run sleap-nn train --config config.yaml
```

The trained model lands in `models/my_first_model/` (0.2.0 auto-suffixes to `-1`, `-2`, … if the
run name already exists). Training also runs built-in inference + evaluation at the end, writing
`labels_pr.train.0.slp` / `labels_pr.val.0.slp` and `metrics.*.npz` into the model dir — so a
single `train` call already exercises train → predict → evaluate. Verified run on the A5000
(BermanFlies, 2 epochs, ~49 s): val **mOKS 0.186**, avg dist **4.15 px**, p50 **2.92 px**,
PCK@5px **0.189** (rough by design — a 2-epoch smoke run; quality is not the Tier 0.5 bar).

> **Reproducibility note (matters for Tier 1).** sleap-nn 0.2.0 has **no default random seed**
> (`trainer_config.seed` is unset; the `seed: 42` default arrives in 0.3.0), so this smoke run is
> unseeded — fine here (parity/quality is not the Tier 0.5 bar), but **Tier 1 baseline configs must
> set `trainer_config.seed` explicitly**. The Tier 1 oracle is built from multiple runs, and an
> unseeded spread can't be told apart from real signal; every later tier grades against that
> baseline, so the seed has to be pinned before it is established.

## 4. Predict on new data with the trained model

Standalone inference on 0.2.0 is **`sleap-nn track`** (`sleap-nn predict` is the ONNX-export
predictor on 0.2.0; the unified `sleap-nn predict` arrives in 0.3.0):

```bash
uv run sleap-nn track --data_path val.pkg.slp --model_paths models/my_first_model/ --output_path val.predictions.slp
```

Confirm `val.predictions.slp` is written with predicted instances. Useful options: `--device`
(default `auto`), `--peak_threshold` (default `0.2`), `--batch_size` (default `4`), and
`--model_paths` may be repeated to run a top-down centroid + centered-instance pair.

## GPU / CUDA arch findings

Recorded on the target RTX A5000 (native Windows, driver 552.22 / CUDA 12.4) on 2026-07-21:

- **`torch` / bundled CUDA:** `torch 2.8.0+cu129` (CUDA 12.9 runtime)
- **`torch.cuda.get_arch_list()`:** `['sm_70', 'sm_75', 'sm_80', 'sm_86', 'sm_90', 'sm_100', 'sm_120']`
- **`torch.cuda.get_device_capability()`:** `(8, 6)` → `sm_86`
- **`torch.cuda.is_available()`:** `True` (`NVIDIA RTX A5000`)
- **Native SASS vs PTX-JIT (inference):** `sm_86` appears in the build's arch list, which strongly
  indicates the A5000 runs precompiled native SASS with no PTX-JIT fallback. This is an inference
  from `get_arch_list()` (arch presence), not a direct cubin/fatbin measurement. (The build also
  ships `sm_100`/`sm_120`, so it would cover Blackwell / RTX 50-series hardware too.)

The `cu129` (CUDA 12.9) build runs on the 12.4 driver via CUDA minor-version
forward-compatibility, so no driver update was needed. `uv run pytest -m integration
tests/test_gpu.py` passes on this box.

## sleap-nn 0.2.0 caveats (found during this verification)

- **The input config must include `data_config.preprocessing`.** `run_training` reads
  `config.data_config.preprocessing.ensure_rgb` (and `.ensure_grayscale`) directly off the
  user-supplied config after the fit loop, and does not backfill that default there. A config
  without it trains successfully but then crashes with
  `omegaconf.errors.ConfigAttributeError: Key 'preprocessing' is not in struct`. Including the
  `preprocessing` block (as above) avoids it. *Report upstream to the SLEAP team.*
- **Checkpoint inference is `sleap-nn track`, not `sleap-nn predict`.** On 0.2.0, `sleap-nn predict`
  is the ONNX-export predictor (`predict [OPTIONS] EXPORT_DIR VIDEO_PATH`). The unified
  `sleap-nn predict --data_path … --model_paths … -o …` documented on nn.sleap.ai is a **0.3.0**
  feature. On the pinned 0.2.0 use `sleap-nn track` (same `--data_path` / `--model_paths` /
  `--output_path` options).
- **CUDA:** `--torch-backend=auto` installed a CUDA 12.9 torch build that runs on the 12.4 driver
  via forward-compatibility (no driver update needed); see "GPU / CUDA arch findings".

## Notes

- **Parity is not the bar.** Per `docs/roadmap.md` ("Oracle / validation philosophy"), this
  run establishes that the PyTorch/`sleap-nn` path works; exact numeric parity with the
  legacy TensorFlow backend is explicitly not required.
- **Legacy stack caveat.** The legacy SLEAP 1.4.1a2 / TensorFlow 2.7 stack has no `sm_120`
  (Blackwell) support and is not used here; `sleap-nn` is torch-based. This is expected and
  not a blocker for this repo.
