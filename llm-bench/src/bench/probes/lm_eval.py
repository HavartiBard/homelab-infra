"""lm-evaluation-harness probe — run a single task via the lm_eval CLI."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ..catalog import LmEvalProbe


# Maps lm-evaluation-harness output keys to our normalized score IDs.
# Add a row here for each task we run; output IDs must match capability YAML outputs.
#
# Note: arc_challenge (the canonical task) uses loglikelihood scoring which
# isn't supported by chat-completions endpoints. Use arc_challenge_chat which
# converts it to a generate_until task with `exact_match` scoring.
TASK_SCORE_MAP: dict[str, dict[str, str]] = {
    "arc_challenge_chat": {"exact_match,remove_whitespace": "arc_challenge_acc"},
    "gsm8k":              {"exact_match,strict-match": "gsm8k_strict_match"},
    "humaneval":          {"pass@1,create_test": "humaneval_pass1"},
    "ifeval":             {"prompt_level_strict_acc,none": "ifeval_strict_acc"},
}


def _chat_completions_url(base_url: str) -> str:
    """Return the full chat completions URL.

    lm-eval's local-chat-completions adapter requires the full endpoint URL
    (it doesn't append `/chat/completions` to the base). Accept either form
    from the caller (`http://host/v1` or `http://host/v1/chat/completions`).
    """
    url = base_url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url = url + "/chat/completions"
    return url


def _find_results_json(output_dir: Path) -> Path:
    """Locate the lm-eval results JSON inside output_dir.

    lm-eval writes to `<output_dir>/<model_sanitized>/results_<timestamp>.json`.
    We glob for the newest match.
    """
    matches = sorted(output_dir.glob("**/results_*.json"))
    if not matches:
        raise FileNotFoundError(
            f"lm-eval succeeded but no results_*.json found under {output_dir}"
        )
    return matches[-1]


def run_lm_eval_probe(
    probe: LmEvalProbe,
    base_url: str,
    *,
    api_key: str,
    model: str,
    output_path: Path,
) -> dict[str, float | None]:
    """Run a single lm-evaluation-harness task and return mapped scores.

    Uses the `local-chat-completions` adapter for arbitrary OpenAI-compatible
    endpoints. The caller passes ``output_path`` as a target file path; this
    function treats it as a base and creates a sibling directory for lm-eval's
    timestamped output, then globs for the results file.
    """
    chat_url = _chat_completions_url(base_url)
    # lm-eval's model_args is a comma-separated key=value string. tokenizer_backend=None
    # skips HF Hub auto-detect (no spurious "unauthenticated requests to HF Hub" warning).
    model_args = (
        f"base_url={chat_url},"
        f"model={model},"
        f"api_key={api_key},"
        f"num_concurrent=4,"
        f"tokenizer_backend=None"
    )

    # Use output_path's parent + stem as a directory for lm-eval to write into.
    # lm-eval will create `<dir>/<model_sanitized>/results_<ts>.json`.
    output_dir = output_path.with_suffix("")
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "lm_eval",
        "--model", "local-chat-completions",
        "--model_args", model_args,
        "--tasks", probe.task,
        "--num_fewshot", str(probe.num_fewshot),
        "--batch_size", str(probe.batch_size),
        "--output_path", str(output_dir),
        # Required for chat-completions endpoint — wraps task prompts in
        # [{role: user, content: ...}] format. Without this, lm-eval throws
        # "LocalChatCompletion expects messages as list[dict]".
        "--apply_chat_template",
        # Disable Qwen3.6's thinking mode at the system level — `/no_think` is
        # the documented Qwen switch, plus a plain English fallback directive.
        # Without this, short-answer tasks see empty `content` because
        # reasoning_content consumes the entire token budget.
        "--system_instruction",
        "/no_think Respond with the answer directly. Do not produce any internal reasoning or chain-of-thought.",
    ]
    # humaneval requires code execution which lm-eval gates behind an explicit
    # opt-in flag. Add it conditionally so we don't accidentally enable code
    # execution for tasks that don't need it.
    if probe.task == "humaneval":
        cmd.append("--confirm_run_unsafe_code")

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"lm_eval failed (exit {result.returncode}) for task={probe.task}: "
            f"{result.stderr.decode(errors='replace')[:500]}"
        )

    results_file = _find_results_json(output_dir)
    data = json.loads(results_file.read_text())
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
