import hashlib
import zipfile
from pathlib import Path

import pytest

from sleap_roots_training.registry import models

MODEL_ID = "soybean/primary/221003_111420.multi_instance.n=1389"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_model_zip(
    models_root: Path, model_id: str, *, with_h5=True, junk=True, prefix=""
):
    """Build ``<models_root>/<model_id>.zip`` and return its SHA256.

    ``prefix`` lets a zip wrap its contents in an inner directory (some real
    snapshot zips have ``<subdir>/best_model.h5``, others have it at the root).
    """
    zip_path = models_root / f"{model_id}.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w") as zf:
        if with_h5:
            zf.writestr(f"{prefix}best_model.h5", b"\x89HDF\r\n\x1a\n weights")
        zf.writestr(f"{prefix}training_config.json", b'{"model": "cfg"}')
        zf.writestr(f"{prefix}viz/validation.0000.png", b"PNGDATA")
        if junk:
            zf.writestr(".DS_Store", b"junk")
            zf.writestr("__MACOSX/._best_model.h5", b"junk")
    return _sha256(zip_path)


def test_junk_filter_is_order_independent_and_drops_junk():
    names = [
        "best_model.h5",
        "training_config.json",
        "viz/a.png",
        ".DS_Store",
        "__MACOSX/x",
        "Thumbs.db",
    ]
    kept = ["best_model.h5", "training_config.json", "viz/a.png"]
    assert models.junk_filter(names) == models.junk_filter(list(reversed(names)))
    assert models.junk_filter(names) == sorted(kept)


def test_resolve_archive_verifies_extracts_and_omits_junk(tmp_path):
    root = tmp_path / "snapshot"
    sha = _make_model_zip(root, MODEL_ID)
    resolved = models.resolve_model_dir(
        MODEL_ID, root, {MODEL_ID: sha}, cache_root=tmp_path / "cache"
    )
    assert isinstance(resolved, Path) and resolved.is_dir()
    assert (resolved / "best_model.h5").exists()
    assert (resolved / "training_config.json").exists()
    assert not (resolved / ".DS_Store").exists()
    assert not (resolved / "__MACOSX").exists()


def test_resolve_archive_with_wrapper_subdir(tmp_path):
    # Some real snapshot zips wrap contents in `<id>/best_model.h5`.
    root = tmp_path / "snapshot"
    sha = _make_model_zip(root, MODEL_ID, prefix="221003_111420.n=1389/")
    resolved = models.resolve_model_dir(
        MODEL_ID, root, {MODEL_ID: sha}, cache_root=tmp_path / "cache"
    )
    # Resolution normalizes to the dir that actually holds best_model.h5.
    assert (resolved / "best_model.h5").exists()
    assert (resolved / "training_config.json").exists()


def test_resolve_checksum_mismatch_raises(tmp_path):
    root = tmp_path / "snapshot"
    _make_model_zip(root, MODEL_ID)
    with pytest.raises(ValueError, match="(?i)sha256|checksum"):
        models.resolve_model_dir(
            MODEL_ID, root, {MODEL_ID: "0" * 64}, cache_root=tmp_path / "cache"
        )


def test_resolve_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match=MODEL_ID):
        models.resolve_model_dir(
            MODEL_ID, tmp_path, {MODEL_ID: "0" * 64}, cache_root=tmp_path / "cache"
        )


def test_resolve_post_unzip_missing_essential_raises(tmp_path):
    root = tmp_path / "snapshot"
    sha = _make_model_zip(root, MODEL_ID, with_h5=False)
    with pytest.raises(ValueError, match="best_model.h5"):
        models.resolve_model_dir(
            MODEL_ID, root, {MODEL_ID: sha}, cache_root=tmp_path / "cache"
        )


def test_resolve_unzipped_dir_is_unpinned_dev_convenience(tmp_path):
    root = tmp_path / "snapshot"
    model_dir = root / MODEL_ID
    model_dir.mkdir(parents=True)
    (model_dir / "best_model.h5").write_bytes(b"w")
    (model_dir / "training_config.json").write_bytes(b"{}")
    # Dev/dry-run: returns the dir as-is.
    got = models.resolve_model_dir(MODEL_ID, root, {}, require_pinned=False)
    assert got == model_dir
    # Under --execute (require_pinned): rejected as not snapshot-pinned.
    with pytest.raises(ValueError, match="(?i)pin"):
        models.resolve_model_dir(MODEL_ID, root, {}, require_pinned=True)


def test_extraction_is_deterministic_across_roots(tmp_path):
    root = tmp_path / "snapshot"
    sha = _make_model_zip(root, MODEL_ID)
    d1 = models.resolve_model_dir(
        MODEL_ID, root, {MODEL_ID: sha}, cache_root=tmp_path / "c1"
    )
    d2 = models.resolve_model_dir(
        MODEL_ID, root, {MODEL_ID: sha}, cache_root=tmp_path / "c2"
    )
    manifest1 = {
        p.relative_to(d1).as_posix(): _sha256(p) for p in d1.rglob("*") if p.is_file()
    }
    manifest2 = {
        p.relative_to(d2).as_posix(): _sha256(p) for p in d2.rglob("*") if p.is_file()
    }
    assert manifest1 == manifest2
    assert set(manifest1) == {
        "best_model.h5",
        "training_config.json",
        "viz/validation.0000.png",
    }
