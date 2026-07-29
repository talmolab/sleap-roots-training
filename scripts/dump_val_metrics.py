"""Print the val evaluation metrics saved by ``sleap-nn train`` for one or more runs.

``sleap-nn train`` writes ``models/<run_name>/metrics.val.0.npz`` after each run. This reads those
files and prints the headline keypoint metrics so the Tier 1 baseline table can be assembled from
the saved artifacts rather than by scrolling back through the training logs. A run that collapsed
to zero predicted instances shows up as all-NaN (see docs/training.md).

Usage (on the GPU box, from the repo dir):
    uv run --no-sync python scripts/dump_val_metrics.py <run_name> [<run_name> ...]
"""

from __future__ import annotations

import os
import sys

import numpy as np


def _emit(key: str, value: object) -> None:
    """Print one metric, summarizing arrays and unwrapping 0-d object dicts."""
    arr = np.asarray(value)
    if arr.dtype == object and arr.ndim == 0:
        inner = arr.item()
        if isinstance(inner, dict):
            for k, v in inner.items():
                _emit(f"{key}.{k}", v)
            return
        print(f"   {key} = {inner}")
        return
    if arr.ndim == 0:
        print(f"   {key} = {arr.item()}")
        return
    if not np.issubdtype(arr.dtype, np.number):
        # non-numeric array (e.g. embedded source filenames) — just show a sample
        sample = arr.ravel()[:1].tolist()
        print(f"   {key}: shape={arr.shape} dtype={arr.dtype} sample={sample}")
        return
    flat = arr.astype(float).ravel()
    if flat.size and not np.all(np.isnan(flat)):
        print(f"   {key}: shape={arr.shape} mean={np.nanmean(flat):.4f}")
    else:
        print(f"   {key}: shape={arr.shape} (all-nan/empty)")


def dump(run: str) -> None:
    path = os.path.join("models", run, "metrics.val.0.npz")
    if not os.path.exists(path):
        print(f"=== {run} ===\n   MISSING ({path})")
        return
    data = np.load(path, allow_pickle=True)
    print(f"=== {run} ===  (keys: {list(data.files)})")
    for key in data.files:
        _emit(key, data[key])


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python scripts/dump_val_metrics.py <run_name> [<run_name> ...]", file=sys.stderr)
        return 2
    for run in argv[1:]:
        dump(run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
