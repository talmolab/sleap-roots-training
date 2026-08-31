"""Command-line interface for ``sleap-roots-training``."""

from pathlib import Path
from typing import Optional

import click
from omegaconf import OmegaConf

from sleap_roots_training import __version__
from sleap_roots_training import backend
from sleap_roots_training import config as training_config
from sleap_roots_training.registry import cards, chooser, config, lineage, publish
from sleap_roots_training.registry.models import resolve_model_dir


@click.group()
@click.version_option(version=__version__, prog_name="sleap-roots-training")
def main() -> None:
    """Config-driven training and evaluation of SLEAP root models.

    ``validate`` and ``emit`` are base-install safe, so a config can be authored and
    checked anywhere; ``run`` chains validate -> emit -> ``sleap-nn train`` on a host that
    also has the ``train`` extra installed. Subcommands are added as the pipeline is built
    out tier by tier (see the program roadmap).
    """


def _require_api_key() -> None:
    """Fail fast (as a clean CLI error) if no wandb credential is resolvable.

    A credential is resolvable via ``WANDB_API_KEY`` or a netrc entry for
    ``api.wandb.ai`` written by ``wandb login``.
    """
    try:
        config.require_api_key()
    except RuntimeError as error:
        raise click.ClickException(str(error))


@main.command(name="seed-registry")
@click.option(
    "--models-root",
    type=click.Path(path_type=Path),
    default=None,
    help="Directory of <model_id>.zip archives (required unless --verify).",
)
@click.option(
    "--selection-matrix",
    # dir_okay=False: `exists=True` alone accepts a directory, which then reaches
    # `OmegaConf.load` and fails as an I/O error deep in the loader. Rejecting it here
    # names the actual mistake ("is a directory") at the argument that made it.
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Selection matrix YAML (defaults to the packaged matrix).",
)
@click.option(
    "--execute", is_flag=True, help="Actually publish (default is a dry run)."
)
@click.option(
    "--yes", is_flag=True, help="Skip the confirmation prompt under --execute."
)
@click.option(
    "--force", is_flag=True, help="Re-publish and re-point the production alias."
)
@click.option(
    "--only",
    multiple=True,
    help=(
        "Restrict validation + publishing to these collection ids (canary). "
        "Under --verify this also SUPPRESSES orphan reporting, since every "
        "collection outside the scope would otherwise be reported as an orphan."
    ),
)
@click.option("--verify", is_flag=True, help="Read-only: check the live registry.")
@click.pass_context
def seed_registry_command(
    ctx: click.Context,
    models_root: Optional[Path],
    selection_matrix: Optional[Path],
    execute: bool,
    yes: bool,
    force: bool,
    only: tuple,
    verify: bool,
) -> None:
    """Seed (or verify) the production model registry from the selection matrix.

    By default this is a dry run: it prints the planned collections + metadata and
    resolves every model directory without contacting wandb. Pass ``--execute`` to
    publish (which checks ``WANDB_API_KEY``, then confirms the target unless ``--yes``).
    ``--verify`` re-runs the consumer read path against the live registry. ``--only``
    scopes every mode to the named collection(s) for canary seeding.
    """
    cfg = config.resolve_registry_config()
    # The loader's messages are carefully row-numbered ("row 0: unknown mode 'teacup'
    # (expected one of [...])") and the spec promises them to operators — but raw they
    # reach the terminal as an unhandled traceback with the message buried in it. Wrap
    # into a ClickException the way the resolve step below already does. Newly
    # load-bearing: a future upstream narrowing of `Mode` hands exactly this error to
    # every operator running `seed-registry`.
    #
    # ValueError alone is the whole set on purpose: the loader normalizes every way the
    # file can be unusable (unreadable, not YAML, not a mapping) into ValueError naming
    # the path, so the wrapping is complete without listing I/O and parse types here --
    # a list that was both incomplete (three reachable types escaped it) and dead in its
    # one named member, since click intercepts a nonexistent path before this runs.
    try:
        matrix = chooser.load_selection_matrix(selection_matrix)
        all_cards = cards.expand_rows_to_cards(matrix.rows)
    except ValueError as error:
        raise click.ClickException(str(error))

    # --only scopes ALL modes (dry-run, --verify, --execute); validate up front so an
    # unknown id fails fast with a clean message and the confirm/plan reflect the scope.
    if only:
        only_set = set(only)
        unknown = only_set - {cards.collection_id(card) for card in all_cards}
        if unknown:
            raise click.UsageError(
                f"--only names unknown collection(s): {sorted(unknown)}"
            )
        all_cards = [c for c in all_cards if cards.collection_id(c) in only_set]
    ids = [cards.collection_id(card) for card in all_cards]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise click.UsageError(f"duplicate collection ids in the matrix: {duplicates}")
    expected = sorted(ids)

    if verify:
        _require_api_key()
        # `--only` scopes `expected` above, so orphan reporting has to be suppressed
        # under it: otherwise a one-collection canary reports every OTHER collection
        # in the registry as orphaned.
        report = publish.verify_registry(cfg, expected, report_orphans=not only)
        for collection in report["present"]:
            click.echo(f"present: {collection}")
        for collection in report["missing"]:
            click.echo(f"missing: {collection}")
        for collection in report["legacy"]:
            click.echo(
                f"LEGACY METADATA: {collection} (an upgraded consumer cannot read it)"
            )
        for collection in report["orphans"]:
            click.echo(
                f"orphan: {collection} (production-aliased, no longer in the matrix)"
            )
        for collection in report["indeterminate"]:
            click.echo(f"indeterminate: {collection} (could not read its aliases)")
        if report["orphans_suppressed"]:
            click.echo(
                "note: orphan reporting is suppressed under --only; "
                "run --verify without --only for the orphan report."
            )
        # Orphans and indeterminate collections are reported, not acted on, and do not
        # fail: an orphan is expected for the whole migration window.
        if publish.verify_failed(report):
            ctx.exit(1)
        return

    if models_root is None:
        raise click.UsageError("--models-root is required (unless --verify)")

    if not execute:
        click.echo("DRY RUN — no wandb calls; pass --execute to publish.")
        for card in all_cards:
            collection = cards.collection_id(card)
            pinned = (models_root / f"{card.source_model_id}.zip").is_file()
            try:
                resolve_model_dir(card.source_model_id, models_root, matrix.checksums)
                # An unpinned already-unzipped dir resolves here but --execute rejects
                # it; label it so a dry-run "ok" is not false confidence.
                status = (
                    "ok"
                    if pinned
                    else "ok — UNPINNED dir; --execute requires the .zip archive"
                )
            except (FileNotFoundError, ValueError) as error:
                status = f"MISSING ({error})"
            click.echo(f"{collection}  {cards.card_to_metadata(card)}  [{status}]")
        return

    _require_api_key()  # fail fast before the confirmation prompt.
    if not yes:
        click.confirm(
            f"Publish {len(all_cards)} cards to {cfg.entity} / {cfg.registry} "
            f"(alias '{cfg.alias}')?",
            abort=True,
        )

    # Validate that every card resolves (filesystem, no network) BEFORE creating a
    # run — a resolution error fails fast and cleanly, minting no empty wandb run.
    try:
        resolved = publish.resolve_all(all_cards, models_root, matrix.checksums)
    except (FileNotFoundError, ValueError) as error:
        raise click.ClickException(str(error))

    import wandb

    lineage_config = lineage.build_lineage(chooser.matrix_sha256(selection_matrix))
    if lineage_config["git_dirty"]:
        click.echo(
            "WARNING: working tree is dirty; the recorded matrix content hash "
            "pins the exact inputs regardless."
        )
    run = wandb.init(job_type="seed_registry", config=lineage_config)
    # `seed_registry` echoes each collection's outcome as it happens, so a failure
    # partway through still leaves the operator a local record of which collections
    # now carry `production` — the summary below is never reached if something
    # propagates out of the seed.
    try:
        report = publish.seed_registry(resolved, cfg, run, force=force)
    except ValueError as error:
        raise click.ClickException(str(error))
    finally:
        run.finish()
    click.echo(f"published ({len(report['published'])}): {report['published']}")
    click.echo(f"skipped ({len(report['skipped'])}): {report['skipped']}")
    if report["stale"]:
        click.echo(
            f"STALE metadata on already-seeded ({len(report['stale'])}): {report['stale']}"
        )
    if report["failed"]:
        click.echo(f"FAILED ({len(report['failed'])}): {report['failed']}")
    if report["failed"] or report["stale"]:
        ctx.exit(1)


