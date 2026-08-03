"""Stratified frame selection: which scans, plants, and views a package labels.

Ported from the vault workflow's ``select_samples.py`` (talmolab/sleap-roots-training#26;
Box copy 2026-07-29). The port preserves the original's selection semantics — QC-cleaned
plants as the sampling pool, stratification by ``plant_age_days`` x ``accession_id``, and
the manifest columns downstream stages read. Deviations forced by the port are recorded in
the change's ``tasks.md`` section 7, not absorbed here.

Reads two CSVs and makes no network calls (design.md F2): the QC output
(``10_final_data.csv``) supplies the clean plant pool, and Bloom's ``scans.csv`` supplies
scan paths and the accession mapping. ``accession_names`` stays caller-supplied — the Bloom
database lookup that produces it is a documented manual prerequisite, deliberately outside
this change.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Mapping, Optional

import pandas as pd

logger = logging.getLogger(__name__)

#: Rotational views in a Bloom cylinder scan; images are named ``1.jpg`` .. ``72.jpg``.
TOTAL_VIEWS = 72

#: The columns ``sample_manifest.csv`` carries, in order. Decision 3 makes this the
#: row-level provenance that travels *inside* the package, so #10's ``publish-labels`` can
#: build a ``LabelCard`` without access to the machine that produced it.
MANIFEST_COLUMNS = (
    "scan_id",
    "plant_qr_code",
    "plant_age_days",
    "accession_id",
    "accession_name",
    "wave_number",
    "view_index",
    "frame_index",
    "source_scan_path",
    "source_image",
    "output_filename",
)


def _load_cleaned(cleaned_csv: Path) -> pd.DataFrame:
    """Load the QC-cleaned table, which may be one file or a glob over group files.

    Args:
        cleaned_csv: Path to ``10_final_data.csv``, or a glob pattern matching one
            such file per age group.

    Returns:
        The concatenated QC-cleaned table.

    Raises:
        FileNotFoundError: If the pattern matches no files.
    """
    cleaned_path = Path(cleaned_csv)
    if cleaned_path.is_file():
        return pd.read_csv(cleaned_path)
    files = sorted(cleaned_path.parent.glob(cleaned_path.name))
    if not files:
        raise FileNotFoundError(f"No files matching {cleaned_csv}")
    logger.info("Loaded %d QC files: %s", len(files), [f.parent.name for f in files])
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def _barcode_column(cleaned: pd.DataFrame) -> str:
    """Return the plant-barcode column name, which the QC pipeline renames.

    Args:
        cleaned: The QC-cleaned table.

    Returns:
        ``"Barcode"`` if the QC pipeline's renamed column is present, else
        ``"plant_qr_code"``.
    """
    return "Barcode" if "Barcode" in cleaned.columns else "plant_qr_code"


def select_view_indices(
    views_per_plant: int, total_views: int = TOTAL_VIEWS
) -> list[int]:
    """Return the 1-based view indices to label, evenly spaced over the rotation.

    Args:
        views_per_plant: Number of rotational views to select per plant.
        total_views: Views present in one scan.

    Returns:
        The selected 1-based view indices, ascending.
    """
    step = total_views // views_per_plant
    return [1 + i * step for i in range(views_per_plant)]


def select_samples(
    cleaned_csv: Path,
    scans_csv: Path,
    output_csv: Path,
    accession_names: Optional[Mapping[int, str]] = None,
    plants_per_group: int = 5,
    views_per_plant: int = 3,
    seed: int = 42,
) -> pd.DataFrame:
    """Select a stratified sample from QC-cleaned scans across age x accession.

    Args:
        cleaned_csv: Path to ``10_final_data.csv`` from sleap-roots-analyze QC output.
            May be a single file or a glob pattern matching multiple group files.
        scans_csv: Path to ``scans.csv`` from a Bloom download (for image path info).
        output_csv: Path to write ``sample_manifest.csv``.
        accession_names: Optional mapping of ``accession_id`` to name, from the Bloom
            database. When provided, names appear in the manifest and in filenames;
            otherwise the numeric id is used as a string.
        plants_per_group: Plants to sample per age x accession group.
        views_per_plant: Rotational views per plant.
        seed: Random seed for reproducibility.

    Returns:
        The manifest, one row per selected frame.
    """
    cleaned = _load_cleaned(Path(cleaned_csv))
    clean_barcodes = set(cleaned[_barcode_column(cleaned)].unique())
    logger.info(
        "QC-cleaned data: %d samples, %d unique plants",
        len(cleaned),
        len(clean_barcodes),
    )

    scans = pd.read_csv(scans_csv)
    logger.info("Full scans.csv: %d scans", len(scans))

    scans_clean = scans[scans["plant_qr_code"].isin(clean_barcodes)].copy()
    logger.info(
        "After QC filter: %d scans from %d plants",
        len(scans_clean),
        scans_clean["plant_qr_code"].nunique(),
    )

    sampled_plants = (
        scans_clean.groupby(["plant_age_days", "accession_id"])["plant_qr_code"]
        .apply(
            lambda x: x.drop_duplicates().sample(
                n=min(plants_per_group, x.nunique()), random_state=seed
            )
        )
        .reset_index(drop=True)
    )
    logger.info("Selected %d unique plants", len(sampled_plants))

    df_sampled = scans_clean[scans_clean["plant_qr_code"].isin(sampled_plants)].copy()

    selected_views = select_view_indices(views_per_plant)
    logger.info("Selected view indices: %s", selected_views)

    rows = []
    # Frame numbering is a per-scan counter, so it indexes views *within* a scan.
    scan_view_counter: dict[int, int] = {}

    for _, scan_row in df_sampled.iterrows():
        scan_path = Path(scan_row["scan_path"])
        scan_id = scan_row["scan_id"]
        acc_id = scan_row["accession_id"]
        acc_name = (
            accession_names.get(acc_id, str(acc_id)) if accession_names else str(acc_id)
        )

        for view_idx in selected_views:
            image_filename = f"{view_idx}.jpg"
            frame_num = scan_view_counter.get(scan_id, 0)
            scan_view_counter[scan_id] = frame_num + 1

            output_filename = (
                f"{acc_name}_{scan_row['plant_qr_code']}"
                f"_age{scan_row['plant_age_days']}_{frame_num}.jpg"
            )
            rows.append(
                {
                    "scan_id": scan_id,
                    "plant_qr_code": scan_row["plant_qr_code"],
                    "plant_age_days": scan_row["plant_age_days"],
                    "accession_id": acc_id,
                    "accession_name": acc_name,
                    "wave_number": scan_row["wave_number"],
                    "view_index": view_idx,
                    "frame_index": frame_num,
                    "source_scan_path": str(scan_path),
                    "source_image": str(scan_path / image_filename),
                    "output_filename": output_filename,
                }
            )

    manifest = pd.DataFrame(rows, columns=list(MANIFEST_COLUMNS))
    manifest.to_csv(output_csv, index=False)
    logger.info("Wrote %d rows to %s", len(manifest), output_csv)
    return manifest
