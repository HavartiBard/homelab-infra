from __future__ import annotations

import logging
from pathlib import Path

import click

from . import __version__

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@click.group()
@click.version_option(__version__, prog_name="bench")
def cli():
    """LLM endpoint benchmarking — capability catalog + orchestrator + dashboard."""


@cli.command()
@click.option("--base-url", required=True, envvar="BENCH_BASE_URL",
              help="OpenAI-compatible API base URL (e.g. http://host:8010/v1)")
@click.option("--catalog-root", required=True, type=click.Path(exists=True, path_type=Path),
              help="Path to benchmarks root (contains capabilities/ and suites/)")
@click.option("--suite-id", required=True,
              help="Suite id to run (e.g. tier1)")
@click.option("--api-key", default="", envvar="BENCH_API_KEY",
              help="API key for the target endpoint")
@click.option("--model", default=None,
              help="Model id (auto-discovered from /v1/models if omitted)")
@click.option("--runtime", default="unknown",
              help="Runtime label (e.g. llama.cpp, vllm, ollama)")
@click.option("--prom-start", default=None,
              help="ISO-8601 start for Prometheus window queries")
@click.option("--prom-end", default=None,
              help="ISO-8601 end for Prometheus window queries")
@click.option("--runs-path", default=None, type=click.Path(path_type=Path),
              help="JSONL file path for appending run records (default: results/runs.jsonl)")
@click.option("--otlp-endpoint", default=None,
              help="Phoenix OTLP gRPC endpoint (e.g. phoenix:4317)")
@click.option("--quantization", default=None,
              help="Quantization label (e.g. bf16, q4_k_m)")
@click.option("--ctx-length", default=None, type=int,
              help="Context length the model was started with")
@click.option("--notes", default=None,
              help="Freeform notes attached to the run record")
def run(
    base_url: str,
    catalog_root: Path,
    suite_id: str,
    api_key: str,
    model: str | None,
    runtime: str,
    prom_start: str | None,
    prom_end: str | None,
    runs_path: Path | None,
    otlp_endpoint: str | None,
    quantization: str | None,
    ctx_length: int | None,
    notes: str | None,
):
    """Run a benchmark suite against an OpenAI-compatible endpoint."""
    from .runner import run_suite

    if runs_path is None:
        runs_path = Path("results/runs.jsonl")

    record = run_suite(
        base_url=base_url,
        catalog_root=catalog_root,
        suite_id=suite_id,
        api_key=api_key,
        model=model,
        runtime=runtime,
        prom_start=prom_start,
        prom_end=prom_end,
        runs_path=runs_path,
        otlp_endpoint=otlp_endpoint,
        quantization=quantization,
        ctx_length=ctx_length,
        notes=notes,
    )

    click.echo(f"Run {record.run_uuid} complete — status: {record.status}")
    if record.error:
        click.echo(f"Errors: {record.error}")
    click.echo(f"Scores: {record.scores}")


@cli.command()
def validate():
    """Validate the capability catalog and suite definitions."""
    raise click.UsageError("Not yet implemented — see Task 12.")


@cli.command(name="list")
def list_cmd():
    """List capabilities and suites available in the catalog."""
    raise click.UsageError("Not yet implemented — see Task 12.")
