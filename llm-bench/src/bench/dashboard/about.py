def render():
    import streamlit as st
    st.title("About llm-bench")
    st.markdown(
        """
        **Phase 1** — capability catalog + orchestrator + read-only leaderboard.

        - **quality_avg** — mean of `arc_challenge_acc`, `gsm8k_strict_match`,
          `humaneval_pass1`, `ifeval_strict_acc`.
        - **speed_score** — `0.5 × cliff_inverse(ttft_p95_ms, 5000) + 0.5 × cliff_normalize(decode_tokens_per_sec, 100)`.

        Spec: `projects/homelab-infra/llm-bench-design.md` in the homelab Obsidian vault.
        Catalog YAMLs: `benchmarks/capabilities/` in the homelab-infra Gitea repo.
        """
    )
