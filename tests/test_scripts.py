"""Unit tests for the Tier 1 baseline helper scripts.

Both scripts import their heavy dep lazily (``clean_pkg`` -> ``sleap_io``, ``dump_val_metrics`` ->
``numpy``), so the modules import in the base env and the dependency-free logic (video selection,
the ``inp == out`` / empty-package / arg guards, the MISSING path) is covered on the normal CI
matrix. The paths that actually touch ``numpy`` (``_emit`` formatting, loading a real ``.npz``) are
marked ``integration`` so they run only where the train extra is installed.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(name: str):
    """Import ``scripts/<name>.py`` as a module (heavy deps are lazy, so this is base-safe)."""
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


clean_pkg = _load("clean_pkg")
dump_val_metrics = _load("dump_val_metrics")


# --- fakes for clean_pkg's pure selection logic (no sleap_io needed) ---------------------------


class _FakeVideo:
    def __init__(self) -> None:
        self.source_video = "\\\\multilab-na.ad.salk.edu\\hpi_dev\\raw.mp4"
        self.shape = (1, 2, 2, 1)


class _FakeLF:
    def __init__(self, video: _FakeVideo) -> None:
        self.video = video


class _FakeLabels:
    def __init__(self, videos: list, lfs: list) -> None:
        self.videos = list(videos)
        self._lfs = list(lfs)
        self.suggestions: list = []

    def __iter__(self):
        return iter(self._lfs)

    def __len__(self) -> int:
        return len(self._lfs)


# --- clean_pkg (base-safe) ---------------------------------------------------------------------


def test_select_videos_drops_the_frameless_stray():
    framed, frameless = _FakeVideo(), _FakeVideo()
    labels = _FakeLabels([framed, frameless], [_FakeLF(framed), _FakeLF(framed)])
    keep, used_ids = clean_pkg._select_videos(labels)
    assert keep == [framed]  # identity: the frameless video is dropped
    assert used_ids == {id(framed)}


def test_select_videos_all_frameless_keeps_nothing():
    labels = _FakeLabels([_FakeVideo(), _FakeVideo()], [])
    keep, used_ids = clean_pkg._select_videos(labels)
    assert keep == []
    assert used_ids == set()


def test_clean_refuses_to_overwrite_input_in_place(tmp_path):
    p = tmp_path / "v000.pkg.slp"
    p.write_bytes(b"")  # content irrelevant: the guard fires before any sleap_io load
    with pytest.raises(SystemExit, match="inp == out"):
        clean_pkg.clean(str(p), str(p))


def test_clean_pkg_main_usage_error():
    assert clean_pkg.main(["clean_pkg.py"]) == 2  # too few args
    assert clean_pkg.main(["clean_pkg.py", "only_one.slp"]) == 2


# --- dump_val_metrics (base-safe: MISSING path + arg handling, no numpy) -----------------------


def test_dump_missing_run_returns_false(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert dump_val_metrics.dump("does_not_exist") is False
    assert "MISSING" in capsys.readouterr().out


def test_dump_val_metrics_main_usage_and_exit_codes(tmp_path, monkeypatch):
    assert dump_val_metrics.main(["dump_val_metrics.py"]) == 2  # no run names
    monkeypatch.chdir(tmp_path)
    assert dump_val_metrics.main(["dump_val_metrics.py", "absent"]) == 1  # a run failed


# --- dump_val_metrics (integration: needs numpy) ----------------------------------------------


def _write_metrics_npz(path: Path, metrics: dict) -> None:
    import numpy as np

    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, metrics=np.array(metrics, dtype=object))


@pytest.mark.integration
def test_emit_unwraps_dicts_scalars_and_summarizes_arrays(capsys):
    import numpy as np

    dump_val_metrics._emit(
        "m",
        np.array(
            {
                "avg": 30.09,
                "dists": np.array([1.0, np.nan, 3.0]),  # partial: 2/3 valid
                "empty": np.array([], dtype=float),
                "video_paths": np.array(["data/v000_raw_val.pkg.slp"]),
            },
            dtype=object,
        ),
    )
    out = capsys.readouterr().out
    assert "m.avg = 30.09" in out
    assert "2/3 valid" in out  # NaN fraction surfaced
    assert "all-nan/empty" in out  # the empty array
    assert "sample=" in out  # the non-numeric path array


@pytest.mark.integration
def test_dump_reads_good_npz_and_reports_corrupt(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    good = tmp_path / "models" / "run_ok" / "metrics.val.0.npz"
    _write_metrics_npz(good, {"distance_metrics": {"avg": 12.3}})
    assert dump_val_metrics.dump("run_ok") is True
    assert "distance_metrics.avg = 12.3" in capsys.readouterr().out

    bad = tmp_path / "models" / "run_bad" / "metrics.val.0.npz"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"not a real npz")
    assert dump_val_metrics.dump("run_bad") is False
    assert "CORRUPT" in capsys.readouterr().out
