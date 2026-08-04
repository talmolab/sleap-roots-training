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

import hashlib
import logging
from pathlib import Path, PurePosixPath
from typing import Mapping, Optional

import pandas as pd

logger = logging.getLogger(__name__)

#: Rotational views in a Bloom cylinder scan; images are named ``1.jpg`` .. ``72.jpg``.
#: The vault script hardcoded this with no validation, so an experiment captured at a
#: different view count silently selected wrong indices (design.md F4). It is a default
#: here, not a constant, and selection validates against it (task 2.5). Verifying it
#: against what is actually on disk belongs to the copy step, which is the first stage
#: that touches the filesystem.
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
    # Deviation (task 7): the vault script globbed `parent.glob(name)`, which can only
    # match a wildcard in the *filename*. QC writes one `10_final_data.csv` per age-group
    # *directory*, so the documented layout (`<qc_out>/*/10_final_data.csv`) never
    # resolved — the workflow doc worked around it with a manual `pd.concat` before
    # calling the script. Anchoring at the last wildcard-free component makes the branch
    # express the layout its own logging already assumed.
    parts = cleaned_path.parts
    wild = [i for i, part in enumerate(parts) if any(c in part for c in "*?[")]
    if wild:
        anchor, pattern = Path(*parts[: wild[0]]), str(Path(*parts[wild[0] :]))
    else:
        anchor, pattern = cleaned_path.parent, cleaned_path.name
    files = sorted(anchor.glob(pattern))
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


def _plant_order_key(plant_qr_code: object, seed: int) -> tuple[str, str]:
    """Return the stable sort key that orders one plant within its group.

    Args:
        plant_qr_code: The plant barcode.
        seed: Selection seed; changing it reshuffles the order.

    Returns:
        A ``(digest, barcode)`` key. The digest spreads plants pseudo-randomly so a
        group's selection is not biased by barcode ordering; the barcode breaks ties
        into a total order.
    """
    barcode = str(plant_qr_code)
    digest = hashlib.sha256(f"{seed}:{barcode}".encode()).hexdigest()
    return (digest, barcode)


def select_plants(
    plant_qr_codes: object, plants_per_group: int, seed: int
) -> list[str]:
    """Return the plants to sample from one age x accession group.

    Deviation (task 2.7). The vault script drew with ``.sample(n, random_state=seed)``,
    which is reproducible for a *given* ``n`` but not nested: drawing ten does not return
    the five plus five more, so a widened re-run was a different label set rather than a
    superset (design.md F3). Ordering by a stable key and taking a prefix makes widening
    monotone by construction, which is what Decision 6's re-derive-and-republish recovery
    path rests on. It also removes the dependency on ``scans.csv`` row order and on
    pandas' RNG, so the same *content* selects the same plants.

    Args:
        plant_qr_codes: The group's plant barcodes; duplicates are ignored.
        plants_per_group: Maximum plants to select. A group smaller than this is taken
            whole.
        seed: Selection seed.

    Returns:
        The selected barcodes, in selection order.
    """
    unique = sorted({str(code) for code in plant_qr_codes})
    ordered = sorted(unique, key=lambda code: _plant_order_key(code, seed))
    return ordered[:plants_per_group]


def select_view_indices(
    views_per_plant: int, total_views: int = TOTAL_VIEWS
) -> list[int]:
    """Return the 1-based view indices to label, spread over the rotation.

    Deviation (task 2.7). The vault script computed ``step = total_views //
    views_per_plant`` from index 1, which is monotone only by coincidence: three views
    gave ``[1, 25, 49]`` and four gave ``[1, 19, 37, 55]``, so widening replaced the
    selection instead of extending it (design.md F3). This picks views greedily by
    farthest-point dispersion, which is nested by construction — every count is a prefix
    of every larger one — while still spreading views over the rotation. Distance is
    measured *circularly*, because view ``total_views`` and view ``1`` are adjacent
    angles on a cylinder scan; the linear formula would have paired them as if they were
    the two extremes. Four views are unchanged from the original (``[1, 19, 37, 55]``);
    three become ``[1, 19, 37]``.

    Args:
        views_per_plant: Number of rotational views to select per plant.
        total_views: Views present in one scan.

    Returns:
        The selected 1-based view indices, ascending.

    Raises:
        ValueError: If ``total_views`` is not positive, or ``views_per_plant`` is not
            between 1 and ``total_views``.
    """
    if total_views < 1:
        raise ValueError(f"total_views must be >= 1, got {total_views}")
    if not 1 <= views_per_plant <= total_views:
        raise ValueError(
            f"views_per_plant must be between 1 and total_views ({total_views}), "
            f"got {views_per_plant}"
        )

    chosen = [0]
    while len(chosen) < views_per_plant:
        # Ties resolve to the lowest index, since only a strictly greater distance wins.
        best, best_distance = None, -1
        for candidate in range(total_views):
            if candidate in chosen:
                continue
            distance = min(
                min(abs(candidate - c), total_views - abs(candidate - c))
                for c in chosen
            )
            if distance > best_distance:
                best, best_distance = candidate, distance
        chosen.append(best)
    return sorted(index + 1 for index in chosen)


