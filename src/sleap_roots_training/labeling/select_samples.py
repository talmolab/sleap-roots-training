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

#: The columns this step reads out of Bloom's ``scans.csv``. Checked up front so a
#: renamed or absent column reports as one named error rather than as a bare ``KeyError``
#: from wherever it is first indexed — ``cli.py`` catches ``OSError``/``ValueError``, so an
#: unvalidated column reaches the operator as a traceback instead of a message.
SCANS_REQUIRED_COLUMNS = (
    "scan_id",
    "plant_qr_code",
    "plant_age_days",
    "accession_id",
    "wave_number",
    "scan_path",
)

#: Columns that key the stratification and the curated filename. A null in either is fatal
#: rather than dropped: ``groupby`` defaults to ``dropna=True``, so a plant with a blank
#: ``accession_id`` would leave the sampling pool with no error and no log line, and the
#: plants that go missing are not a random subset — typically a whole accession or wave
#: whose Bloom record is stale. ``plant_qr_code`` is not listed because the QC join above
#: already excludes a scan with no barcode: it cannot match a cleaned plant, so it is never
#: in the pool to be silently dropped from.
GROUPING_COLUMNS = ("plant_age_days", "accession_id")


def posix_path(path: object) -> PurePosixPath:
    """Normalize a manifest or ``scans.csv`` path to the portable POSIX form.

    Public and shared with the copy step, which resolves what this writes (blocking review
    of #40). Selection had its own inlined copy of this rule and the copy step had another,
    which is a duplication of exactly the bug class the two of them exist to fix: a
    manifest written on the vault's Windows machine carries backslash separators that do
    not resolve anywhere else, and the manifest travels inside the package (Decision 3), so
    it outlives the machine that wrote it.

    Args:
        path: A path as written by either producer, possibly with backslash separators from
            a Windows run or a ``./`` prefix from the legacy Bloom CLI.

    Returns:
        The normalized path. ``PurePosixPath`` collapses a leading ``./``.
    """
    return PurePosixPath(str(path).replace("\\", "/"))


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
    if "Barcode" in cleaned.columns:
        return "Barcode"
    if "plant_qr_code" not in cleaned.columns:
        raise ValueError(
            "the QC-cleaned table has no plant-barcode column: expected 'Barcode' (the "
            "name the QC pipeline renames it to) or 'plant_qr_code', found "
            f"{sorted(cleaned.columns)}. Without it there is no way to say which plants "
            "passed QC."
        )
    return "plant_qr_code"


def _accession_key(accession_id: object) -> str:
    """Return the string an accession id is looked up and named by.

    One rule, so the coverage check and the curated filename cannot disagree. A whole
    number is rendered without a trailing ``.0``: one null anywhere in the column types
    it ``float64``, and the difference between ``"111"`` and ``"111.0"`` is a map that
    stops matching and a package whose every filename changed.

    Args:
        accession_id: The raw cell value.

    Returns:
        The normalized key.
    """
    if isinstance(accession_id, float) and accession_id.is_integer():
        return str(int(accession_id))
    return str(accession_id)


def _assert_accession_names_cover(
    scans_clean: pd.DataFrame, accession_names: Mapping[str, str]
) -> None:
    """Fail if a supplied accession map does not name every accession being selected.

    Deviation (blocking review of #40). Selection used to fall back to ``str(acc_id)`` for
    an unmapped id — the exact fallback :mod:`render_readme` refuses at build time, calling
    it a package that "documents its genotypes as numbers". So an incomplete map was
    accepted here, carried into every curated filename, and only rejected three stages
    later; completing the map then renamed every file in the package, which is the
    comparability break the naming rules exist to avoid.

    Omitting the map entirely stays legal — the numeric ids are a deliberate choice, and
    the caller is warned. Supplying a partial one is not: it means the Bloom lookup
    (design.md F2) was started and not finished.

    Args:
        scans_clean: The QC-filtered scan rows.
        accession_names: The caller's map, keyed by accession id as a string.

    Raises:
        ValueError: If any accession in the selection pool is unmapped.
    """
    present = {_accession_key(value) for value in scans_clean["accession_id"].unique()}
    unmapped = sorted(present - set(accession_names))
    if unmapped:
        raise ValueError(
            f"--accession-names does not cover accession id(s) {unmapped}; it maps "
            f"{sorted(accession_names)}. The name goes into every curated filename, so an "
            "unmapped id would be labeled with its number and the whole package would have "
            "to be renamed once the lookup is finished. Accession names are looked up from "
            "Bloom by hand, so a partial map means the lookup is incomplete."
        )


