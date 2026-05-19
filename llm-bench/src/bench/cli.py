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
@click.option("--pre-warm/--no-pre-warm", default=False,
              help="Send a 1-token request to llama-swap before the first "
                   "probe so the model is loaded and TTFT measurements aren't "
                   "inflated by the initial 30-90s model-load time")
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
    pre_warm: bool,
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
        pre_warm=pre_warm,
    )

    click.echo(f"Run {record.run_uuid} complete — status: {record.status}")
    if record.warm_time_sec is not None:
        click.echo(f"Pre-warm: {record.warm_time_sec:.1f}s")
    if record.error:
        click.echo(f"Errors: {record.error}")
    click.echo(f"Scores: {record.scores}")


@cli.command()
@click.option("--catalog-root", type=click.Path(exists=True, path_type=Path),
              help="Path to benchmarks root (validates capabilities/ + suites/)")
def validate(catalog_root: Path | None):
    """Validate the capability catalog and suite definitions."""
    from .catalog import load_catalog, load_suite

    if catalog_root is None:
        raise click.UsageError("--catalog-root required")

    capabilities = load_catalog(catalog_root)
    suites_dir = catalog_root / "suites"
    if not suites_dir.is_dir():
        raise click.ClickException(f"No suites/ directory at {catalog_root}")

    suite_paths = sorted(suites_dir.glob("*.yml"))
    suites = [load_suite(p) for p in suite_paths]

    # Validate every suite's capability references resolve
    errors: list[str] = []
    for suite in suites:
        for cap_id in suite.capabilities:
            if cap_id not in capabilities:
                errors.append(f"suite '{suite.id}' references missing capability '{cap_id}'")

    click.echo(f"✓ {len(capabilities)} capabilities loaded")
    click.echo(f"✓ {len(suites)} suites loaded ({', '.join(s.id for s in suites)})")
    if errors:
        for e in errors:
            click.echo(f"✗ {e}", err=True)
        raise click.ClickException(f"{len(errors)} validation error(s)")


@cli.command(name="list")
@click.option("--catalog-root", type=click.Path(exists=True, path_type=Path),
              help="Path to benchmarks root — lists capabilities + suites")
@click.option("--base-url", envvar="BENCH_BASE_URL", default=None,
              help="If provided, also list models exposed by the llama-swap proxy")
@click.option("--api-key", default="", envvar="BENCH_API_KEY",
              help="API key for the llama-swap endpoint")
def list_cmd(catalog_root: Path | None, base_url: str | None, api_key: str):
    """List capabilities, suites, and (optionally) models exposed by the endpoint."""
    if catalog_root is None and base_url is None:
        raise click.UsageError("Pass --catalog-root and/or --base-url")

    if catalog_root is not None:
        from .catalog import load_catalog, load_suite

        capabilities = load_catalog(catalog_root)
        click.echo(f"Capabilities ({len(capabilities)}):")
        for cap_id, cap in sorted(capabilities.items()):
            click.echo(f"  {cap_id:30s}  {cap.probe.type:18s} {cap.name}")

        suites_dir = catalog_root / "suites"
        if suites_dir.is_dir():
            suites = [load_suite(p) for p in sorted(suites_dir.glob("*.yml"))]
            click.echo(f"\nSuites ({len(suites)}):")
            for s in suites:
                click.echo(f"  {s.id:20s}  {len(s.capabilities)} capabilities  ({', '.join(s.capabilities)})")

    if base_url is not None:
        from .llama_swap import LlamaSwapClient
        click.echo(f"\nModels at {base_url}:")
        try:
            client = LlamaSwapClient(base_url, api_key=api_key, timeout=10)
            for m in client.list_models():
                click.echo(f"  {m}")
        except RuntimeError as exc:
            click.echo(f"  (error: {exc})", err=True)
