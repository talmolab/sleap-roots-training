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

    try:
        device_name = torch.cuda.get_device_name(0)
        capability = torch.cuda.get_device_capability()
        arch_list = torch.cuda.get_arch_list()
    except Exception as exc:  # driver/runtime mismatch on a flaky GPU host
        pytest.skip(f"CUDA introspection failed: {exc}")

    print(f"torch {torch.__version__} (CUDA {torch.version.cuda})")
    print(f"device: {device_name}")
    print(f"compute capability: sm_{capability[0]}{capability[1]}")
    print(f"arch list: {arch_list}")

    assert arch_list, "torch.cuda.get_arch_list() is empty"
