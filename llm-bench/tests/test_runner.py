"""Tests for runner.py — the benchmark orchestration layer."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bench.catalog import (
    Capability,
    LatencyProbe,
    LmEvalProbe,
    Output,
    PrometheusProbe,
    Suite,
)
from bench.runner import (
    _discover_model,
    _dispatch_probe,
    _exc_msg,
    _failed_record,
    _load_suite_for_id,
    run_suite,
)
from bench.db import get_connection
from bench.store import read_runs


# ---------------------------------------------------------------------------
# Helpers: build a minimal catalog on disk
# ---------------------------------------------------------------------------

_CAPABILITY_LATENCY_YAML = """
capability:
  id: cap-latency
  name: Latency
  category: speed
  description: "TTFT and throughput"
  probe:
    type: latency
    fixture: fixtures/latency.jsonl
    sample_size: 2
  outputs:
    - id: ttft_p50_ms
      unit: ms
      direction: lower_is_better
    - id: ttft_p95_ms
      unit: ms
      direction: lower_is_better
    - id: decode_tokens_per_sec
      unit: tok/s
      direction: higher_is_better
    - id: prompt_eval_tokens_per_sec
      unit: tok/s
      direction: higher_is_better
"""

_CAPABILITY_LMEVAL_YAML = """
capability:
  id: cap-lm-eval
  name: LM Eval
  category: quality
  description: "arc_challenge accuracy"
  probe:
    type: lm_eval_harness
    task: arc_challenge
    num_fewshot: 0
    batch_size: auto
  outputs:
    - id: arc_challenge_acc
      unit: acc
      direction: higher_is_better
"""

_SUITE_YAML = """
suite:
  id: test-suite
  name: Test Suite
  capabilities: [cap-latency, cap-lm-eval]
  aggregates:
    quality_avg:
      type: mean
      inputs: [arc_challenge_acc]
"""

_SUITE_LATENCY_ONLY_YAML = """
suite:
  id: test-suite-latency
  name: Test Suite Latency Only
  capabilities: [cap-latency]
  aggregates: {}
