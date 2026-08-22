"""Unit tests for the Tier 1 baseline helper scripts.

Both scripts import their heavy dep lazily (``clean_pkg`` -> ``sleap_io``, ``dump_val_metrics`` ->
``numpy``), so the modules import in the base env and the dependency-free logic (video selection,
the ``inp == out`` / empty-package / arg guards, the MISSING path) is covered on the normal CI
matrix.

The ``numpy`` paths (``_emit`` formatting, loading a real ``.npz``) used to be marked
``integration`` "so they run only where the train extra is installed". That premise was wrong:
``numpy`` is an unconditional requirement of both ``pandas`` and ``sleap-io``, which are *core*
dependencies, so it is present in every install including the base CI env
(``uv sync --locked --group dev``). The marker bought nothing and cost coverage — CI runs
``-m "not integration"``, so these tests ran nowhere, which is how the corrupt-``.npz`` bug they
cover survived on ``main``. They are unmarked. See #53 for the integration tests still in that
position.
"""

from __future__ import annotations

import importlib.util
import sys
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
regen_model_checksums = _load("regen_model_checksums")


# --- fakes for clean_pkg (no sleap_io needed) --------------------------------------------------


class _FakeSourceVideo:
    def __init__(self, filename: str) -> None:
        self.filename = filename


class _FakeVideo:
    def __init__(self) -> None:
        self.source_video = "\\\\multilab-na.ad.salk.edu\\hpi_dev\\raw.mp4"
        self.shape = (1, 2, 2, 1)


class _FakeLF:
    def __init__(self, video: _FakeVideo) -> None:
        self.video = video


class _FakeNode:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeSkeleton:
    def __init__(self, nodes: list) -> None:
        self.nodes = list(nodes)


class _FakeSuggestion:
    def __init__(self, video: _FakeVideo) -> None:
        self.video = video


_R1_R6 = [f"r{i}" for i in range(1, 7)]


class _FakeLabels:
    def __init__(self, videos, lfs, skeletons=None, suggestions=None) -> None:
        self.videos = list(videos)
        self._lfs = list(lfs)
        self.suggestions = list(suggestions or [])
        self.skeletons = (
            skeletons
            if skeletons is not None
            else [_FakeSkeleton([_FakeNode(n) for n in _R1_R6])]
        )

    def __iter__(self):
        return iter(self._lfs)

    def __len__(self) -> int:
        return len(self._lfs)


def _install_fake_sio(monkeypatch, load_map: dict) -> dict:
    """Inject a fake ``sleap_io`` so ``clean()`` runs in the base env.

    ``load_map`` maps a path string to the ``_FakeLabels`` that ``load_slp`` should return for it
    (``clean`` loads the input once, then re-loads the output for the share-marker check).
    ``save_slp`` writes a stub file so the sha256 / sidecar paths run, and records what it saved.
    Returns the ``saved`` dict for assertions.
    """
    import types

    saved: dict = {}

    def load_slp(path, open_videos=True):
        return load_map[str(path)]

    def save_slp(labels, path, embed=True):
        Path(path).write_bytes(b"fake-embedded-slp")
        saved["labels"], saved["path"] = labels, str(path)

    monkeypatch.setitem(
        sys.modules,
        "sleap_io",
        types.SimpleNamespace(load_slp=load_slp, save_slp=save_slp),
    )
    return saved


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


def test_clean_end_to_end_drops_frameless_prunes_suggestions_and_writes_sidecar(
    tmp_path, monkeypatch, capsys
):
    inp = tmp_path / "in.pkg.slp"
    inp.write_bytes(b"raw-input-bytes")
    out = tmp_path / "out.pkg.slp"
    framed, frameless = _FakeVideo(), _FakeVideo()
    dirty = _FakeLabels(
        [framed, frameless],
        [_FakeLF(framed), _FakeLF(framed)],
        suggestions=[_FakeSuggestion(frameless)],  # points at the video we drop
    )
    clean_v = _FakeVideo()
    clean_v.source_video = None  # the reloaded output: pointer already nulled
    reloaded = _FakeLabels([clean_v], [_FakeLF(clean_v)])
    _install_fake_sio(monkeypatch, {str(inp): dirty, str(out): reloaded})

    clean_pkg.clean(str(inp), str(out))

    assert dirty.videos == [framed]  # frame-less video dropped
    assert dirty.suggestions == []  # suggestion to the dropped video pruned
    assert all(
        v.source_video is None for v in dirty.videos
    )  # provenance pointer nulled
    assert out.exists()  # save_slp wrote the output
    sidecar = Path(str(out) + ".sha256")
    assert sidecar.exists() and clean_pkg._sha256(str(out)) in sidecar.read_text()
    printed = capsys.readouterr().out
    assert "1 video(s) kept (1 frame-less dropped)" in printed
    assert "r1" in printed and "r6" in printed


