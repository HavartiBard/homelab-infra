"""lm-evaluation-harness probe — run a single task via the lm_eval CLI."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ..catalog import LmEvalProbe


# Maps lm-evaluation-harness output keys to our normalized score IDs.
# Add a row here for each task we run; output IDs must match capability YAML outputs.
TASK_SCORE_MAP: dict[str, dict[str, str]] = {
    "arc_challenge": {"acc,none": "arc_challenge_acc"},
    "gsm8k":         {"exact_match,strict-match": "gsm8k_strict_match"},
    "humaneval":     {"pass@1,create_test": "humaneval_pass1"},
    "ifeval":        {"prompt_level_strict_acc,none": "ifeval_strict_acc"},
}


def run_lm_eval_probe(
    probe: LmEvalProbe,
    base_url: str,
    *,
    api_key: str,
    model: str,
    output_path: Path,
) -> dict[str, float | None]:
    """Run a single lm-evaluation-harness task and return mapped scores.

    Uses the `local-chat-completions` adapter for arbitrary OpenAI-compatible endpoints.
    """
    model_args = f"base_url={base_url},model={model},api_key={api_key}"
    cmd = [
        "lm_eval",
        "--model", "local-chat-completions",
        "--model_args", model_args,
        "--tasks", probe.task,
        "--num_fewshot", str(probe.num_fewshot),
        "--batch_size", str(probe.batch_size),
        "--output_path", str(output_path),
        # Disable thinking-mode reasoning via system instruction. Qwen3.6
        # (and similar reasoning-capable models) honor explicit no-think
        # directives. Without this, lm-eval's short-answer tasks see empty
        # `content` because thinking_content consumes the token budget.
        "--system_instruction",
        "/no_think Respond with the answer directly. Do not produce any internal reasoning or chain-of-thought.",
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"lm_eval failed (exit {result.returncode}) for task={probe.task}: "
            f"{result.stderr.decode(errors='replace')[:500]}"
        )

    data = json.loads(Path(output_path).read_text())
    task_results = data.get("results", {}).get(probe.task, {})

    score_map = TASK_SCORE_MAP.get(probe.task)
    if score_map is None:
        raise ValueError(
            f"No score mapping defined for task '{probe.task}' — extend TASK_SCORE_MAP."
        )

    out: dict[str, float | None] = {}
    for lm_eval_key, normalized_id in score_map.items():
        v = task_results.get(lm_eval_key)
        out[normalized_id] = float(v) if v is not None else None
    return out