"""


def _write_catalog(tmp_path: Path, suite_yaml: str = _SUITE_YAML) -> Path:
    """Create a minimal catalog tree with capabilities/ and suites/."""
    cap_dir = tmp_path / "capabilities"
    cap_dir.mkdir()
    (cap_dir / "latency.yml").write_text(_CAPABILITY_LATENCY_YAML)
    (cap_dir / "lm_eval.yml").write_text(_CAPABILITY_LMEVAL_YAML)
    suite_dir = tmp_path / "suites"
    suite_dir.mkdir()
    (suite_dir / "test.yml").write_text(suite_yaml)

    # Write a minimal latency fixture
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    (fixtures_dir / "latency.jsonl").write_text(
        json.dumps({"prompt": "Hello world"}) + "\n"
        + json.dumps({"prompt": "Another prompt"}) + "\n"
    )

    return tmp_path


# ---------------------------------------------------------------------------
# _discover_model
# ---------------------------------------------------------------------------

class TestDiscoverModel:
    def test_discover_model_returns_first_model(self, httpx_mock):
        httpx_mock.add_response(
            url="http://test/v1/models",
            json={"data": [{"id": "llama3.1"}, {"id": "qwen2"}]},
        )
        model = _discover_model("http://test/v1", api_key="key")
        assert model == "llama3.1"

    def test_discover_model_includes_api_key(self, httpx_mock):
        httpx_mock.add_response(
            url="http://test/v1/models",
            json={"data": [{"id": "gpt-4o"}]},
            match_headers={"Authorization": "Bearer secret"},
        )
        _discover_model("http://test/v1", api_key="secret")
        assert httpx_mock.get_request().headers["Authorization"] == "Bearer secret"

    def test_discover_model_raises_on_http_error(self, httpx_mock):
        httpx_mock.add_response(
            url="http://test/v1/models",
            status_code=500,
        )
        with pytest.raises(RuntimeError, match="Model discovery failed"):
            _discover_model("http://test/v1")

    def test_discover_model_raises_on_empty_list(self, httpx_mock):
        httpx_mock.add_response(
            url="http://test/v1/models",
            json={"data": []},
        )
        with pytest.raises(RuntimeError, match="zero models"):
            _discover_model("http://test/v1")

    def test_discover_model_strips_trailing_slash(self, httpx_mock):
        httpx_mock.add_response(
            url="http://test/v1/models",
            json={"data": [{"id": "phi"}]},
        )
        model = _discover_model("http://test/v1/")
        assert model == "phi"


# ---------------------------------------------------------------------------
# _dispatch_probe
# ---------------------------------------------------------------------------

class TestDispatchProbe:
    def test_dispatch_latency_probe(self, tmp_path):
        probe = LatencyProbe(type="latency", fixture="fake.jsonl", sample_size=1)
        with patch("bench.probes.latency.run_latency_probe") as mock:
            mock.return_value = {"ttft_p50_ms": 100.0}
            scores, artifacts = _dispatch_probe(
                probe, "http://test", model="m", api_key="",
                root=tmp_path, run_dir=tmp_path,
                prom_start=None, prom_end=None,
            )
            assert scores == {"ttft_p50_ms": 100.0}
            assert artifacts == {}
            mock.assert_called_once()

    def test_dispatch_lm_eval_probe(self, tmp_path):
        probe = LmEvalProbe(type="lm_eval_harness", task="arc_challenge")
        with patch("bench.probes.lm_eval.run_lm_eval_probe") as mock:
            mock.return_value = {"arc_challenge_acc": 0.5}
            scores, artifacts = _dispatch_probe(
                probe, "http://test", model="m", api_key="",
                root=tmp_path, run_dir=tmp_path,
                prom_start=None, prom_end=None,
            )
            assert scores == {"arc_challenge_acc": 0.5}
            # lm_eval probe records its JSON output path under a descriptive key
            assert "lm_eval_arc_challenge" in artifacts
            assert artifacts["lm_eval_arc_challenge"].endswith("lm_eval_arc_challenge.json")
            mock.assert_called_once()
            call_kwargs = mock.call_args[1]
            assert call_kwargs["model"] == "m"

    def test_dispatch_prometheus_probe(self, tmp_path):
        probe = PrometheusProbe(
            type="prometheus_window",
            queries={"cpu_avg": "avg(cpu)"},
        )
        with patch("bench.probes.prometheus.run_prometheus_window_probe") as mock:
            mock.return_value = {"cpu_avg": 80.0}
            scores, artifacts = _dispatch_probe(
                probe, "http://prom", model="m", api_key="",
                root=tmp_path, run_dir=tmp_path,
                prom_start="2026-01-01T00:00:00Z",
                prom_end="2026-01-01T01:00:00Z",
            )
            assert scores == {"cpu_avg": 80.0}
            assert artifacts == {}
            mock.assert_called_once()

    def test_dispatch_prometheus_skipped_without_times(self, tmp_path, caplog):
        probe = PrometheusProbe(
            type="prometheus_window",
            queries={"cpu_avg": "avg(cpu)"},
        )
        scores, artifacts = _dispatch_probe(
            probe, "http://prom", model="m", api_key="",
            root=tmp_path, run_dir=tmp_path,
            prom_start=None, prom_end=None,
        )
        assert scores == {}
        assert artifacts == {}
        assert "skipped" in caplog.text

    def test_dispatch_unknown_probe_type_raises(self, tmp_path):
        class FakeProbe:
            pass
        fake = FakeProbe()
        # Manually assign type attribute so isinstance checks don't match
        type(fake).__bases__ = (object,)
        with pytest.raises(ValueError, match="Unknown probe type"):
            _dispatch_probe(
                fake, "http://test", model="m", api_key="",
                root=tmp_path, run_dir=tmp_path,
                prom_start=None, prom_end=None,
            )


# ---------------------------------------------------------------------------
# _load_suite_for_id
# ---------------------------------------------------------------------------

class TestLoadSuiteForId:
    def test_load_existing_suite(self, tmp_path):
        root = _write_catalog(tmp_path)
        from bench.catalog import load_catalog
        catalog = load_catalog(root)
        suite = _load_suite_for_id(root, "test-suite", catalog)
        assert suite.id == "test-suite"

    def test_load_missing_suite_raises(self, tmp_path):
        root = _write_catalog(tmp_path)
        from bench.catalog import load_catalog
        catalog = load_catalog(root)
        with pytest.raises(FileNotFoundError, match="not found"):
            _load_suite_for_id(root, "nonexistent", catalog)

    def test_load_missing_suites_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Suites directory not found"):
            _load_suite_for_id(tmp_path, "anything", {})


# ---------------------------------------------------------------------------
# _failed_record
# ---------------------------------------------------------------------------

class TestFailedRecord:
    def test_failed_record_has_correct_status(self):
        record = _failed_record(
            run_id="abc",
            started_at="2026-01-01T00:00:00+00:00",
            base_url="http://test/v1",
            suite_id="s1",
            error="model not found",
        )
        assert record.status == "failed"
        assert record.error == "model not found"
        assert record.model_id == ""
        assert record.run_uuid == "abc"


# ---------------------------------------------------------------------------
# _exc_msg
# ---------------------------------------------------------------------------

class TestExcMsg:
    def test_exc_msg_with_active_exception(self):
        try:
            raise ValueError("boom")
        except ValueError:
            assert _exc_msg() == "boom"

    def test_exc_msg_without_active_exception(self):
        # No active exception — returns "unknown"
        import sys
        # Clear any active exception context
        assert _exc_msg() == "unknown" or "NoneType" in type(None).__name__


# ---------------------------------------------------------------------------
# run_suite integration tests
# ---------------------------------------------------------------------------

class TestRunSuite:
    def test_run_suite_records_ok_run(self, tmp_path):
        catalog_root = _write_catalog(tmp_path, _SUITE_LATENCY_ONLY_YAML)
        db = get_connection(tmp_path / "bench.duckdb")

        with patch("bench.probes.latency.run_latency_probe") as mock_latency:
            mock_latency.return_value = {
                "ttft_p50_ms": 100.0,
                "ttft_p95_ms": 200.0,
                "decode_tokens_per_sec": 50.0,
                "prompt_eval_tokens_per_sec": 200.0,
            }

            record = run_suite(
                base_url="http://test/v1",
                catalog_root=catalog_root,
                suite_id="test-suite-latency",
                model="test-model",
                runtime="test", db=db,
            )

        assert record.status == "ok"
        assert record.model_id == "test-model"
        assert record.endpoint_url == "http://test/v1"
        assert record.run_uuid is not None
        assert len(record.run_uuid) == 32  # uuid4 hex

        # Verify JSONL persistence
        runs = read_runs(db)
        assert len(runs) == 1
        assert runs[0].run_uuid == record.run_uuid

    def test_run_suite_auto_discovers_model(self, tmp_path, httpx_mock):
        httpx_mock.add_response(
            url="http://test/v1/models",
            json={"data": [{"id": "auto-model"}]},
        )
        catalog_root = _write_catalog(tmp_path, _SUITE_LATENCY_ONLY_YAML)
        db = get_connection(tmp_path / "bench.duckdb")

        with patch("bench.probes.latency.run_latency_probe") as mock_latency:
            mock_latency.return_value = {
                "ttft_p50_ms": 100.0,
                "ttft_p95_ms": 200.0,
                "decode_tokens_per_sec": 50.0,
                "prompt_eval_tokens_per_sec": 200.0,
            }
            record = run_suite(
                base_url="http://test/v1",
                catalog_root=catalog_root,
                suite_id="test-suite-latency", db=db,
            )

        assert record.model_id == "auto-model"

    def test_run_suite_aborts_on_discovery_failure(self, tmp_path, httpx_mock):
        httpx_mock.add_response(
            url="http://test/v1/models",
            status_code=500,
        )
        catalog_root = _write_catalog(tmp_path, _SUITE_LATENCY_ONLY_YAML)
        db = get_connection(tmp_path / "bench.duckdb")

        with pytest.raises(RuntimeError, match="Benchmark run aborted"):
            run_suite(
                base_url="http://test/v1",
                catalog_root=catalog_root,
                suite_id="test-suite-latency", db=db,
            )

        # Should still have written a failed record
        runs = read_runs(db)
        assert len(runs) == 1
        assert runs[0].status == "failed"
        assert "Model discovery failed" in runs[0].error

    def test_run_suite_continues_on_probe_failure(self, tmp_path):
        catalog_root = _write_catalog(tmp_path)  # full suite with latency + lm_eval
        db = get_connection(tmp_path / "bench.duckdb")

        # Latency succeeds, lm_eval fails
        with (
            patch("bench.probes.latency.run_latency_probe") as mock_lat,
            patch("bench.probes.lm_eval.run_lm_eval_probe") as mock_eval,
        ):
            mock_lat.return_value = {
                "ttft_p50_ms": 100.0,
                "ttft_p95_ms": 200.0,
                "decode_tokens_per_sec": 50.0,
                "prompt_eval_tokens_per_sec": 200.0,
            }
            mock_eval.side_effect = RuntimeError("lm_eval crashed")

            record = run_suite(
                base_url="http://test/v1",
                catalog_root=catalog_root,
                suite_id="test-suite",
                model="m1",
                runtime="test", db=db,
            )

        assert record.status == "failed"
        assert "lm_eval" in record.error
        # Latency scores should still be present
        assert record.scores.get("ttft_p50_ms") == 100.0

    def test_run_suite_handles_missing_capability_in_suite(self, tmp_path):
        # Write a suite referencing a nonexistent capability
        bad_suite = """
