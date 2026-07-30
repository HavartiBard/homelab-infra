# Jetson inference observability and rollup dashboards

## Goal

Add Jetson Nano inference visibility without replacing its stable native Ollama
deployment, then provide a rollup dashboard for inference services across
Goudai and Jetson. Spraycheese remains a future ComfyUI/GPU-worker addition.

## Design

- Keep Goudai on llama-swap/llama.cpp.
- Keep Jetson on native Ollama. llama-swap is not introduced solely for metric
  consistency.
- Add a small Jetson textfile collector that polls Ollama's local `/api/ps` and
  `/api/tags` endpoints.
- Add `host` labels to the node_exporter Prometheus targets for `goudai` and
  `jetson`.
- Normalize rollup metrics with `inference_*` recording rules:
  - `inference_model_loaded`
  - `inference_model_memory_bytes`
  - `inference_generation_tokens_per_second` where the backend provides it
- Create separate Jetson and inference-rollup Grafana dashboards.

## Metric contract

| Metric | Backend | Meaning |
|---|---|---|
| `homelab_ollama_endpoint_up` | Jetson/Ollama | API availability |
| `homelab_ollama_model_loaded` | Jetson/Ollama | Model currently resident |
| `homelab_ollama_model_memory_bytes` | Jetson/Ollama | Ollama-reported model memory |
| `goudai_llm_generation_tokens_per_second` | Goudai/llama-swap | llama.cpp generation throughput |
| `inference_*` | Rollup | Stable cross-backend dashboard names |

Jetson throughput is intentionally not fabricated from model load state. Ollama
does not expose a Prometheus endpoint on the current Jetson installation; a
future Ollama proxy or request-timing collector can add it to the rollup.

## Execution and verification

1. Deploy `deploy-jetson-ollama-metrics.yml` to `jetson.lab`.
2. Confirm Jetson node_exporter exposes `homelab_ollama_*`.
3. Reload Prometheus and confirm the Jetson target has `host="jetson"`.
4. Open the Jetson dashboard and inference rollup; confirm model state and
   host memory work while Jetson throughput is shown as unavailable.

## Rollback

Remove the Jetson metrics role/playbook and dashboard JSON, remove the added
Prometheus target labels/rules, then redeploy observability. The native Ollama
service is not modified by this design.
