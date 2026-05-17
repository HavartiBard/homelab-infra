import click

from . import __version__


@click.group()
@click.version_option(__version__, prog_name="bench")
def cli():
    """LLM endpoint benchmarking — capability catalog + orchestrator + dashboard."""


@cli.command()
def run():
    """Run a benchmark suite against an OpenAI-compatible endpoint."""
    raise click.UsageError("Not yet implemented — see Task 11.")


@cli.command()
def validate():
    """Validate the capability catalog and suite definitions."""
    raise click.UsageError("Not yet implemented — see Task 11.")


@cli.command(name="list")
def list_cmd():
    """List capabilities and suites available in the catalog."""
    raise click.UsageError("Not yet implemented — see Task 11.")