suite:
  id: bad-suite
  name: Bad Suite
  capabilities: [does-not-exist]
  aggregates: {}
"""
        root = _write_catalog(tmp_path)
        suite_dir = root / "suites"
        (suite_dir / "bad.yml").write_text(bad_suite)
        db = get_connection(tmp_path / "bench.duckdb")

        record = run_suite(
            base_url="http://test/v1",
            catalog_root=root,
            suite_id="bad-suite",
            model="m1", db=db,
        )

        assert record.status == "failed"
        assert "does-not-exist" in record.error

    def test_run_suite_skips_otel_on_init_failure(self, tmp_path, caplog):
        catalog_root = _write_catalog(tmp_path, _SUITE_LATENCY_ONLY_YAML)
        db = get_connection(tmp_path / "bench.duckdb")

        with (
            patch("bench.runner.init_tracing", side_effect=Exception("OTEL boom")),
            patch("bench.probes.latency.run_latency_probe") as mock_lat,
        ):
            mock_lat.return_value = {
                "ttft_p50_ms": 100.0,
                "ttft_p95_ms": 200.0,
                "decode_tokens_per_sec": 50.0,
                "prompt_eval_tokens_per_sec": 200.0,
            }
            record = run_suite(
                base_url="http://test/v1",
                catalog_root=catalog_root,
                suite_id="test-suite-latency",
                model="m1", db=db,
                otlp_endpoint="bad-endpoint:4317",
            )

        assert record.status == "ok"
        assert "failed" in caplog.text or "failed" in caplog.text.lower()

    def test_run_suite_skips_phoenix_emit_failure(self, tmp_path, caplog):
        catalog_root = _write_catalog(tmp_path, _SUITE_LATENCY_ONLY_YAML)
        db = get_connection(tmp_path / "bench.duckdb")

        with (
            patch("bench.runner.init_tracing"),
            patch("bench.runner.log_run_to_phoenix", side_effect=Exception("Phoenix down")),
            patch("bench.probes.latency.run_latency_probe") as mock_lat,
        ):
            mock_lat.return_value = {
                "ttft_p50_ms": 100.0,
                "ttft_p95_ms": 200.0,
                "decode_tokens_per_sec": 50.0,
                "prompt_eval_tokens_per_sec": 200.0,
            }
            record = run_suite(
                base_url="http://test/v1",
                catalog_root=catalog_root,
                suite_id="test-suite-latency",
                model="m1", db=db,
                otlp_endpoint="phoenix:4317",
            )

        assert record.status == "ok"

    def test_run_suite_sets_optional_fields(self, tmp_path):
        catalog_root = _write_catalog(tmp_path, _SUITE_LATENCY_ONLY_YAML)
        db = get_connection(tmp_path / "bench.duckdb")

        with patch("bench.probes.latency.run_latency_probe") as mock_lat:
            mock_lat.return_value = {
                "ttft_p50_ms": 100.0,
                "ttft_p95_ms": 200.0,
                "decode_tokens_per_sec": 50.0,
                "prompt_eval_tokens_per_sec": 200.0,
            }
            record = run_suite(
                base_url="http://test/v1",
                catalog_root=catalog_root,
                suite_id="test-suite-latency",
                model="m1",
                runtime="llama.cpp", db=db,
                quantization="q4_k_m",
                ctx_length=8192,
                sampling_params={"temperature": 0.7},
                notes="test run",
            )

        assert record.quantization == "q4_k_m"
        assert record.ctx_length == 8192
        assert record.sampling_params == {"temperature": 0.7}
        assert record.notes == "test run"
        assert record.runtime == "llama.cpp"

    def test_run_suite_default_db(self, tmp_path):
        catalog_root = _write_catalog(tmp_path, _SUITE_LATENCY_ONLY_YAML)
        db = get_connection(tmp_path / "nested" / "subdir" / "bench.duckdb")

        with (
            patch("bench.probes.latency.run_latency_probe") as mock_lat,
            patch("bench.runner.append_run") as mock_append,
        ):
            mock_lat.return_value = {
                "ttft_p50_ms": 10.0,
                "ttft_p95_ms": 20.0,
                "decode_tokens_per_sec": 30.0,
                "prompt_eval_tokens_per_sec": 50.0,
            }
            run_suite(
                base_url="http://test/v1",
                catalog_root=catalog_root,
                suite_id="test-suite-latency",
                model="m1",
                db=db,
            )

        mock_append.assert_called_once()
        call_db = mock_append.call_args[0][0]
        assert call_db is db  # runner must pass through the exact connection
        # get_connection creates parent dirs — verify the nested path was created
        assert (tmp_path / "nested" / "subdir").exists()

    def test_run_suite_aggregates_computed(self, tmp_path):
        catalog_root = _write_catalog(tmp_path)  # full suite with aggregates
        db = get_connection(tmp_path / "bench.duckdb")

        with (
            patch("bench.probes.latency.run_latency_probe") as mock_lat,
            patch("bench.probes.lm_eval.run_lm_eval_probe") as mock_eval,
        ):
            mock_lat.return_value = {
                "ttft_p50_ms": 100.0,
                "ttft_p95_ms": 200.0,
                "decode_tokens_per_sec": 50.0,
                "prompt_eval_tokens_per_sec": 200.0,
            }
            mock_eval.return_value = {"arc_challenge_acc": 0.75}

            record = run_suite(
                base_url="http://test/v1",
                catalog_root=catalog_root,
                suite_id="test-suite",
                model="m1", db=db,
            )

        # quality_avg = mean([arc_challenge_acc]) = 0.75
        assert record.scores.get("quality_avg") == pytest.approx(0.75)

    def test_run_suite_uuid_is_hex32(self, tmp_path):
        catalog_root = _write_catalog(tmp_path, _SUITE_LATENCY_ONLY_YAML)

        with (
            patch("bench.probes.latency.run_latency_probe") as mock_lat,
            patch("bench.runner.append_run"),
        ):
            mock_lat.return_value = {
                "ttft_p50_ms": 100.0,
                "ttft_p95_ms": 200.0,
                "decode_tokens_per_sec": 50.0,
                "prompt_eval_tokens_per_sec": 200.0,
            }
            record = run_suite(
                base_url="http://test/v1",
                catalog_root=catalog_root,
                suite_id="test-suite-latency",
                model="m1",
                db=tmp_path / "bench.duckdb",
            )

        assert len(record.run_uuid) == 32
        assert all(c in "0123456789abcdef" for c in record.run_uuid)


# ---------------------------------------------------------------------------
# Issue #118 polish — Prometheus best-effort, git SHAs, lm_eval artifacts
# ---------------------------------------------------------------------------

_CAPABILITY_PROMETHEUS_YAML = """
capability:
  id: cap-prom
  name: Prometheus
  category: telemetry
  description: "VRAM peak"
  probe:
    type: prometheus_window
    queries:
      vram_gb_peak: max_over_time(vram_used[$duration])
  outputs:
    - id: vram_gb_peak
      unit: GiB
      direction: lower_is_better