@main.command(name="validate")
@click.argument("config_path", type=click.Path(exists=True, path_type=Path))
def validate_command(config_path: Path) -> None:
    """Validate a training config file (CONFIG_PATH) against the schema.

    Runs the experiment-metadata, explicit-seed, and W&B-enablement checks, and — when the
    optional ``train`` extra is installed — delegates deep validation to ``sleap-nn``.
    Prints a success line and exits 0 when the config conforms; prints a clear, field-named
    error and exits non-zero otherwise.
    """
    try:
        cfg = training_config.load_config(config_path)
        notes = training_config.validate_config(cfg)
    except training_config.ConfigError as error:
        raise click.ClickException(str(error))
    for note in notes:
        click.echo(f"note: {note}")
    if notes:
        # Deep sleap-nn validation was skipped (no train extra) — don't imply a full pass.
        click.echo(
            f"OK: {config_path} passed base checks (deep sleap-nn validation skipped; "
            "install the 'train' extra to validate the backend config)"
        )
    else:
        click.echo(f"OK: {config_path} is valid")


@main.command(name="emit")
@click.argument("config_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the sleap-nn config here (default: stdout).",
)
def emit_command(config_path: Path, output: Optional[Path]) -> None:
    """Emit the sleap-nn-native config from CONFIG_PATH (``experiment`` block stripped).

    Validates CONFIG_PATH, then writes the config to pass to ``sleap-nn train --config``:
    sleap-nn's struct-mode config rejects the repo-owned ``experiment`` key, so it is
    removed. Works without the ``train`` extra, so you can author + validate + emit on one
    machine and train on another. Exits non-zero with a clear error if the config is invalid.
    """
    try:
        cfg = training_config.load_config(config_path)
        training_config.validate_config(cfg)
    except training_config.ConfigError as error:
        raise click.ClickException(str(error))
    sleap_nn_yaml = training_config.to_sleap_nn_yaml(cfg)
    if output is None:
        click.echo(sleap_nn_yaml, nl=False)
        return
    try:
        # newline="\n" is explicit, not incidental: the default (newline=None) translates
        # every "\n" to os.linesep, so the same config emits CRLF on Windows -- the platform
        # the target GPU box runs (docs/training-backend.md) -- and LF everywhere else. That
        # makes the emitted bytes host-dependent, which breaks byte-comparison of one config
        # against another (the `run` command relies on it, and the deferred content hashing
        # in #10/#11 would too).
        output.write_text(sleap_nn_yaml, encoding="utf-8", newline="\n")
    except OSError as error:
        raise click.ClickException(f"could not write {output}: {error}")
    click.echo(f"wrote sleap-nn config to {output}")


