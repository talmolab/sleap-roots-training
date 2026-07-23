"""Command-line interface for ``sleap-roots-training``."""

from pathlib import Path
from typing import Optional

import click

from sleap_roots_training import __version__
from sleap_roots_training import config as training_config
from sleap_roots_training.registry import cards, chooser, config, lineage, publish
from sleap_roots_training.registry.models import resolve_model_dir


@click.group()
@click.version_option(version=__version__, prog_name="sleap-roots-training")
def main() -> None:
    """Config-driven training and evaluation of SLEAP root models.

    Subcommands are added as the pipeline is built out tier by tier (see the
    program roadmap). Run ``sleap-roots-training --help`` to list them.
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
    type=click.Path(exists=True, path_type=Path),
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
    help="Restrict validation + publishing to these collection ids (canary).",
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
    matrix = chooser.load_selection_matrix(selection_matrix)
    all_cards = cards.expand_rows_to_cards(matrix.rows)

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
        report = publish.verify_registry(cfg, expected)
        for collection in report["present"]:
            click.echo(f"present: {collection}")
        for collection in report["missing"]:
            click.echo(f"missing: {collection}")
        if report["missing"]:
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
    try:
        report = publish.seed_registry(resolved, cfg, run, force=force)
    except ValueError as error:
        raise click.ClickException(str(error))
    finally:
        run.finish()
    click.echo(f"published ({len(report['published'])}): {report['published']}")
    click.echo(f"skipped ({len(report['skipped'])}): {report['skipped']}")


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
    click.echo(f"OK: {config_path} is valid")


if __name__ == "__main__":  # pragma: no cover
    main()