def test_clean_refuses_empty_package(tmp_path, monkeypatch):
    inp = tmp_path / "in.pkg.slp"
    inp.write_bytes(b"x")
    out = tmp_path / "out.pkg.slp"
    dirty = _FakeLabels([_FakeVideo()], [])  # no labeled frames at all
    _install_fake_sio(monkeypatch, {str(inp): dirty})
    with pytest.raises(SystemExit, match="no videos carry labeled frames"):
        clean_pkg.clean(str(inp), str(out))
    assert not out.exists()  # nothing written


def test_clean_raises_if_share_pointer_survives_reload(tmp_path, monkeypatch):
    inp = tmp_path / "in.pkg.slp"
    inp.write_bytes(b"x")
    out = tmp_path / "out.pkg.slp"
    framed = _FakeVideo()
    dirty = _FakeLabels([framed], [_FakeLF(framed)])
    leaked = _FakeVideo()
    leaked.source_video = _FakeSourceVideo(
        "\\\\multilab-na.ad.salk.edu\\hpi_dev\\raw.mp4"
    )
    reloaded = _FakeLabels([leaked], [_FakeLF(leaked)])
    _install_fake_sio(monkeypatch, {str(inp): dirty, str(out): reloaded})
    with pytest.raises(ValueError, match="still points at the share"):
        clean_pkg.clean(str(inp), str(out))


def test_clean_requires_a_skeleton(tmp_path, monkeypatch):
    inp = tmp_path / "in.pkg.slp"
    inp.write_bytes(b"x")
    out = tmp_path / "out.pkg.slp"
    framed = _FakeVideo()
    dirty = _FakeLabels([framed], [_FakeLF(framed)], skeletons=[])  # skeleton-less file
    _install_fake_sio(monkeypatch, {str(inp): dirty})
    with pytest.raises(ValueError, match="no skeleton"):
        clean_pkg.clean(str(inp), str(out))
    assert not out.exists()


def test_sha256_matches_identical_content_and_differs_otherwise(tmp_path):
    a, b, c = tmp_path / "a", tmp_path / "b", tmp_path / "c"
    a.write_bytes(b"hello world")
    b.write_bytes(b"hello world")
    c.write_bytes(b"different bytes")
    assert clean_pkg._sha256(str(a)) == clean_pkg._sha256(str(b))
    assert clean_pkg._sha256(str(a)) != clean_pkg._sha256(str(c))


# --- dump_val_metrics (base-safe: MISSING path + arg handling, no numpy) -----------------------


def test_dump_missing_run_returns_false(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert dump_val_metrics.dump("does_not_exist") is False
    assert "MISSING" in capsys.readouterr().out


def test_dump_val_metrics_main_usage_and_exit_codes(tmp_path, monkeypatch):
    assert dump_val_metrics.main(["dump_val_metrics.py"]) == 2  # no run names
    monkeypatch.chdir(tmp_path)
    assert dump_val_metrics.main(["dump_val_metrics.py", "absent"]) == 1  # a run failed


# --- dump_val_metrics -------------------------------------------------------------------------


def _write_metrics_npz(path: Path, metrics: dict) -> None:
    import numpy as np

    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, metrics=np.array(metrics, dtype=object))


def _write_npz_with_truncated_pickle(path: Path) -> None:
    """Write a structurally valid ``.npz`` whose member holds a truncated pickle.

    Byte-flipping a member instead would break the zip CRC and raise ``BadZipFile``, which the
    handler already caught — so it would not exercise the uncaught path at all. Rewriting the
    archive with ``zipfile`` recomputes a correct CRC, so the damage survives the zip layer and
    reaches the unpickler. That is what a ``.npz`` from an interrupted ``sleap-nn train`` (killed
    job, full disk) actually looks like: the archive is well-formed, the pickle inside is not.
    """
    import zipfile

    source = path.parent / "_source_for_truncation.npz"
    _write_metrics_npz(source, {"distance_metrics": {"avg": 12.3}})
    # `with` rather than relying on the temporary being refcount-collected before the unlink:
    # on Windows a still-open handle makes `source.unlink()` raise PermissionError.
    with zipfile.ZipFile(source) as archive:
        member = archive.read("metrics.npy")
    source.unlink()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr("metrics.npy", member[: len(member) - 12])


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


