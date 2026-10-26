"""Build a byte-reproducible ``<model_id>.zip`` from a trained model directory.

The registry pins each source archive by SHA256 (``checksums:`` in
``model_selection.yaml``). An ordinary zip's bytes depend on file timestamps, modes, the
host and the compressor, so its checksum could only be re-derived by keeping the archive
itself. This writes entries **stored** (uncompressed), in sorted path order, with a fixed
timestamp, fixed permission bits and a fixed creator system, each under one top-level
directory named after the (resolved) model directory. The same file tree -- the same
names and bytes, under a directory of the same name -- therefore always gives the same
SHA256, on any host and Python, and it is printed. OS junk (``.DS_Store``, ``Thumbs.db``,
``__MACOSX``, ``Zone.Identifier``) is left out; anything else in the directory is archived,
so build from a directory holding only the model's files.

Usage:
    uv run python scripts/build_model_zip.py <model-dir> <models-root>/<model_id>.zip

It refuses a directory without ``best_model.h5`` and ``training_config.json``, an output
inside the model directory (the next build would archive it), and an existing output. The
archive is written to a temporary file beside the output and renamed into place only once
complete, so a failed build leaves nothing an operator could mistake for a good archive. An
existing temporary file is refused and left alone: it may be another build's.
"""

import shutil
import sys
import zipfile
from pathlib import Path

from sleap_roots_training.registry.models import (
    ESSENTIAL_FILES,
    _sha256_of_file,
    junk_filter,
)

# The earliest timestamp a zip entry can carry; any fixed value works, this one is canonical.
_FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)
# Regular file, rw-r--r--, recorded as created on Unix so every host writes the same bytes.
_FILE_ATTR = 0o100644 << 16
_UNIX = 3
_COPY_CHUNK = 1 << 20


def main(model_dir: str, out_zip: str) -> int:
    """Write the reproducible archive of ``model_dir`` to ``out_zip`` and print its SHA256.

    Args:
        model_dir: The trained model directory (holding ``best_model.h5`` and
            ``training_config.json``); relative paths, including ``.``, are resolved.
        out_zip: The archive to create, outside ``model_dir``; its parent directories are
            created.

    Returns:
        0 on success; 1 when the source is not a model directory or the output is inside
        it or already exists.
    """
    source, out = Path(model_dir).resolve(), Path(out_zip).resolve()
    if not source.is_dir() or not source.name:
        print(f"not a directory: {model_dir}", file=sys.stderr)
        return 1
    if source in out.parents:
        print(f"refusing to write inside the model directory: {out}", file=sys.stderr)
        return 1
    if out.exists():
        print(f"refusing to overwrite: {out} exists", file=sys.stderr)
        return 1
    relative = junk_filter(
        p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()
    )
    missing = [name for name in ESSENTIAL_FILES if name not in relative]
    if missing:
        print(f"not a model directory: {source} lacks {missing}", file=sys.stderr)
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_name(out.name + ".partial")
    # Created exclusively before the cleanup below takes ownership of it: an existing
    # partial may be another build's work in progress, so it is refused, never deleted.
    try:
        handle = open(partial, "xb")
    except FileExistsError:
        print(
            f"refusing to build: {partial} exists (a killed or running build); "
            "remove it once no build is writing it",
            file=sys.stderr,
        )
        return 1
    try:
        with handle, zipfile.ZipFile(handle, "w") as archive:
            for name in relative:
                path = source / name
                info = zipfile.ZipInfo(f"{source.name}/{name}", _FIXED_DATE_TIME)
                info.external_attr = _FILE_ATTR
                info.create_system = _UNIX
                info.compress_type = zipfile.ZIP_STORED
                # Set before opening, as `writestr` does, so the ZIP64 decision -- and with
                # it the bytes -- match; then stream rather than hold a large file in memory.
                info.file_size = path.stat().st_size
                with open(path, "rb") as src, archive.open(info, "w") as dest:
                    shutil.copyfileobj(src, dest, _COPY_CHUNK)
        partial.rename(out)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    print(_sha256_of_file(out))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
