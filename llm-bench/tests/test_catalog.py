from pathlib import Path

import pytest
import yaml

from bench.catalog import Capability, Suite, load_capability, load_suite


def test_load_latency_capability(tmp_path):
    f = tmp_path / "ttft.yml"
    f.write_text("""
capability:
  id: ttft
  name: Time to First Token
  category: speed
  description: Test
  probe:
    type: latency
    fixture: fixtures/latency-prompts.jsonl
    sample_size: 50
  outputs:
    - { id: ttft_p50_ms, unit: ms, direction: lower_is_better }
    - { id: ttft_p95_ms, unit: ms, direction: lower_is_better }
""")
    cap = load_capability(f)
    assert isinstance(cap, Capability)
    assert cap.id == "ttft"
    assert cap.probe.type == "latency"
    assert cap.probe.sample_size == 50
    assert [o.id for o in cap.outputs] == ["ttft_p50_ms", "ttft_p95_ms"]


def test_load_lm_eval_capability(tmp_path):
    f = tmp_path / "arc.yml"
    f.write_text("""
capability:
  id: arc_challenge
  name: ARC-Challenge
  category: reasoning
  description: Test
  probe:
    type: lm_eval_harness
    task: arc_challenge
    num_fewshot: 0
    batch_size: auto
  outputs:
    - { id: arc_challenge_acc, unit: accuracy, direction: higher_is_better }
""")
    cap = load_capability(f)
    assert cap.probe.type == "lm_eval_harness"
    assert cap.probe.task == "arc_challenge"


def test_load_prometheus_capability(tmp_path):
    f = tmp_path / "vram.yml"
    f.write_text("""
capability:
  id: vram
  name: VRAM
  category: efficiency
  description: Test
  probe:
    type: prometheus_window
    queries:
      vram_gb_peak: 'max_over_time(x[$duration])'
  outputs:
    - { id: vram_gb_peak, unit: GB, direction: lower_is_better }
""")
    cap = load_capability(f)
    assert cap.probe.type == "prometheus_window"
    assert "vram_gb_peak" in cap.probe.queries


def test_load_suite(tmp_path):
    f = tmp_path / "tier1.yml"
    f.write_text("""
suite:
  id: tier1
  name: Tier 1
  capabilities: [ttft, arc_challenge]
  aggregates:
    quality_avg:
      type: mean
      inputs: [arc_challenge_acc]
    speed_score:
      type: weighted
      inputs:
        ttft_p95_ms: { weight: 1.0, transform: { type: cliff_inverse, cliff: 5000 } }
""")
    suite = load_suite(f)
    assert suite.id == "tier1"
    assert suite.aggregates["quality_avg"].type == "mean"
    assert suite.aggregates["speed_score"].inputs["ttft_p95_ms"].weight == 1.0


def test_invalid_probe_type_rejected(tmp_path):
    f = tmp_path / "bad.yml"
    f.write_text("""
capability:
  id: bad
  name: Bad
  category: speed
  description: Test
  probe:
    type: nonsense
  outputs:
    - { id: x, unit: ms, direction: lower_is_better }
""")
    with pytest.raises(Exception):
        load_capability(f)
