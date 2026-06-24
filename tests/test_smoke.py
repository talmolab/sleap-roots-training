import sleap_roots_training
from sleap_roots_training import cli


def test_version_present():
    assert sleap_roots_training.__version__


def test_cli_help_runs():
    from click.testing import CliRunner

    result = CliRunner().invoke(cli.main, ["--help"])
    assert result.exit_code == 0
    assert "sleap-roots-training" in result.output.lower() or "config-driven" in (
        result.output.lower()
    )
