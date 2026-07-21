"""GPU backend smoke test (integration-marked; skipped without a CUDA device).

Mirrors ``talmolab/sleap-roots-predict``'s ``tests/test_gpu.py``, extended to record the
``torch`` build-arch list and the device compute capability so a run on the target
hardware (RTX A5000, ``sm_86``) documents whether kernels are native or PTX-JIT.

Marked ``@pytest.mark.integration`` so the default CI run (``-m "not integration"``, with
no ``train`` extra installed) deselects it and never requires a GPU, ``torch``, or network.
``torch`` is imported inside the test body (never at module scope), so collection never
raises where ``torch`` is absent — the test skips cleanly instead.
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
def test_gpu_available_and_report_arch():
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("no CUDA device available")

    arch_list = torch.cuda.get_arch_list()
    capability = torch.cuda.get_device_capability()
    print(f"torch {torch.__version__} (CUDA {torch.version.cuda})")
    print(f"device: {torch.cuda.get_device_name(0)}")
    print(f"compute capability: sm_{capability[0]}{capability[1]}")
    print(f"arch list: {arch_list}")

    assert torch.cuda.is_available()
    assert arch_list, "torch.cuda.get_arch_list() is empty"
