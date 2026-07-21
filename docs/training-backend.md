# sleap-nn training backend runbook

Tier 0.5 (#9) verification runbook: the exact, reproducible commands to install the
`sleap-nn` keypoint backend, train and predict on a small sample dataset, and check the
GPU. It de-risks Tier 1 by proving the released backend works end to end before any
config-driven training is built on it.

The backend ships as an optional extra so the base install and CI stay lean:

- Phase-1 pins (in `pyproject.toml`): `sleap-nn>=0.2.0,<0.3.0`, `sleap-io>=0.7.1,<0.8.0`,
  `torch>=2.5.0`. Capped below the v0.3.0 / sleap-io 0.8.0 mask line (Phase 2); raise at
  the Tier 6 mask re-verify.
- The end-user install target is `sleap-roots-training[train]` (works once the package is
  published); from a source checkout, install the extra from the working tree (below).

> **Status:** install + GPU/arch findings are **verified on the RTX A5000** (see "GPU / CUDA
> arch findings"). The train/predict commands below reflect the documented `sleap-nn` CLI and are
> **pending end-to-end verification on the pinned 0.2.0** — `sleap-nn` **0.3.0** introduced the
> unified `sleap-nn predict` CLI, so on 0.2.0 the prediction entrypoint may differ; the exact
> verified commands get recorded here once the sample run completes.

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

Write a minimal `config.yaml` (tiny run — a couple of epochs is enough to prove the path):

```yaml
data_config:
  train_labels_path:
    - train.pkg.slp
  val_labels_path:
    - val.pkg.slp
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

(This config/sample follows the sleap-nn quickstart, which documents the 0.3.0 CLI; if the
0.2.0 config schema differs, run `uv run sleap-nn train --help` and adjust — the exact working
config used gets recorded here after the run.)

## 4. Predict with the trained model

```bash
uv run sleap-nn predict --data_path val.pkg.slp --model_paths models/<run_name>/ -o val.predictions.slp
```

Confirm `val.predictions.slp` is written with predicted instances.

## GPU / CUDA arch findings

Recorded on the target RTX A5000 (native Windows, driver 552.22 / CUDA 12.4) on 2026-07-21:

- **`torch` / bundled CUDA:** `torch 2.8.0+cu129` (CUDA 12.9 runtime)
- **`torch.cuda.get_arch_list()`:** `['sm_70', 'sm_75', 'sm_80', 'sm_86', 'sm_90', 'sm_100', 'sm_120']`
- **`torch.cuda.get_device_capability()`:** `(8, 6)` → `sm_86`
- **`torch.cuda.is_available()`:** `True` (`NVIDIA RTX A5000`)
- **Native vs JIT:** `sm_86` is present in the arch list, so the A5000 runs **native precompiled
  SASS kernels — no PTX-JIT fallback**. (The build also ships `sm_100`/`sm_120`, so it would cover
  Blackwell / RTX 50-series hardware too.)

The `cu129` (CUDA 12.9) build runs on the 12.4 driver via CUDA minor-version
forward-compatibility, so no driver update was needed. `uv run pytest -m integration
tests/test_gpu.py` passes on this box.

## Notes

- **Parity is not the bar.** Per `docs/roadmap.md` ("Oracle / validation philosophy"), this
  run establishes that the PyTorch/`sleap-nn` path works; exact numeric parity with the
  legacy TensorFlow backend is explicitly not required.
- **Legacy stack caveat.** The legacy SLEAP 1.4.1a2 / TensorFlow 2.7 stack has no `sm_120`
  (Blackwell) support and is not used here; `sleap-nn` is torch-based. This is expected and
  not a blocker for this repo.
