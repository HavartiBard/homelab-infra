from click.testing import CliRunner
from bench.cli import cli


def test_cli_shows_version():
    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "bench, version" in result.output


def test_cli_lists_subcommands():
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    for sub in ("run", "validate", "list"):
        assert sub in result.output
