"""Regenerate the ``checksums:`` block of ``model_selection.yaml``.

Prints the SHA256 of each ``<model_id>.zip`` referenced by the committed selection
matrix, as a YAML mapping ready to paste into the matrix.

Usage:
    uv run python scripts/regen_model_checksums.py <models-root>

where ``<models-root>`` holds every referenced model as ``<model_id>.zip`` (the model id is
a relative path, e.g. ``20250401_wheat_models/250328_095645.multi_instance.n=1658``). Not
every model ships in a models-downloader snapshot, so stage all of them under one root; a
partial root reports the absent ones as MISSING.
"""

import sys
from pathlib import Path

from sleap_roots_training.registry import cards, chooser
from sleap_roots_training.registry.models import _sha256_of_file


def main(models_root: str) -> int:
    """Print the ``checksums:`` block for the ``<model_id>.zip`` files under ``models_root``."""
    root = Path(models_root)
    matrix = chooser.load_selection_matrix()
    model_ids = sorted(
        {c.source_model_id for c in cards.expand_rows_to_cards(matrix.rows)}
    )
    print("checksums:")
    for model_id in model_ids:
        zip_path = root / f"{model_id}.zip"
        if not zip_path.is_file():
            print(f"  # MISSING: {model_id}.zip", file=sys.stderr)
            continue
        print(f"  {model_id}: {_sha256_of_file(zip_path)}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