@main.group(name="labeling")
def labeling_group() -> None:
    """Build the labeling packages that seed the label registry.

    The four stages of the ``/build-labeling-package`` workflow, in order: ``select`` a
    stratified sample from QC-cleaned scans, ``copy-images`` to gather them under curated
    names, ``build`` the package, and ``validate`` one you have been handed. ``build``
    runs every stage itself and is the normal path; the two stage commands exist because
    the workflow doc drives them separately when a step needs to be re-run in isolation.
    """


def _labeling_error(error: Exception) -> click.ClickException:
    """Wrap a labeling-stage failure as a CLI error.

    Every stage in :mod:`sleap_roots_training.labeling` reports by raising ``ValueError``
    or ``OSError`` with a message written for the person who ran the command — naming the
    row, the path, or the parameter. Unwrapped they arrive as a traceback with that
    message buried in it.

    ``KeyError`` is caught too, as a backstop (blocking review of #40). The stages now
    validate their input columns up front, so a missing column arrives as a named
    ``ValueError``; but every stage indexes a DataFrame somewhere, and a raw ``KeyError``
    escaping here is precisely the traceback this function exists to prevent. Its ``str``
    is a bare quoted key, so it is labeled rather than printed alone.

    Args:
        error: The stage's exception.

    Returns:
        The click exception to raise.
    """
    if isinstance(error, KeyError):
        return click.ClickException(
            f"missing key {error} — the input is missing a column or field this stage "
            "reads. Check that the CSV is the one this stage expects and that its header "
            "has not been renamed."
        )
    return click.ClickException(str(error))


