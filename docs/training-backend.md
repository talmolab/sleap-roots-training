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

> **Status:** commands below reflect the documented `sleap-nn` CLI. The GPU/arch findings
> section is a placeholder to be backfilled from a real run on the target hardware — see
> "GPU / CUDA arch findings". `sleap-nn` **0.3.0** introduced the unified `sleap-nn predict`
> CLI; on the pinned **0.2.0** the prediction entrypoint may differ, so record what actually
> works on the box.

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

`--torch-backend=auto` detects the 12.4 driver and picks a compatible PyTorch CUDA wheel.
If you want to pin it explicitly, use `--torch-backend=cu124` (matches the driver) or
`cu126` (runs on a 12.4 driver via CUDA minor-version forward-compatibility). `cu128`
(CUDA 12.8) also works via forward-compat, but update the NVIDIA driver first if you hit a
CUDA-init error. `--torch-backend` requires the `uv pip` interface (not `uv sync`).

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

Use a small labeled sample dataset (a SLEAP / `sleap-nn` sample `.pkg.slp`; the point is
that the path works, not that the model is good). Training is config-driven:

```bash
uv run sleap-nn train --config config.yaml
```

The `config.yaml` sets at least:

- `data_config.train_labels_path` / `data_config.val_labels_path` → the sample `.pkg.slp`
  files;
- `model_config` → backbone + head (single-instance / centered-instance keypoints);
- `trainer_config` → `max_epochs` (keep tiny, e.g. 1–2), `save_ckpt: true`, `ckpt_dir`,
  `run_name`.

(The exact minimal `config.yaml` used is recorded with the run in the PR.)

## 4. Predict with the trained model

```bash
uv run sleap-nn predict --data_path val.pkg.slp --model_paths models/<run_name>/ -o val.predictions.slp
```

Confirm `val.predictions.slp` is written with predicted instances.

## GPU / CUDA arch findings

<!-- TODO(spike): backfill from the real A5000 run (task 4). Paste the exact
torch.cuda.get_arch_list() and get_device_capability() output, and state whether sm_86 runs
native SASS kernels or falls back to PTX JIT. -->

_To be recorded from the verification run on the RTX A5000:_

- `torch` version / bundled CUDA: _TBD_
- `torch.cuda.get_arch_list()`: _TBD_
- `torch.cuda.get_device_capability()`: _TBD_ (expected `(8, 6)` → `sm_86`)
- Native SASS kernels for `sm_86`, or PTX-JIT fallback? _TBD_

## Notes

- **Parity is not the bar.** Per `docs/roadmap.md` ("Oracle / validation philosophy"), this
  run establishes that the PyTorch/`sleap-nn` path works; exact numeric parity with the
  legacy TensorFlow backend is explicitly not required.
- **Legacy stack caveat.** The legacy SLEAP 1.4.1a2 / TensorFlow 2.7 stack has no `sm_120`
  (Blackwell) support and is not used here; `sleap-nn` is torch-based. This is expected and
  not a blocker for this repo.
