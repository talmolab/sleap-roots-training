"""Command-line interface for ``sleap-roots-training``."""

import click

from sleap_roots_training import __version__


@click.group()
@click.version_option(version=__version__, prog_name="sleap-roots-training")
def main() -> None:
    """Config-driven training and evaluation of SLEAP root models.

    Subcommands are added as the pipeline is built out tier by tier (see the
    program roadmap). Run ``sleap-roots-training --help`` to list them.
    """


if __name__ == "__main__":  # pragma: no cover
    main()