def _parse_accessions(value: str) -> dict:
    """Parse the ``--accessions`` mapping, from JSON or from ``@path``.

    The map is the output of a hand-run Bloom query (design.md F2), so it arrives as
    something a person pasted. ``@path`` exists because pasting JSON into a shell is how a
    quote goes missing.

    Args:
        value: A JSON object, or ``@`` followed by a path to one.

    Returns:
        The mapping of accession id to name, with string keys.

    Raises:
        click.ClickException: If it is unreadable or is not an object of scalars.
    """
    import json

    text = value
    if value.startswith("@"):
        try:
            text = Path(value[1:]).read_text(encoding="utf-8")
        except OSError as error:
            raise click.ClickException(f"--accessions: could not read file: {error}")
    try:
        parsed = json.loads(text)
    except ValueError as error:
        raise click.ClickException(
            f"--accessions is not valid JSON: {error}. Expected a mapping of accession "
            'id to name, e.g. \'{"12742739": "A3244"}\', or @path to a file holding one.'
        )
    if not isinstance(parsed, dict):
        raise click.ClickException(
            f"--accessions is a {type(parsed).__name__}, expected a JSON object mapping "
            "accession id to name."
        )
    return {str(key): str(name) for key, name in parsed.items()}


@labeling_group.command(name="select")
@click.option(
    "--cleaned-csv",
    required=True,
    help="QC-cleaned `10_final_data.csv`; may be a glob over per-age-group files.",
)
@click.option(
    "--scans-csv",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="`scans.csv` from the Bloom download.",
)
@click.option(
    "--output-csv",
    required=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Where to write `sample_manifest.csv`.",
)
# `IntRange(min=1)` rather than `int`: these count things, and a zero or negative
# value used to reach `ordered[:n]` and silently select nothing, or "all but N"
# plants per group, exiting 0 either way (blocking review of #40).
@click.option(
    "--plants-per-group", type=click.IntRange(min=1), default=5, show_default=True
)
@click.option(
    "--views-per-plant", type=click.IntRange(min=1), default=3, show_default=True
)
@click.option("--seed", type=int, default=42, show_default=True)
@click.option(
    "--total-views",
    type=click.IntRange(min=1),
    default=None,
    help="Rotational views per scan (default: the packaged assumption).",
)
@click.option(
    "--accession-names",
    default=None,
    help="JSON map of accession id to name, or @path to a file holding one.",
)
def labeling_select_command(
    cleaned_csv: str,
    scans_csv: Path,
    output_csv: Path,
    plants_per_group: int,
    views_per_plant: int,
    seed: int,
    total_views: Optional[int],
    accession_names: Optional[str],
) -> None:
    """Select a stratified sample of frames and write the manifest.

    Deterministic: the same inputs and parameters select the same frames. Widening
    ``--plants-per-group`` yields a superset; widening ``--views-per-plant`` re-spaces the
    views evenly, so it adds frames without keeping every old one — but a curated filename
    always names the same view, so a re-derived package still merges. Record the
    parameters — ``build`` writes them into the package so it can be widened later.
    """
    from sleap_roots_training.labeling import select_samples

    names = _parse_accessions(accession_names) if accession_names else None
    try:
        manifest = select_samples.select_samples(
            Path(cleaned_csv),
            scans_csv,
            output_csv,
            accession_names=names,
            plants_per_group=plants_per_group,
            views_per_plant=views_per_plant,
            seed=seed,
            total_views=(
                select_samples.TOTAL_VIEWS if total_views is None else total_views
            ),
        )
    except (OSError, ValueError, KeyError) as error:
        raise _labeling_error(error)
    click.echo(
        f"selected {len(manifest)} frame(s) across "
        f"{manifest['plant_qr_code'].nunique()} plant(s) -> {output_csv}"
    )


