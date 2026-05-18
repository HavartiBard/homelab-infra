import json

import pytest

from bench.catalog import LmEvalProbe
from bench.probes.lm_eval import run_lm_eval_probe


def _make_probe(task: str) -> LmEvalProbe:
    return LmEvalProbe(
        type="lm_eval_harness", task=task, num_fewshot=0, batch_size="auto"
    )


def test_lm_eval_probe_parses_output(monkeypatch, tmp_path):
    output_path = tmp_path / "out.json"
    # Simulate what lm_eval writes for arc_challenge
    output_path.write_text(
        json.dumps(
            {
                "results": {
                    "arc_challenge": {
                        "acc,none": 0.421,
                        "acc_stderr,none": 0.015,
                        "alias": "arc_challenge",
                    }
                }
            }
        )
    )

    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd

        class R:
            returncode = 0
            stdout = b"completed"
            stderr = b""

        return R()

    monkeypatch.setattr("subprocess.run", fake_run)

    scores = run_lm_eval_probe(
        _make_probe("arc_challenge"),
        "http://fake/v1",
        api_key="x",
        model="m",
        output_path=output_path,
    )

    assert scores == {"arc_challenge_acc": pytest.approx(0.421)}
    # Verify command construction
    assert "lm_eval" in captured["cmd"][0] or captured["cmd"][0].endswith("lm_eval")
    assert "--model" in captured["cmd"]
    idx = captured["cmd"].index("--model")
    assert captured["cmd"][idx + 1] == "local-chat-completions"


def test_lm_eval_probe_gsm8k_strict_match(monkeypatch, tmp_path):
    output_path = tmp_path / "out.json"
    output_path.write_text(
        json.dumps(
            {"results": {"gsm8k": {"exact_match,strict-match": 0.31, "alias": "gsm8k"}}}
        )
    )

    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **kw: type(
            "R", (), {"returncode": 0, "stdout": b"", "stderr": b""}
        )(),
    )

    scores = run_lm_eval_probe(
        _make_probe("gsm8k"),
        "http://fake/v1",
        api_key="x",
        model="m",
        output_path=output_path,
    )
    assert scores == {"gsm8k_strict_match": pytest.approx(0.31)}