def _assert_scans_columns(scans: pd.DataFrame, scans_csv: Path) -> None:
    """Fail if ``scans.csv`` lacks a column selection reads.

    Args:
        scans: The loaded ``scans.csv``.
        scans_csv: Its path, for the error message.

    Raises:
        ValueError: If any required column is absent, naming the missing columns.
    """
    absent = [c for c in SCANS_REQUIRED_COLUMNS if c not in scans.columns]
    if absent:
        raise ValueError(
            f"{scans_csv} is not a Bloom scans.csv: missing column(s) "
            f"{', '.join(absent)}. Selection reads every one of "
            f"{', '.join(SCANS_REQUIRED_COLUMNS)}."
        )


def _assert_no_null_grouping_keys(scans_clean: pd.DataFrame) -> None:
    """Fail if any QC-clean scan is missing a key that stratification or naming needs.

    Deviation (blocking review of #40). ``groupby`` defaults to ``dropna=True``, so a row
    with a null ``accession_id`` was excluded from its group and therefore from the
    sampling pool — no error, no warning, and a manifest that reports success while
    covering fewer accessions than the operator asked for. The documented Phase 0 recipe
    in ``.claude/commands/build-labeling-package.md`` produces exactly this null: it
    left-joins a fresh Bloom accession map onto the scan table, so every plant the map
    does not cover arrives here with a blank id.

    A null ``plant_age_days`` is fatal for a second reason: one of them types the whole
    column ``float64``, and the curated filename then reads ``age3.0`` for *every* row in
    the package, breaking comparability with the published collections over one bad cell.

    Args:
        scans_clean: The QC-filtered scan rows.

    Raises:
        ValueError: If any grouping column holds a null, naming the column, the count, and
            an example scan.
    """
    for column in GROUPING_COLUMNS:
        null_rows = scans_clean[scans_clean[column].isna()]
        if null_rows.empty:
            continue
        examples = sorted(str(sid) for sid in null_rows["scan_id"].head(5))
        raise ValueError(
            f"{len(null_rows)} QC-clean scan(s) have no {column!r} (for example scan_id "
            f"{', '.join(examples)}). Selection stratifies on "
            f"{', '.join(GROUPING_COLUMNS)} and names every curated file from them, so a "
            "null would drop those plants from the sampling pool without saying so. Fix "
            "the upstream record — most often an accession map that does not cover every "
            "plant — rather than letting the package under-represent them."
        )


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
    the *plant* dimension monotone by construction. It also removes the dependency on
    ``scans.csv`` row order and on pandas' RNG, so the same *content* selects the same
    plants.

    Monotone here means "against the same pool". The prefix is of a sorted order over the
    barcodes present, so adding plants to ``scans.csv`` re-sorts it: 10 plants at
    ``plants_per_group=3`` and seed 42 give ``['P00','P08','P09']``, and the same call
    after 5 more land gives ``['P08','P09','P10']`` — not a superset. That is why the
    package records the ``scans.csv`` hash (:class:`~...metadata.Provenance`), and it is
    also why Decision 6's recovery path rests on ``output_filename`` naming the view rather
    than on any superset property (design.md "F3 revisited").

    Args:
        plant_qr_codes: The group's plant barcodes; duplicates are ignored.
        plants_per_group: Maximum plants to select. A group smaller than this is taken
            whole.
        seed: Selection seed.

    Returns:
        The selected barcodes, in selection order.
    """
    if not isinstance(plants_per_group, int) or plants_per_group < 1:
        raise ValueError(
            f"plants_per_group is {plants_per_group!r}; it counts plants, so it must be a "
            "positive integer. The prefix slice this ends in gives Python's semantics to a "
            "bad value rather than rejecting it: zero selects nothing and a negative "
            "number drops that many plants from the end of every group, both silently."
        )
    unique = sorted({str(code) for code in plant_qr_codes})
    ordered = sorted(unique, key=lambda code: _plant_order_key(code, seed))
    return ordered[:plants_per_group]


def select_view_indices(
    views_per_plant: int, total_views: int = TOTAL_VIEWS
) -> list[int]:
    """Return the 1-based view indices to label, spread evenly over the rotation.

    Views are stepped uniformly from index 1, so the selection covers the whole cylinder
    at every count: three views are ``[1, 25, 49]`` (120 degrees apart), four are
    ``[1, 19, 37, 55]`` (90 degrees apart).

    Deviation (blocking review of #40). Task 2.7 replaced this uniform step with greedy
    farthest-point dispersion, to buy the nesting property Decision 6's widen-and-republish
    path wanted — every count a subset of every larger one. Greedy dispersion on a circle
    is only *uniform* at powers of two, and the shipped default is not one: it gave
    ``[1, 19, 37]``, which is 0/90/180 degrees, so views 38-72 — half the cylinder — never
    contributed ground truth. That is a worse defect than the one it fixed. It also broke
    view geometry against the eight published label collections, which were selected with
    this uniform step, undercutting the "new packages extend the existing corpus" rationale.

    Nesting is not the property that makes widening safe, and buying it here cost coverage.
    What makes widening safe is that ``output_filename`` names the *view*, not its position
    in the selection, so a frame keeps its identity whether or not the view sets nest. That
    guarantee now lives in :func:`select_samples`, and monotonicity is taken from the plant
    dimension alone (:func:`select_plants`), where a prefix of a stable order gives it for
    free and costs nothing.

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

    # Scaled per index rather than a fixed `total_views // views_per_plant` step. The fixed
    # step truncates, and the truncation accumulates into the *last* arc: at 72 views, 25
    # views gave `[1, 3, ..., 49]` and never sampled 50-72, and 37 gave `[1..37]` — 175°
    # unsampled. That is the same half-cylinder defect this function was rewritten to fix,
    # reintroduced at a different parameter (blocking review of #40, second pass). Scaling
    # each index keeps every circular gap within one view of every other, at every count.
    return [
        1 + (index * total_views) // views_per_plant for index in range(views_per_plant)
    ]


def select_samples(
    cleaned_csv: Path,
    scans_csv: Path,
    output_csv: Path,
    accession_names: Optional[Mapping[object, str]] = None,
    plants_per_group: int = 5,
    views_per_plant: int = 3,
    seed: int = 42,
    total_views: int = TOTAL_VIEWS,
) -> pd.DataFrame:
    r"""Select a stratified sample from QC-cleaned scans across age x accession.

    Selection is deterministic: the same inputs and parameters yield the same frames.
    Widening ``plants_per_group`` yields a superset of the narrower selection; widening
    ``views_per_plant`` re-spaces the views evenly over the rotation, so it adds frames
    without keeping every earlier one. What holds across every width is that a given
    ``output_filename`` always names the same view of the same plant, which is what
    Decision 6's re-derive-and-republish path actually needs.

    Args:
        cleaned_csv: Path to ``10_final_data.csv`` from sleap-roots-analyze QC output.
            May be a single file or a glob pattern matching multiple group files.
        scans_csv: Path to ``scans.csv`` from a Bloom download (for image path info).
        output_csv: Path to write ``sample_manifest.csv``.
        accession_names: Optional mapping of ``accession_id`` to name, from the Bloom
            database. Keys are compared as strings, so an id read as an int from a CSV and
            one written as a string in a JSON map both resolve — the two entry points used
            to coerce differently, so a non-numeric id worked for one and raised for the
            other. When supplied it must cover every accession in the pool; when omitted
            the numeric id is used and the caller is warned.
        plants_per_group: Plants to sample per age x accession group.
        views_per_plant: Rotational views per plant.
        seed: Selection seed for reproducibility.
        total_views: Rotational views present in one scan.

    Returns:
        The manifest, one row per selected frame.

    Raises:
        ValueError: If a count parameter is not positive, if the view parameters are out
            of range, if a required column is absent, if a grouping key is null, if the
            QC pool and ``scans.csv`` share no barcode, if a supplied accession map is
            incomplete, if the selection is empty, or if two frames would be given
            colliding ``output_filename``\\ s.
    """
    names = (
        None
        if accession_names is None
        else {str(key): str(value) for key, value in accession_names.items()}
    )
    cleaned = _load_cleaned(Path(cleaned_csv))
    clean_barcodes = {str(code) for code in cleaned[_barcode_column(cleaned)].unique()}
    logger.info(
        "QC-cleaned data: %d samples, %d unique plants",
        len(cleaned),
        len(clean_barcodes),
    )

    scans = pd.read_csv(scans_csv)
    _assert_scans_columns(scans, Path(scans_csv))
    logger.info("Full scans.csv: %d scans", len(scans))

    # Compared as strings on both sides. A barcode column read as int64 from one CSV and
    # as object from the other is a dtype skew that silently intersects to nothing, which
    # is one of the two documented ways to reach an empty pool.
    scans_clean = scans[scans["plant_qr_code"].astype(str).isin(clean_barcodes)].copy()
    logger.info(
        "After QC filter: %d scans from %d plants",
        len(scans_clean),
        scans_clean["plant_qr_code"].nunique(),
    )
    if scans_clean.empty:
        raise ValueError(
            f"no scan in {scans_csv} names a plant that passed QC: {len(scans)} scan(s) "
            f"and {len(clean_barcodes)} QC-clean barcode(s) have zero barcodes in common. "
            "An empty pool selects nothing, and a package with no frames reports success "
            "at every later stage (design.md F1). The usual cause is a --cleaned-csv glob "
            "matching a different wave than this scans.csv describes."
        )
    _assert_no_null_grouping_keys(scans_clean)
    if names is None:
        logger.warning(
            "No accession names supplied: every curated filename will carry the numeric "
            "accession id instead of the genotype name, which is not what the published "
            "collections look like. Supplying the map later renames every file in the "
            "package, so look it up in Bloom now if you mean to have it."
        )
    else:
        _assert_accession_names_cover(scans_clean, names)

    # Validate the view parameters before any selection work, so a bad view count fails
    # on its own terms rather than as a strange manifest.
    selected_views = select_view_indices(views_per_plant, total_views)
    logger.info("Selected view indices: %s", selected_views)

    # Each group keeps only *its own* rows for the plants it selected (deviation, blocking
    # review of #40, second pass). The selections used to be unioned into one flat set and
    # then applied to the whole table by barcode, so a plant selected in (age 3, accession
    # A) dragged in every scan it had at every other age — whether or not (age 7, accession
    # A) had selected it. When the plant set is identical at every age that is a no-op,
    # which is why it went unnoticed; when it is not — dropout, staggered waves, a plant
    # that failed QC at one age only — both groups inflate, and the plants double-counted
    # are exactly the ones present in more groups. That is survivorship, and survivorship
    # correlates with vigor, so the label set skewed toward healthy plants while the README
    # and the metadata both reported the *requested* plants_per_group.
    sampled: list[pd.DataFrame] = []
    realized: dict[tuple, int] = {}
    for group_key, group in scans_clean.groupby(list(GROUPING_COLUMNS)):
        selected = select_plants(group["plant_qr_code"], plants_per_group, seed)
        realized[group_key] = len(selected)
        sampled.append(group[group["plant_qr_code"].astype(str).isin(selected)])
    df_sampled = pd.concat(sampled).sort_index()

    # Realized counts, not the requested one. A group smaller than the request is taken
    # whole and that is legitimate, but nothing reported it — so "5 plants per group" in
    # the README was a request presented as a result.
    short_groups = {key: n for key, n in realized.items() if n < plants_per_group}
    logger.info(
        "Selected %d plant(s) across %d age x accession group(s)",
        sum(realized.values()),
        len(realized),
    )
    if short_groups:
        listed = ", ".join(
            f"(age {key[0]}, accession {key[1]}): {n}"
            for key, n in sorted(short_groups.items())[:5]
        )
        more = f" ... and {len(short_groups) - 5} more" if len(short_groups) > 5 else ""
        logger.warning(
            "%d of %d group(s) hold fewer than the %d plant(s) requested and were taken "
            "whole: %s%s. The package is smaller and less balanced than the parameters "
            "suggest.",
            len(short_groups),
            len(realized),
            plants_per_group,
            listed,
            more,
        )

    rows = []
    # Frame numbering is a per-scan counter, so it indexes views *within* a scan.
    scan_view_counter: dict[int, int] = {}

    for _, scan_row in df_sampled.iterrows():
        # Deviation (task 7j): the vault script used `Path`, so a manifest written on the
        # vault's Windows machine carried backslash separators that do not resolve here.
        # Normalizing to POSIX makes the manifest portable, which matters because the
        # manifest travels inside the package (Decision 3) and outlives the machine.
        # The rule itself lives in `posix_path`, which the copy step also resolves paths
        # with — it was inlined here, a second copy of exactly the bug class this change is
        # otherwise careful to centralize (blocking review of #40).
        scan_path = posix_path(scan_row["scan_path"])
        scan_id = scan_row["scan_id"]
        acc_id = scan_row["accession_id"]
        acc_key = _accession_key(acc_id)
        acc_name = acc_key if names is None else names[acc_key]

        # Nulls are already rejected, so the age is a whole number; `int` keeps a column
        # that pandas typed `float64` for an unrelated reason from writing `age3.0`.
        age = int(scan_row["plant_age_days"])

        for view_idx in selected_views:
            image_filename = f"{view_idx}.jpg"
            frame_num = scan_view_counter.get(scan_id, 0)
            scan_view_counter[scan_id] = frame_num + 1

            # Deviation (blocking review of #40). The name used to embed `frame_num` — the
            # frame's *position* in this selection — so which image a given name referred
            # to depended on how many views the run asked for: `..._1.jpg` was view 19 at
            # `views_per_plant=3` and view 10 at 5. Decision 6's recovery path is exactly
            # "re-derive wider and republish", and filename is the only key the package
            # offers a labeler's corrections, so that silently attached one view's root
            # traces to another view's pixels. Naming the view makes a frame's identity
            # independent of the selection that produced it — the same view is the same
            # file in every package, and a view that was not selected before is simply a
            # new file. `frame_index` stays the within-scan position, because it indexes
            # into the scan's video (`build_package._scan_frame_order`).
            output_filename = (
                f"{acc_name}_{scan_row['plant_qr_code']}"
                f"_age{age}_view{view_idx:03d}.jpg"
            )
            rows.append(
                {
                    "scan_id": scan_id,
                    "plant_qr_code": scan_row["plant_qr_code"],
                    "plant_age_days": age,
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

    # No empty-manifest check here: the two ways to reach one are both rejected above, by
    # name and with the actual cause. A QC pool sharing no barcode with `scans.csv` fails
    # at the filter, and a non-positive `plants_per_group` fails in `select_plants` — so a
    # check at this point could only ever restate one of them, and would be a guard no test
    # can reach.
    manifest = pd.DataFrame(rows, columns=list(MANIFEST_COLUMNS))
    assert_unique_output_filenames(manifest)
    manifest.to_csv(output_csv, index=False)
    logger.info("Wrote %d rows to %s", len(manifest), output_csv)
    return manifest


def _assert_output_filenames_are_bare(manifest: pd.DataFrame) -> None:
    r"""Fail if any ``output_filename`` is anything other than a plain filename.

    Deviation (blocking review of #40). ``output_filename`` is interpolated from
    ``accession_name`` — hand-pasted by the operator (design.md F2) — and from
    ``plant_qr_code``, copied verbatim out of Bloom; the copy step then hands it straight
    to ``shutil.copy2(src, output_dir / output_filename)``, which resolves separators. An
    accession name of ``../../pwn``, or a barcode carrying a space and a slash, therefore
    wrote curated images *outside* the staging directory — where ``shutil.rmtree`` on the
    failure path could not remove them, defeating :mod:`package`'s "nothing lands until
    everything passes". A one-level ``..`` that happens to land back inside staging let
    the build complete with images outside ``images/`` entirely.

    :mod:`metadata` already validates ``experiment`` against a slug pattern, with the
    docstring "It becomes part of a filename, so anything a shell or a filesystem treats
    specially is rejected at construction." The principle was in the codebase; it just was
    not applied to the two fields that actually vary per package.

    Characters a filesystem reserves are rejected too, not only separators: an accession
    like ``PI:594301`` copies fine on the Linux pod that builds the package and raises
    ``OSError`` on the Windows machine that opens it, which is the delivery target.

    Args:
        manifest: The assembled manifest.

    Raises:
        ValueError: If any ``output_filename`` contains a path separator, a ``..``
            segment, a reserved character, or is otherwise not a bare filename.
    """
    offenders: dict[str, str] = {}
    for name in sorted({str(value) for value in manifest["output_filename"]}):
        if name in ("", ".", ".."):
            reason = "is empty or a directory reference"
        elif "/" in name or "\\" in name:
            reason = "contains a path separator"
        elif set(name) & set('<>:"|?*'):
            reason = "contains a character Windows reserves in filenames"
        elif name != Path(name).name:
            reason = "is not a bare filename"
        else:
            continue
        offenders[name] = reason
    if not offenders:
        return
    listed = "; ".join(
        f"{name!r} {reason}" for name, reason in list(offenders.items())[:5]
    )
    more = f" ... and {len(offenders) - 5} more" if len(offenders) > 5 else ""
    raise ValueError(
        f"{len(offenders)} output_filename value(s) are not plain filenames: "
        f"{listed}{more}. output_filename is joined onto the package's images directory "
        "and copied there, so a separator or a '..' writes outside the package — past the "
        "staging directory that is supposed to make a failed build leave nothing behind. "
        "It is built from accession_name and plant_qr_code, so fix whichever of those "
        "carries the character rather than the manifest."
    )


def assert_unique_output_filenames(manifest: pd.DataFrame) -> None:
    r"""Fail if two frames were assigned the same curated filename.

    Public because the copy step calls it too (task 3.5): a hand-edited manifest can
    reach that step without passing through selection, and the collision is invisible
    once ``shutil.copy2`` has absorbed it. The check belongs with the manifest writer,
    so both callers enforce one rule rather than two that can drift.

    ``output_filename`` is built from ``(accession_name, plant_qr_code, plant_age_days,
    view_index)``, so uniqueness holds
    only while each ``(plant_qr_code, plant_age_days)`` pair maps to one scan
    (design.md F6). Nothing downstream notices when it does not: the copy step's
    ``shutil.copy2`` overwrites silently and still counts every call, and the builder
    then points two scans' labels at one image — a wrong package that looks healthy.

    Task 0.8 settled that a repeated pair is an artifact of the upstream record rather
    than a legitimate replicate, so this fails loudly and names the scans instead of
    disambiguating. Disambiguating would rename every curated file — breaking
    comparability with the eight published collections — to accommodate a state that
    should not exist, and would hide a record somebody needs to go fix.

    Uniqueness is judged **case-insensitively** (deviation, blocking review of #40). The
    check used to be byte-exact, so two hand-typed accession names differing only in case
    (``WEEP-1-4`` and ``Weep-1-4``) were "unique" here and then collided on macOS's and
    Windows' case-insensitive filesystems: the copy step reported every call it made and
    left one fewer file on disk, which is precisely the design.md F5 silent partial copy
    this step claims to have eliminated. The same manifest built a good package on the
    Linux pod and a short one on the labeler's Mac.

    Args:
        manifest: The assembled manifest.

    Raises:
        ValueError: If any ``output_filename`` is not a plain filename, or if two frames
            are given names that collide, naming the colliding filenames and the
            ``scan_id``\\ s that produced them.
    """
    _assert_output_filenames_are_bare(manifest)

    folded = manifest["output_filename"].astype(str).str.casefold()
    duplicated = manifest[folded.duplicated(keep=False)]
    if duplicated.empty:
        return
    groups = list(duplicated.groupby(folded[duplicated.index]))
    collisions = "; ".join(
        f"{sorted(set(group['output_filename']))} from scan_ids "
        f"{sorted(set(group['scan_id']))}"
        for _, group in groups
    )
    case_only = any(len(set(group["output_filename"])) > 1 for _, group in groups)
    if case_only:
        raise ValueError(
            f"output_filename is not unique across the manifest once case is folded: "
            f"{collisions}. These names differ only in case, so they are distinct here "
            "and the same file on macOS and Windows — the package would build correctly "
            "on Linux and lose a frame wherever it is opened. Accession names are pasted "
            "by hand (design.md F2); make the spelling consistent."
        )
    raise ValueError(
        f"output_filename is not unique across the manifest: {collisions}. "
        "Two scans share a (plant_qr_code, plant_age_days) pair, which indicates a "
        "duplicate record upstream in Bloom rather than a real replicate — fix the "
        "record rather than renaming the frames."
    )
