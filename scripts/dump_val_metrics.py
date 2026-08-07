"""Print the val evaluation metrics saved by ``sleap-nn train`` for one or more runs.

``sleap-nn train`` writes ``models/<run_name>/metrics.val.0.npz`` after each run. This reads those
files and prints the headline keypoint metrics so the Tier 1 baseline table can be assembled from
the saved artifacts rather than by scrolling back through the training logs. A run that collapsed
to zero predicted instances shows up as all-NaN (see docs/training.md).

``numpy`` is imported lazily (it rides in with the train extra), so this module stays importable in
the base env for unit tests of the MISSING / arg-handling paths.

Usage (on the GPU box, from the repo dir):
    uv run --no-sync python scripts/dump_val_metrics.py <run_name> [<run_name> ...]
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path


def _emit(key: str, value: object) -> None:
    """Print one metric, summarizing arrays and unwrapping 0-d object dicts.

    Object arrays that wrap a dict are assumed 0-d (the shape sleap-nn writes); an ``ndim >= 1``
    object array of dicts would fall through to the generic sample branch — acceptable here, not a
    crash.
    """
    import numpy as np

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
    valid = int(np.count_nonzero(~np.isnan(flat)))
    if valid:
        # Surface the valid/total count so a *partial* collapse can't hide behind a plausible mean.
        print(
            f"   {key}: shape={arr.shape} mean={np.nanmean(flat):.4f} "
            f"({valid}/{flat.size} valid)"
        )
    else:
        print(f"   {key}: shape={arr.shape} (all-nan/empty)")


def dump(run: str) -> bool:
    """Print the val metrics for one run; return True on success (all-NaN means it collapsed).

    ``models/<run>`` is relative to the current directory, matching the configs' ``ckpt_dir:
    models``; run this from the repo root. The ``.0.`` in the filename is sleap-nn's
    per-eval-dataset index.
    """
    path = Path("models") / run / "metrics.val.0.npz"
    if not path.exists():
        print(f"=== {run} ===\n   MISSING ({path})")
        return False
    import numpy as np  # lazy: needed only once we actually have a file to load

    try:
        data = np.load(path, allow_pickle=True)
        print(f"=== {run} ===  (keys: {list(data.files)})")
        for key in data.files:
            _emit(key, data[key])
    except (OSError, ValueError, EOFError, zipfile.BadZipFile) as exc:
        # a truncated/corrupt npz must not abort the rest of the batch
        print(f"=== {run} ===\n   CORRUPT ({path}): {type(exc).__name__}: {exc}")
        return False
    return True


def main(argv: list[str]) -> int:
    """CLI entry point: dump val metrics for each run name in argv (nonzero if any failed)."""
    if len(argv) < 2:
        print(
            "usage: python scripts/dump_val_metrics.py <run_name> [<run_name> ...]",
            file=sys.stderr,
        )
        return 2
    # Materialize to a list (not a generator) so EVERY run is dumped even if an earlier one fails.
    results = [dump(run) for run in argv[1:]]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