@labeling_group.command(name="copy-images")
@click.option(
    "--manifest",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="`sample_manifest.csv` from `labeling select`.",
)
@click.option(
    "--scans-csv",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="The `scans.csv` the manifest was selected from; its directory is the base "
    "every `source_image` resolves against.",
)
@click.option(
    "--output-dir",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Destination `images/` directory.",
)
@click.option(
    "--total-views",
    type=click.IntRange(min=1),
    default=None,
    help="Views the scans hold.",
)
def labeling_copy_images_command(
    manifest: Path, scans_csv: Path, output_dir: Path, total_views: Optional[int]
) -> None:
    """Gather every manifest row's source image under its curated name.

    All-or-nothing: every row resolves before anything is written, so a partial ``images/``
    is never left behind to be mistaken for a complete one.
    """
    from sleap_roots_training.labeling import copy_images, select_samples

    try:
        copied = copy_images.copy_selected_images(
            manifest,
            scans_csv,
            output_dir,
            total_views=(
                select_samples.TOTAL_VIEWS if total_views is None else total_views
            ),
        )
    except (OSError, ValueError, KeyError) as error:
        raise _labeling_error(error)
    click.echo(f"copied {copied} image(s) -> {output_dir}")


@labeling_group.command(name="build")
@click.option(
    "--manifest",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="`sample_manifest.csv` from `labeling select`.",
)
@click.option(
    "--scans-csv",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="The `scans.csv` the manifest was selected from.",
)
@click.option(
    "--predictions-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="The pipeline's `sleap_roots_traits_input/` directory.",
)
@click.option(
    "--output-dir",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Where to write the package. Must not already exist.",
)
@click.option("--species", required=True, help="Crop (e.g. soybean).")
@click.option("--mode", required=True, help="Capture mode (e.g. cylinder).")
@click.option("--experiment", required=True, help="Experiment slug (e.g. weep).")
@click.option(
    "--root-type",
    "root_types",
    multiple=True,
    required=True,
    help="Root type to build a project for; repeat for several.",
)
@click.option(
    "--bloom-experiment-id",
    required=True,
    type=int,
    help="The Bloom experiment the scans came from.",
)
@click.option(
    "--accessions",
    required=True,
    help="JSON map of accession id to name, or @path to a file holding one.",
)
@click.option("--seed", type=int, required=True, help="The seed selection ran with.")
@click.option("--plants-per-group", type=click.IntRange(min=1), required=True)
@click.option("--views-per-plant", type=click.IntRange(min=1), required=True)
@click.option("--total-views", type=click.IntRange(min=1), required=True)
@click.option("--version", default="v000", show_default=True)
def labeling_build_command(
    manifest: Path,
    scans_csv: Path,
    predictions_dir: Path,
    output_dir: Path,
    species: str,
    mode: str,
    experiment: str,
    root_types: tuple,
    bloom_experiment_id: int,
    accessions: str,
    seed: int,
    plants_per_group: int,
    views_per_plant: int,
    total_views: int,
    version: str,
) -> None:
    """Build a complete, validated labeling package.

    Runs the copy, build, metadata, README, and validation steps and moves the result into
    ``--output-dir`` only once all of them pass — a failed build writes nothing.

    The selection parameters are required, not defaulted: they are recorded in the package
    so it can be re-derived and widened later, and a default that silently disagreed with
    the run that produced the manifest would make those instructions wrong.
    """
    from sleap_roots_training.labeling.metadata import (
        PackageMetadata,
        SelectionParameters,
    )
    from sleap_roots_training.labeling.package import build_labeling_package

    accession_map = _parse_accessions(accessions)
    try:
        metadata = PackageMetadata(
            species=species,
            mode=mode,
            experiment=experiment,
            root_types=tuple(root_types),
        )
        selection = SelectionParameters(
            seed=seed,
            plants_per_group=plants_per_group,
            views_per_plant=views_per_plant,
            total_views=total_views,
        )
        package_dir = build_labeling_package(
            manifest,
            scans_csv,
            predictions_dir,
            output_dir,
            metadata,
            bloom_experiment_id=bloom_experiment_id,
            accessions=accession_map,
            selection=selection,
            version=version,
        )
    except (OSError, ValueError, KeyError) as error:
        raise _labeling_error(error)

    from sleap_roots_training.labeling.metadata import read_package_metadata
    from sleap_roots_training.labeling.layout import project_filename_for

    record = read_package_metadata(package_dir)
    click.echo(f"built labeling package: {package_dir}")
    click.echo(f"  {record.frame_count} frames, {len(record.accessions)} accession(s)")
    for root_type in record.metadata.root_types:
        click.echo(
            f"  {project_filename_for(record, root_type)} "
            f"({len(record.skeletons[root_type])} nodes)"
        )


