from __future__ import annotations

import json as _json
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
@click.option("--db-path", default=None, type=click.Path(path_type=Path),
              envvar="LLM_BENCH_DB_PATH",
              help="DuckDB file path (default: /data/bench.duckdb)")
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
    db_path: Path | None,
    otlp_endpoint: str | None,
    quantization: str | None,
    ctx_length: int | None,
    notes: str | None,
    pre_warm: bool,
):
    """Run a benchmark suite against an OpenAI-compatible endpoint."""
    from .runner import run_suite

    from .db import get_connection

    if db_path is None:
        db_path = Path("/data/bench.duckdb")

    db = get_connection(db_path)
    record = run_suite(
        base_url=base_url,
        catalog_root=catalog_root,
        suite_id=suite_id,
        api_key=api_key,
        model=model,
        runtime=runtime,
        prom_start=prom_start,
        prom_end=prom_end,
        db=db,
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


@cli.group()
def db():
    """Database management commands."""


@db.command(name="migrate")
@click.option("--jsonl-path", default=Path("/data/runs.jsonl"),
              type=click.Path(path_type=Path),
              help="Source JSONL file (default: /data/runs.jsonl)")
@click.option("--db-path", default=Path("/data/bench.duckdb"),
              type=click.Path(path_type=Path),
              envvar="LLM_BENCH_DB_PATH",
              help="Target DuckDB file (default: /data/bench.duckdb)")
@click.option("--mirror-jsonl/--no-mirror-jsonl", default=False,
              help="Enable JSONL mirror writes after migration "
                   "(touches /data/.mirror_jsonl_enabled)")
def db_migrate(jsonl_path: Path, db_path: Path, mirror_jsonl: bool):
    """One-time migration of runs.jsonl into DuckDB."""
    from .db.migrate import migrate_jsonl_to_duckdb

    result = migrate_jsonl_to_duckdb(jsonl_path, db_path)
    if result.already_done:
        click.echo("Migration already done; nothing to do.")
        return
    click.echo(f"migrated {result.migrated} runs (skipped {result.skipped})")
    if mirror_jsonl:
        marker = Path("/data/.mirror_jsonl_enabled")
        marker.touch()
        click.echo(f"JSONL mirroring enabled (marker: {marker})")


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


@cli.group()
def references():
    """Public benchmark reference management."""


_ALL_SOURCES = ("frontier", "hf_v1", "hf_v2", "bigcode", "all")


def _build_fetchers(source: str, frontier_yaml: Path | None):
    """Construct the list of SourceFetcher instances for a `--source` choice."""
    from .references.sources.frontier import FrontierFetcher
    from .references.sources.hf_v1 import HFOpenLLMV1Fetcher
    from .references.sources.hf_v2 import HFOpenLLMV2Fetcher
    from .references.sources.bigcode import BigCodeHumanEvalFetcher

    if frontier_yaml is None:
        # Repo root: <repo>/benchmarks/references/frontier.yml
        # cli.py lives at <repo>/llm-bench/src/bench/cli.py
        frontier_yaml = Path(__file__).resolve().parents[3] / "benchmarks" / "references" / "frontier.yml"

    all_fetchers = {
        "frontier": FrontierFetcher(frontier_yaml),
        "hf_v1": HFOpenLLMV1Fetcher(),
        "hf_v2": HFOpenLLMV2Fetcher(),
        "bigcode": BigCodeHumanEvalFetcher(),
    }
    if source == "all":
        return list(all_fetchers.values())
    return [all_fetchers[source]]


@references.command(name="refresh")
@click.option("--source", default="all",
              type=click.Choice(_ALL_SOURCES, case_sensitive=False),
              help="Which source(s) to refresh")
@click.option("--db-path", default=Path("/data/bench.duckdb"),
              envvar="LLM_BENCH_DB_PATH",
              type=click.Path(path_type=Path))
@click.option("--frontier-yaml", default=None,
              type=click.Path(exists=True, path_type=Path),
              help="Override path to benchmarks/references/frontier.yml")
def references_refresh(source: str, db_path: Path, frontier_yaml: Path | None):
    """Refresh published reference scores."""
    from .db import get_connection
    from .references.importer import refresh

    fetchers = _build_fetchers(source, frontier_yaml)
    db = get_connection(db_path)
    report = refresh(db, fetchers=fetchers)

    for name, count in report.ok_sources.items():
        click.echo(f"[ok] {name}: {count} records")
    for name, err in report.failed_sources.items():
        click.echo(f"[fail] {name}: {err}", err=True)
    if not report.ok_sources and report.failed_sources:
        raise click.ClickException("All sources failed")


@references.command(name="list")
@click.option("--source", default=None,
              type=click.Choice(_ALL_SOURCES[:-1], case_sensitive=False),
              help="Filter to a single source")
@click.option("--db-path", default=Path("/data/bench.duckdb"),
              envvar="LLM_BENCH_DB_PATH",
              type=click.Path(path_type=Path))
@click.option("--format", "fmt", default="table",
              type=click.Choice(["table", "json"]))
def references_list(source: str | None, db_path: Path, fmt: str):
    """List reference rows in the DB."""
    from .db import get_connection

    db = get_connection(db_path)
    sql = "SELECT model_id, source, display_name, as_of FROM refs"
    params: list = []
    if source:
        sql += " WHERE source LIKE ?"
        params = [f"%{source}%"]
    sql += " ORDER BY model_id, source"
    rows = db.execute(sql, params).fetchall()

    if fmt == "json":
        click.echo(_json.dumps(
            [
                {"model_id": r[0], "source": r[1],
                 "display_name": r[2], "as_of": str(r[3])}
                for r in rows
            ],
            indent=2,
        ))
        return

    click.echo(f"{'model_id':<50} {'source':<22} {'as_of':<12}")
    click.echo("-" * 84)
    for r in rows:
        click.echo(f"{r[0]:<50} {r[1]:<22} {str(r[3]):<12}")


@references.command(name="show")
@click.argument("model_id")
@click.option("--db-path", default=Path("/data/bench.duckdb"),
              envvar="LLM_BENCH_DB_PATH",
              type=click.Path(path_type=Path))
def references_show(model_id: str, db_path: Path):
    """Show all sources' scores for a model (substring match allowed)."""
    from .db import get_connection

    db = get_connection(db_path)
    rows = db.execute(
        """
        SELECT model_id, source, display_name,
               arc_challenge_acc, gsm8k_strict_match,
               humaneval_pass1, ifeval_strict_acc,
               citation_url, as_of
        FROM refs
        WHERE model_id LIKE ?
        ORDER BY model_id, source
        """,
        [f"%{model_id}%"],
    ).fetchall()

    if not rows:
        click.echo(f"No references found matching '{model_id}'")
        return

    for r in rows:
        click.echo(f"{r[0]} ({r[1]}, as_of={r[8]})")
        click.echo(f"  arc_challenge_acc:  {r[3]}")
        click.echo(f"  gsm8k_strict_match: {r[4]}")
        click.echo(f"  humaneval_pass1:    {r[5]}")
        click.echo(f"  ifeval_strict_acc:  {r[6]}")
        if r[7]:
            click.echo(f"  citation: {r[7]}")
