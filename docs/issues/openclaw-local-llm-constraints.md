---
title: OpenClaw Jetson local-model constraints
labels:
  - "type:task"
  - "component:openclaw"
importance: high
---

# OpenClaw Jetson local LLM issue tracker

## Problem

- The Jetson-local models (`ollama/llama3.1:8b-instruct-q4_K_M` and `ollama/qwen2.5-coder:7b-instruct-q4_K_M`) advertise a `contextWindow` of 4096 tokens.
- OpenClaw’s control UI (and its internal `CONTEXT_WINDOW_HARD_MIN_TOKENS`) refuses to load models whose context window is below **16 000 tokens**. The gateway logs `blocked model (context window too small)` and never surfaces the models in the UI.
- Until a larger-context quant is available for the Jetson, the control UI will always default to the LMStudio models on the higher-end host.

## Evidence

1. Gateway log excerpt:  
   ```
   blocked model (context window too small): ollama/llama3.1:8b-instruct-q4_K_M ctx=4096 (min=16000) source=modelsConfig
   ```
2. `llama-server` options show the default `--ctx-size 4096` (loaded from the GGUF metadata).
3. The gateway config currently advertises only LMStudio models after the latest deploy, and `openclaw.json` still contains the enscribed Jetson entries, but they remain unused because of the guard.

## Constraints

- OpenClaw hard-codes `CONTEXT_WINDOW_HARD_MIN_TOKENS = 16e3` (see `agents/context-window-guard.ts` in the OpenClaw distribution).
- Changing the Jetson models’ `contextWindow` value in the config is a temporary hack; the guard still rejects them if the hard-coded minimum remains, so any fix must either:
  1. Ship a Jetson model/re-quant that truly supports ≥16 000 tokens, or
  2. Patch OpenClaw (proxy or gateway) to relax the context-window guard when running in this homelab environment.
- The Jetson hardware is limited to ~8 GB of VRAM, so model size upgrades must be balanced against available resources.

## Suggested next steps

1. Scope a Jetson-friendly model that can report ≥16 000 tokens without exhausting VRAM (e.g., a trimmed GLM/Qwen variant built for extended context). Test it locally with `llama-server` and ensure `curl http://localhost:1234/api/tags` exposes it.
2. If no such model exists yet, capture the minimal configuration required by OpenClaw and open a Gitea issue linking this doc; include the gateway logs, the LMStudio fallback config, and the desired long-context model list.
3. For the longer term, consider a patch in the OpenClaw repo (or via a plugin) that lowers `CONTEXT_WINDOW_HARD_MIN_TOKENS` for trusted hosts or accepts per-model overrides pulled from `contextWindowCap` metadata.

Please create a Gitea issue referencing this document and assign it to the Jetson / OpenClaw project so the team can return later. Include the log snippets above so we can track when we eventually get a 16 000-token-capable Jetson model running locally.