@labeling_group.command(name="validate")
@click.argument(
    "package_dir", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
def labeling_validate_command(package_dir: Path) -> None:
    """Check PACKAGE_DIR is a publishable labeling package.

    The layout, the manifest's columns, the counts, the recorded skeletons, and the embed
    guarantee. Reads nothing outside the directory, so a delivered package validates where
    it lands rather than only where it was built — this is the check ``publish-labels``
    runs before any upload.
    """
    from sleap_roots_training.labeling.validate import validate_package

    try:
        record = validate_package(package_dir)
    except (OSError, ValueError, KeyError) as error:
        raise _labeling_error(error)
    click.echo(
        f"OK: {package_dir} is a valid labeling package "
        f"({record.metadata.species} / {record.metadata.experiment}, "
        f"{record.frame_count} frames, "
        f"{', '.join(record.metadata.root_types)})"
    )


def _warn_on_dataset_mismatch(cfg) -> None:
    """Note when the recorded dataset identity is not what the backend will actually read.

    ``run`` promotes ``experiment.dataset.path`` into the published lineage record, so a config
    where it disagrees with ``data_config.train_labels_path`` produces a ``source_config.yaml``
    that faithfully records the wrong dataset. Pre-existing in ``validate``, but this is the
    command that makes the field load-bearing, so it is the command that should say something.
    A note rather than a refusal: the two are not required to be equal (a packaged split can
    legitimately differ), and failing a run over it would be a step too far.

    Args:
        cfg: A loaded training config.
    """
    dataset = OmegaConf.select(cfg, "experiment.dataset.path", default=None)
    train_paths = (
        OmegaConf.select(cfg, "data_config.train_labels_path", default=None) or []
    )
    if isinstance(train_paths, str):
        train_paths = [train_paths]
    if (
        dataset
        and train_paths
        and str(dataset) not in [str(path) for path in train_paths]
    ):
        click.echo(
            f"note: experiment.dataset.path ({dataset}) is not among "
            f"data_config.train_labels_path ({[str(p) for p in train_paths]}); "
            "source_config.yaml will record the former as this run's dataset identity"
        )


@main.command(name="run")
@click.argument(
    "config_path", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option(
    "--resolved-config",
    # dir_okay=False for the same reason --selection-matrix has it: a directory would
    # otherwise reach the writer and surface as a raw IsADirectoryError.
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Stage the emitted config here instead of in the run directory.",
)
@click.pass_context
def run_command(
    ctx: click.Context, config_path: Path, resolved_config: Optional[Path]
) -> None:
    """Validate CONFIG_PATH, stage it, and run ``sleap-nn train`` on it.

    The one-command path for a host that has **both** this package and the ``train``
    extra installed (the GPU box). ``validate`` and ``emit`` are unchanged and remain
    base-install safe, so the author-here / train-there workflow still uses them.

    Two configs are written into ``<trainer_config.ckpt_dir>/<trainer_config.run_name>/``
    before training starts: ``emitted_config.yaml`` (what ``sleap-nn`` is given) and
    ``source_config.yaml`` (what you wrote, ``experiment`` block included -- the identity
    no ``sleap-nn`` artifact records). The backend's own output streams live, and its exit
    status is this command's exit status.
    """
    # Step order is the contract (see the change's design.md D6): every step that can fail
    # cheaply runs before any step with a side effect, so a failure here leaves nothing
    # written and no subprocess started. A stale config beside a run that never happened
    # is indistinguishable later from a real one.
    try:
        binary = backend.resolve_sleap_nn()
    except backend.BackendError as error:
        raise click.ClickException(str(error))

    try:
        cfg = training_config.load_config(config_path)
        notes = training_config.validate_config(cfg)
    except training_config.ConfigError as error:
        raise click.ClickException(str(error))
    for note in notes:
        # Resolving the console script does NOT mean `sleap_nn` is importable here (it may
        # come from another environment entirely), so deep validation can still be skipped.
        # Say so rather than let an operator assume a multi-hour run was fully checked.
        click.echo(f"note: {note}")

    try:
        # Every gate below reads through OmegaConf, which *resolves*, while the emitted config is
        # written unresolved and with the `experiment` block stripped. Reconcile the two before
        # anything is staged, or `run_name: ${experiment.species}_v1` would gate and stage under
        # a value the backend can never resolve.
        backend.check_emitted_config_resolvable(cfg)
        backend.reject_inline_api_key(cfg)
        wandb_on = backend.wandb_enabled(cfg)
    except backend.BackendError as error:
        raise click.ClickException(str(error))
    _warn_on_dataset_mismatch(cfg)
    if wandb_on:
        # Every committed baseline example sets use_wandb; without a resolvable credential
        # the run dies hours in, at wandb.init(). Fail now instead.
        _require_api_key()

    try:
        run_dir = backend.run_directory(cfg)
        backend.check_run_directory(run_dir)
        destination = backend.resolved_config_path(run_dir, resolved_config)
        backend.stage_artifacts(cfg, config_path, run_dir, destination)
    except backend.BackendError as error:
        raise click.ClickException(str(error))

    # Echo the resolved backend before a multi-hour run: this is the only signal that the
    # interpreter-first search picked a different environment than the operator expected.
    version = backend.backend_version(binary)
    click.echo(f"backend: {binary}" + (f" ({version})" if version else ""))
    # Absolute: with a relative or drive-relative `ckpt_dir`, the printed path is the only clue
    # about where the files actually went, and a bare relative path is no clue at all.
    click.echo(f"config:  {destination.resolve()}")
    click.echo(f"run dir: {run_dir.resolve()}")
    try:
        outcome = backend.run_backend(backend.build_argv(binary, destination))
    except backend.BackendError as error:
        # The backend can fail to *launch* (a truncated wheel, a PATHEXT hit on something that
        # is not executable) after the artifacts are staged. Those stay on disk deliberately --
        # they record what was attempted -- but the failure is still a clean CLI error.
        raise click.ClickException(str(error))
    if outcome.note:
        click.echo(outcome.note, err=True)
    if outcome.exit_code != 0:
        ctx.exit(outcome.exit_code)
    # Name what was actually written. Hard-coding both constants told the operator that both
    # files were in the run directory even when --resolved-config had put one elsewhere.
    click.echo(
        f"OK: training finished; {run_dir.resolve()} holds {backend.SOURCE_CONFIG_NAME}, "
        f"emitted config at {destination.resolve()}"
    )


if __name__ == "__main__":  # pragma: no cover
    main()
