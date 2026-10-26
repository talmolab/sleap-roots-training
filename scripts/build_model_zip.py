"""Build a byte-reproducible ``<model_id>.zip`` from a trained model directory.

The registry pins each source archive by SHA256 (``checksums:`` in
``model_selection.yaml``). An ordinary zip's bytes depend on file timestamps and the
compressor, so its checksum could only be re-derived by keeping the archive itself. This
writes entries **stored** (uncompressed), in sorted path order, with a fixed timestamp and
fixed permission bits, each under one top-level directory named after the model directory.
The same directory contents therefore always give the same SHA256, which it prints. OS junk
(``.DS_Store``, ``Thumbs.db``, ``__MACOSX``, ``Zone.Identifier``) is left out, so the digest
cannot depend on the host that built it.

Usage:
    uv run python scripts/build_model_zip.py <model-dir> <models-root>/<model_id>.zip

It refuses to overwrite an existing output.
"""

import sys
import zipfile
from pathlib import Path

from sleap_roots_training.registry.models import _sha256_of_file, junk_filter

# The earliest timestamp a zip entry can carry; any fixed value works, this one is canonical.
_FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)
# Regular file, rw-r--r--, recorded as created on Unix so every host writes the same bytes.
_FILE_ATTR = 0o100644 << 16
_UNIX = 3


def main(model_dir: str, out_zip: str) -> int:
    """Write the reproducible archive of ``model_dir`` to ``out_zip`` and print its SHA256.

    Args:
        model_dir: The trained model directory (holding ``best_model.h5`` and
            ``training_config.json``).
        out_zip: The archive to create; its parent directories are created.

    Returns:
        0 on success; 1 when the source is not a directory or the output already exists.
    """
    source, out = Path(model_dir), Path(out_zip)
    if not source.is_dir():
        print(f"not a directory: {source}", file=sys.stderr)
        return 1
    if out.exists():
        print(f"refusing to overwrite: {out} exists", file=sys.stderr)
        return 1
    relative = junk_filter(
        p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "x", compression=zipfile.ZIP_STORED) as archive:
        for name in relative:
            info = zipfile.ZipInfo(f"{source.name}/{name}", _FIXED_DATE_TIME)
            info.external_attr = _FILE_ATTR
            info.create_system = _UNIX
            archive.writestr(info, (source / name).read_bytes())
    print(_sha256_of_file(out))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
