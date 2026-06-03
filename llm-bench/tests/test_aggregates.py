import math

import pytest

from bench.aggregates import compute_aggregates, cliff_inverse, cliff_normalize
from bench.catalog import load_suite
from pathlib import Path
import tempfile


def test_cliff_inverse_at_zero():
    assert cliff_inverse(0, 5000) == pytest.approx(1.0)


def test_cliff_inverse_at_cliff():
    assert cliff_inverse(5000, 5000) == pytest.approx(0.0)


def test_cliff_inverse_beyond_cliff_clamps_to_zero():
    assert cliff_inverse(99999, 5000) == 0.0


def test_cliff_inverse_midpoint():
    assert cliff_inverse(2500, 5000) == pytest.approx(0.5)


def test_cliff_normalize_at_cliff():
    assert cliff_normalize(100, 100) == pytest.approx(1.0)


def test_cliff_normalize_beyond_cliff_clamps_to_one():
    assert cliff_normalize(250, 100) == 1.0


def test_cliff_normalize_midpoint():
    assert cliff_normalize(50, 100) == pytest.approx(0.5)


def _write_suite(tmp_path, body: str) -> Path:
    f = tmp_path / "tier1.yml"
    f.write_text(body)
    return f


def test_mean_aggregate(tmp_path):
    suite = load_suite(_write_suite(tmp_path, """
suite:
  id: t
  name: t
  capabilities: [a]
  aggregates:
    quality_avg:
      type: mean
      inputs: [a_acc, b_acc, c_acc]
"""))
    scores = {"a_acc": 0.6, "b_acc": 0.8, "c_acc": 1.0}
    out = compute_aggregates(scores, suite)
    assert out["quality_avg"] == pytest.approx(0.8)


def test_mean_with_null_inputs_returns_null(tmp_path):
    suite = load_suite(_write_suite(tmp_path, """
suite:
  id: t
  name: t
  capabilities: [a]
  aggregates:
    quality_avg:
      type: mean
      inputs: [a_acc, b_acc]
"""))
    scores = {"a_acc": 0.6, "b_acc": None}
    out = compute_aggregates(scores, suite)
    assert out["quality_avg"] is None


def test_weighted_aggregate_with_cliff_transforms(tmp_path):
    suite = load_suite(_write_suite(tmp_path, """
suite:
  id: t
  name: t
  capabilities: [a]
  aggregates:
    speed_score:
      type: weighted
      inputs:
        ttft_p95_ms:           { weight: 0.5, transform: { type: cliff_inverse,   cliff: 5000 } }
        decode_tokens_per_sec: { weight: 0.5, transform: { type: cliff_normalize, cliff: 100  } }
"""))
    # ttft 2500ms -> 0.5; decode 50 t/s -> 0.5; weighted sum = 0.5*0.5 + 0.5*0.5 = 0.5
    scores = {"ttft_p95_ms": 2500.0, "decode_tokens_per_sec": 50.0}
    out = compute_aggregates(scores, suite)
    assert out["speed_score"] == pytest.approx(0.5)