def test_dump_reports_a_member_that_fails_to_unpickle(tmp_path, monkeypatch, capsys):
    """The second uncaught path, and the one a narrow guard around ``np.load`` would miss.

    ``np.load`` returns a *lazy* ``NpzFile``: members are decompressed and unpickled on
    ``__getitem__``, not at load time. So a file whose archive is well-formed but whose member is
    a truncated pickle raises inside the read loop, well after ``np.load`` has returned happily.
    Both paths raise ``UnpicklingError``, which subclasses none of ``OSError`` / ``ValueError`` /
    ``EOFError`` / ``BadZipFile``.
    """
    monkeypatch.chdir(tmp_path)
    truncated = tmp_path / "models" / "run_trunc" / "metrics.val.0.npz"
    truncated.parent.mkdir(parents=True, exist_ok=True)
    _write_npz_with_truncated_pickle(truncated)

    assert dump_val_metrics.dump("run_trunc") is False
    out = capsys.readouterr().out
    assert "CORRUPT" in out
    # The exception type is named, so an operator can tell a truncated write apart from a
    # wholly unreadable file without re-running under a debugger.
    assert "UnpicklingError" in out


def test_a_corrupt_run_does_not_abort_the_batch(tmp_path, monkeypatch, capsys):
    """The guarantee both comments in the script claim, asserted end-to-end through ``main``.

    ``dump``'s handler says "a truncated/corrupt npz must not abort the rest of the batch", and
    ``main`` materializes a list "so EVERY run is dumped even if an earlier one fails". Calling
    ``dump`` directly cannot see whether that holds: a fix that left ``main`` propagating would
    still pass every other test here. The good run *after* the corrupt one is the whole point —
    that is the output silently lost before this fix.
    """
    monkeypatch.chdir(tmp_path)
    models = tmp_path / "models"
    _write_metrics_npz(models / "run_ok" / "metrics.val.0.npz", {"m": {"avg": 12.3}})
    (models / "run_bad").mkdir(parents=True, exist_ok=True)
    (models / "run_bad" / "metrics.val.0.npz").write_bytes(b"not a real npz")
    _write_metrics_npz(models / "run_later" / "metrics.val.0.npz", {"m": {"avg": 45.6}})

    exit_code = dump_val_metrics.main(
        ["dump_val_metrics.py", "run_ok", "run_bad", "run_later"]
    )
    out = capsys.readouterr().out

    assert "12.3" in out
    assert "CORRUPT" in out
    assert "45.6" in out, "the run after the corrupt one must still be dumped"
    assert exit_code == 1  # nonzero, because one of the three failed


def test_a_bug_in_emit_is_not_reported_as_a_corrupt_file(tmp_path, monkeypatch, capsys):
    """The discriminator for guarding the *read* rather than the whole function.

    The untrusted thing is the file, not our own formatting code. If the ``try`` also wrapped
    ``_emit``, a genuine programming error in formatting would reach the operator as
    ``CORRUPT (<path>)`` — sending them to investigate a data file that is perfectly fine, while
    the real bug stays invisible. A broad ``except Exception`` around the whole body passes every
    other test in this file and fails only this one.
    """
    monkeypatch.chdir(tmp_path)
    good = tmp_path / "models" / "run_ok" / "metrics.val.0.npz"
    _write_metrics_npz(good, {"distance_metrics": {"avg": 12.3}})

    def _boom(key, value):
        raise AttributeError("simulated bug in _emit")

    monkeypatch.setattr(dump_val_metrics, "_emit", _boom)
    with pytest.raises(AttributeError, match="simulated bug"):
        dump_val_metrics.dump("run_ok")
    assert "CORRUPT" not in capsys.readouterr().out


# --- regen_model_checksums (consumes the Card API) ---------------------------------------------


def test_regen_model_checksums_enumerates_every_physical_model(tmp_path, capsys):
    # This script consumes `expand_rows_to_cards` and `c.source_model_id` but sits in
    # NO CI path filter, NO lint target and, until now, NO test -- so a break here was
    # silent. It reddened for real when the Card shape changed, which is exactly the
    # class of break this guards.
    assert regen_model_checksums.main(str(tmp_path)) == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("checksums:")
    # Every distinct physical model is enumerated, one line each, deduped and sorted.
    missing = [ln for ln in captured.err.splitlines() if "MISSING" in ln]
    assert len(missing) == 8, captured.err
    assert missing == sorted(missing)


def test_regen_model_checksums_hashes_a_present_archive(tmp_path, capsys):
    # The negative control: the MISSING path above passes even if the hashing branch is
    # broken. Plant one real archive and assert it is hashed rather than reported absent.
    import hashlib
    import zipfile

    model_id = "rice/older/crown/221208_113552.multi_instance.n=574"
    archive = tmp_path / f"{model_id}.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("best_model.h5", "w")
    expected = hashlib.sha256(archive.read_bytes()).hexdigest()

    assert regen_model_checksums.main(str(tmp_path)) == 0
    captured = capsys.readouterr()
    assert f"  {model_id}: {expected}" in captured.out
    assert model_id not in captured.err  # not reported missing