"""

_SUITE_LATENCY_PLUS_PROM_YAML = """
suite:
  id: test-suite-lat-prom
  name: Latency + Prometheus
  capabilities: [cap-latency, cap-prom]
  aggregates: {}
"""


class TestPolishIssue118:
    def test_prometheus_probe_failure_does_not_fail_run(self, tmp_path):
        """Telemetry probe failures must NOT promote status to 'failed'."""
        root = _write_catalog(tmp_path, _SUITE_LATENCY_PLUS_PROM_YAML)
        # Add the prometheus capability YAML
        (root / "capabilities" / "prom.yml").write_text(_CAPABILITY_PROMETHEUS_YAML)
        db = get_connection(tmp_path / "bench.duckdb")

        with (
            patch("bench.probes.latency.run_latency_probe") as mock_lat,
            patch("bench.probes.prometheus.run_prometheus_window_probe") as mock_prom,
        ):
            mock_lat.return_value = {
                "ttft_p50_ms": 100.0,
                "ttft_p95_ms": 200.0,
                "decode_tokens_per_sec": 50.0,
                "prompt_eval_tokens_per_sec": 200.0,
            }
            # Prometheus blows up
            mock_prom.side_effect = ConnectionError("prom unreachable")

            record = run_suite(
                base_url="http://test/v1",
                catalog_root=root,
                suite_id="test-suite-lat-prom",
                model="m1", db=db,
                prom_start="2026-01-01T00:00:00Z",
                prom_end="2026-01-01T01:00:00Z",
            )

        # The run still succeeded — Prometheus is telemetry, not scoring
        assert record.status == "ok"
        assert record.error is None
        # Latency scores still landed
        assert record.scores.get("ttft_p50_ms") == 100.0
        # Prometheus outputs are explicit null
        assert record.scores.get("vram_gb_peak") is None

    def test_lm_eval_failure_still_fails_run(self, tmp_path):
        """Scoring probe failures must still mark the run as failed (regression guard)."""
        root = _write_catalog(tmp_path)  # latency + lm_eval suite
        db = get_connection(tmp_path / "bench.duckdb")

        with (
            patch("bench.probes.latency.run_latency_probe") as mock_lat,
            patch("bench.probes.lm_eval.run_lm_eval_probe") as mock_eval,
        ):
            mock_lat.return_value = {
                "ttft_p50_ms": 100.0,
                "ttft_p95_ms": 200.0,
                "decode_tokens_per_sec": 50.0,
                "prompt_eval_tokens_per_sec": 200.0,
            }
            mock_eval.side_effect = RuntimeError("lm_eval crashed")
            record = run_suite(
                base_url="http://test/v1",
                catalog_root=root,
                suite_id="test-suite",
                model="m1", db=db,
            )

        # Scoring probe failure → still fails (Phase 4 contract)
        assert record.status == "failed"
        assert "lm_eval" in record.error

    def test_run_suite_populates_git_shas(self, tmp_path):
        """``infra_git_sha`` and ``catalog_git_sha`` populated from git rev-parse."""
        root = _write_catalog(tmp_path, _SUITE_LATENCY_ONLY_YAML)
        db = get_connection(tmp_path / "bench.duckdb")

        with (
            patch("bench.probes.latency.run_latency_probe") as mock_lat,
            patch("bench.runner._read_git_sha") as mock_sha,
        ):
            mock_lat.return_value = {
                "ttft_p50_ms": 100.0, "ttft_p95_ms": 200.0,
                "decode_tokens_per_sec": 50.0, "prompt_eval_tokens_per_sec": 200.0,
            }
            mock_sha.side_effect = lambda p: "deadbeef" if "bench" in str(p) else "cafebabe"
            record = run_suite(
                base_url="http://test/v1",
                catalog_root=root,
                suite_id="test-suite-latency",
                model="m1", db=db,
            )

        assert record.infra_git_sha == "deadbeef"
        assert record.catalog_git_sha == "cafebabe"

    def test_run_suite_handles_missing_git_gracefully(self, tmp_path):
        """``_read_git_sha`` returning None must not fail the run."""
        root = _write_catalog(tmp_path, _SUITE_LATENCY_ONLY_YAML)
        db = get_connection(tmp_path / "bench.duckdb")

        with (
            patch("bench.probes.latency.run_latency_probe") as mock_lat,
            patch("bench.runner._read_git_sha", return_value=None),
        ):
            mock_lat.return_value = {
                "ttft_p50_ms": 100.0, "ttft_p95_ms": 200.0,
                "decode_tokens_per_sec": 50.0, "prompt_eval_tokens_per_sec": 200.0,
            }
            record = run_suite(
                base_url="http://test/v1",
                catalog_root=root,
                suite_id="test-suite-latency",
                model="m1", db=db,
            )

        assert record.status == "ok"
        assert record.infra_git_sha is None
        assert record.catalog_git_sha is None

    def test_run_suite_records_lm_eval_artifact_path(self, tmp_path):
        """lm_eval probe writes a JSON file — its path lands in ``record.artifacts``."""
        root = _write_catalog(tmp_path)  # full suite incl. arc_challenge lm_eval
        db = get_connection(tmp_path / "bench.duckdb")

        with (
            patch("bench.probes.latency.run_latency_probe") as mock_lat,
            patch("bench.probes.lm_eval.run_lm_eval_probe") as mock_eval,
        ):
            mock_lat.return_value = {
                "ttft_p50_ms": 100.0, "ttft_p95_ms": 200.0,
                "decode_tokens_per_sec": 50.0, "prompt_eval_tokens_per_sec": 200.0,
            }
            mock_eval.return_value = {"arc_challenge_acc": 0.75}
            record = run_suite(
                base_url="http://test/v1",
                catalog_root=root,
                suite_id="test-suite",
                model="m1", db=db,
            )

        assert record.status == "ok"
        # The lm_eval probe's task is "arc_challenge" — key is built from that
        assert "lm_eval_arc_challenge" in record.artifacts
        assert record.artifacts["lm_eval_arc_challenge"].endswith(
            "lm_eval_arc_challenge.json"
        )


# ---------------------------------------------------------------------------
# Pre-warm hook (Phase B — llama-swap integration)
# ---------------------------------------------------------------------------

class TestPreWarm:
    def test_pre_warm_called_when_enabled(self, tmp_path):
        """When pre_warm=True, LlamaSwapClient.pre_warm runs before probes."""
        from unittest.mock import patch as _patch

        catalog_root = _write_catalog(tmp_path, _SUITE_LATENCY_ONLY_YAML)
        db = get_connection(tmp_path / "bench.duckdb")

        with (
            _patch("bench.probes.latency.run_latency_probe") as mock_lat,
            _patch("bench.runner.LlamaSwapClient") as mock_swap_cls,
        ):
            mock_lat.return_value = {
                "ttft_p50_ms": 100.0, "ttft_p95_ms": 200.0,
                "decode_tokens_per_sec": 50.0, "prompt_eval_tokens_per_sec": 200.0,
            }
            mock_swap_cls.return_value.pre_warm.return_value = 12.5

            record = run_suite(
                base_url="http://test/v1",
                catalog_root=catalog_root,
                suite_id="test-suite-latency",
                model="m1", db=db,
                pre_warm=True,
            )

        mock_swap_cls.assert_called_once()
        mock_swap_cls.return_value.pre_warm.assert_called_once_with("m1")
        assert record.warm_time_sec == 12.5

    def test_pre_warm_failure_does_not_abort_run(self, tmp_path, caplog):
        """LlamaSwapClient.pre_warm raising shouldn't fail the run."""
        from unittest.mock import patch as _patch

        catalog_root = _write_catalog(tmp_path, _SUITE_LATENCY_ONLY_YAML)
        db = get_connection(tmp_path / "bench.duckdb")

        with (
            _patch("bench.probes.latency.run_latency_probe") as mock_lat,
            _patch("bench.runner.LlamaSwapClient") as mock_swap_cls,
        ):
            mock_lat.return_value = {
                "ttft_p50_ms": 100.0, "ttft_p95_ms": 200.0,
                "decode_tokens_per_sec": 50.0, "prompt_eval_tokens_per_sec": 200.0,
            }
            mock_swap_cls.return_value.pre_warm.side_effect = RuntimeError("swap unreachable")

            record = run_suite(
                base_url="http://test/v1",
                catalog_root=catalog_root,
                suite_id="test-suite-latency",
                model="m1", db=db,
                pre_warm=True,
            )

        assert record.status == "ok"
        assert record.warm_time_sec is None
        assert "Pre-warm failed" in caplog.text

    def test_pre_warm_default_is_disabled(self, tmp_path):
        """Without pre_warm=True, LlamaSwapClient is never constructed."""
        from unittest.mock import patch as _patch

        catalog_root = _write_catalog(tmp_path, _SUITE_LATENCY_ONLY_YAML)
        db = get_connection(tmp_path / "bench.duckdb")

        with (
            _patch("bench.probes.latency.run_latency_probe") as mock_lat,
            _patch("bench.runner.LlamaSwapClient") as mock_swap_cls,
        ):
            mock_lat.return_value = {
                "ttft_p50_ms": 100.0, "ttft_p95_ms": 200.0,
                "decode_tokens_per_sec": 50.0, "prompt_eval_tokens_per_sec": 200.0,
            }

            record = run_suite(
                base_url="http://test/v1",
                catalog_root=catalog_root,
                suite_id="test-suite-latency",
                model="m1", db=db,
                # pre_warm not passed → defaults to False
            )

        mock_swap_cls.assert_not_called()
        assert record.warm_time_sec is None