def select_samples(
    cleaned_csv: Path,
    scans_csv: Path,
    output_csv: Path,
    accession_names: Optional[Mapping[int, str]] = None,
    plants_per_group: int = 5,
    views_per_plant: int = 3,
    seed: int = 42,
    total_views: int = TOTAL_VIEWS,
) -> pd.DataFrame:
    """Select a stratified sample from QC-cleaned scans across age x accession.

    Selection is deterministic and monotone: the same inputs and parameters yield the
    same frames, and widening ``plants_per_group`` or ``views_per_plant`` yields a
    superset of the narrower selection (Decision 5).

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
        seed: Selection seed for reproducibility.
        total_views: Rotational views present in one scan.

    Returns:
        The manifest, one row per selected frame.

    Raises:
        ValueError: If the view parameters are out of range, or if two frames would be
            given the same ``output_filename``.
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

    # Validate the view parameters before any selection work, so a bad view count fails
    # on its own terms rather than as a strange manifest.
    selected_views = select_view_indices(views_per_plant, total_views)
    logger.info("Selected view indices: %s", selected_views)

    sampled_plants = set()
    for group_key, group in scans_clean.groupby(["plant_age_days", "accession_id"]):
        selected = select_plants(group["plant_qr_code"], plants_per_group, seed)
        logger.debug("Group %s: selected %d plants", group_key, len(selected))
        sampled_plants.update(selected)
    logger.info("Selected %d unique plants", len(sampled_plants))

    df_sampled = scans_clean[
        scans_clean["plant_qr_code"].astype(str).isin(sampled_plants)
    ].copy()

    rows = []
    # Frame numbering is a per-scan counter, so it indexes views *within* a scan.
    scan_view_counter: dict[int, int] = {}

    for _, scan_row in df_sampled.iterrows():
        # Deviation (task 7j): the vault script used `Path`, so a manifest written on the
        # vault's Windows machine carried backslash separators that do not resolve here.
        # Normalizing to POSIX makes the manifest portable, which matters because the
        # manifest travels inside the package (Decision 3) and outlives the machine.
        scan_path = PurePosixPath(str(scan_row["scan_path"]).replace("\\", "/"))
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
    assert_unique_output_filenames(manifest)
    manifest.to_csv(output_csv, index=False)
    logger.info("Wrote %d rows to %s", len(manifest), output_csv)
    return manifest


def assert_unique_output_filenames(manifest: pd.DataFrame) -> None:
    r"""Fail if two frames were assigned the same curated filename.

    Public because the copy step calls it too (task 3.5): a hand-edited manifest can
    reach that step without passing through selection, and the collision is invisible
    once ``shutil.copy2`` has absorbed it. The check belongs with the manifest writer,
    so both callers enforce one rule rather than two that can drift.

    ``output_filename`` is built from ``(accession_name, plant_qr_code, plant_age_days,
    frame_index)`` while the frame counter is keyed by ``scan_id``, so uniqueness holds
    only while each ``(plant_qr_code, plant_age_days)`` pair maps to one scan
    (design.md F6). Nothing downstream notices when it does not: the copy step's
    ``shutil.copy2`` overwrites silently and still counts every call, and the builder
    then points two scans' labels at one image — a wrong package that looks healthy.

    Task 0.8 settled that a repeated pair is an artifact of the upstream record rather
    than a legitimate replicate, so this fails loudly and names the scans instead of
    disambiguating. Disambiguating would rename every curated file — breaking
    comparability with the eight published collections — to accommodate a state that
    should not exist, and would hide a record somebody needs to go fix.

    Args:
        manifest: The assembled manifest.

    Raises:
        ValueError: If any ``output_filename`` appears more than once, naming the
            colliding filenames and the ``scan_id``\\ s that produced them.
    """
    duplicated = manifest[manifest.duplicated("output_filename", keep=False)]
    if duplicated.empty:
        return
    collisions = "; ".join(
        f"{name!r} from scan_ids {sorted(set(group['scan_id']))}"
        for name, group in duplicated.groupby("output_filename")
    )
    raise ValueError(
        f"output_filename is not unique across the manifest: {collisions}. "
        "Two scans share a (plant_qr_code, plant_age_days) pair, which indicates a "
        "duplicate record upstream in Bloom rather than a real replicate — fix the "
        "record rather than renaming the frames."
    )
