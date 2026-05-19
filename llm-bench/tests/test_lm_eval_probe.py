import json

import pytest

from bench.catalog import LmEvalProbe
from bench.probes.lm_eval import (
    _chat_completions_url,
    _find_results_json,
    run_lm_eval_probe,
)


def _make_probe(task: str) -> LmEvalProbe:
    return LmEvalProbe(
        type="lm_eval_harness", task=task, num_fewshot=0, batch_size="auto"
    )


def _seed_lmeval_output(output_dir, task, score_key, score_value):
    """Write a fake lm-eval results JSON where _find_results_json will look."""
    model_dir = output_dir / "qwen__qwen3.6-27b-mtp"
    model_dir.mkdir(parents=True, exist_ok=True)
    results_file = model_dir / "results_2026-05-18T12-00-00.000.json"
    results_file.write_text(
        json.dumps(
            {
                "results": {
                    task: {
                        score_key: score_value,
                        "alias": task,
                    }
                }
            }
        )
    )
    return results_file


def test_chat_completions_url_appends_path():
    assert _chat_completions_url("http://h/v1") == "http://h/v1/chat/completions"
    assert _chat_completions_url("http://h/v1/") == "http://h/v1/chat/completions"
    assert (
        _chat_completions_url("http://h/v1/chat/completions")
        == "http://h/v1/chat/completions"
    )


def test_find_results_json_raises_when_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="no results_"):
        _find_results_json(tmp_path)


def test_find_results_json_returns_latest_match(tmp_path):
    (tmp_path / "model").mkdir()
    older = tmp_path / "model" / "results_2026-01-01T00-00-00.000.json"
    newer = tmp_path / "model" / "results_2026-05-18T12-00-00.000.json"
    older.write_text("{}")
    newer.write_text("{}")
    assert _find_results_json(tmp_path).name == newer.name


def test_lm_eval_probe_parses_output(monkeypatch, tmp_path):
    output_path = tmp_path / "out.json"
    output_dir = output_path.with_suffix("")  # /tmp/.../out

    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        # Simulate lm-eval writing its results file as a side-effect of the
        # subprocess call (which we're mocking, so write it manually).
        _seed_lmeval_output(
            output_dir,
            task="arc_challenge_chat",
            score_key="exact_match,remove_whitespace",
            score_value=0.421,
        )

        class R:
            returncode = 0
            stdout = b"completed"
            stderr = b""

        return R()

    monkeypatch.setattr("subprocess.run", fake_run)

    scores = run_lm_eval_probe(
        _make_probe("arc_challenge_chat"),
        "http://fake/v1",
        api_key="x",
        model="qwen/qwen3.6-27b-mtp",
        output_path=output_path,
    )

    assert scores == {"arc_challenge_acc": pytest.approx(0.421)}
    # Verify command construction
    assert "lm_eval" in captured["cmd"][0] or captured["cmd"][0].endswith("lm_eval")
    assert "--apply_chat_template" in captured["cmd"]
    assert "--system_instruction" in captured["cmd"]
    # base_url should have /chat/completions appended
    model_args_idx = captured["cmd"].index("--model_args") + 1
    assert "/chat/completions" in captured["cmd"][model_args_idx]
    assert "tokenizer_backend=None" in captured["cmd"][model_args_idx]


def test_lm_eval_probe_gsm8k_strict_match(monkeypatch, tmp_path):
    output_path = tmp_path / "out.json"
    output_dir = output_path.with_suffix("")

    def fake_run(cmd, **kw):
        _seed_lmeval_output(
            output_dir, "gsm8k", "exact_match,strict-match", 0.31
        )
        return type("R", (), {"returncode": 0, "stdout": b"", "stderr": b""})()

    monkeypatch.setattr("subprocess.run", fake_run)

    scores = run_lm_eval_probe(
        _make_probe("gsm8k"),
        "http://fake/v1",
        api_key="x",
        model="m",
        output_path=output_path,
    )
    assert scores == {"gsm8k_strict_match": pytest.approx(0.31)}


def test_lm_eval_probe_humaneval_adds_unsafe_code_flag(monkeypatch, tmp_path):
    """humaneval requires --confirm_run_unsafe_code; other tasks must not get it."""
    output_path = tmp_path / "out.json"
    output_dir = output_path.with_suffix("")

    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = list(cmd)
        _seed_lmeval_output(
            output_dir, "humaneval", "pass@1,create_test", 0.0
        )
        return type("R", (), {"returncode": 0, "stdout": b"", "stderr": b""})()

    monkeypatch.setattr("subprocess.run", fake_run)
    run_lm_eval_probe(
        _make_probe("humaneval"),
        "http://fake/v1",
        api_key="x",
        model="m",
        output_path=output_path,
    )
    assert "--confirm_run_unsafe_code" in captured["cmd"]


def test_lm_eval_probe_non_humaneval_no_unsafe_code_flag(monkeypatch, tmp_path):
    output_path = tmp_path / "out.json"
    output_dir = output_path.with_suffix("")

    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = list(cmd)
        _seed_lmeval_output(
            output_dir, "ifeval", "prompt_level_strict_acc,none", 0.5
        )
        return type("R", (), {"returncode": 0, "stdout": b"", "stderr": b""})()

    monkeypatch.setattr("subprocess.run", fake_run)
    run_lm_eval_probe(
        _make_probe("ifeval"),
        "http://fake/v1",
        api_key="x",
        model="m",
        output_path=output_path,
    )
    assert "--confirm_run_unsafe_code" not in captured["cmd"]
