# Mem0 memory for the Hermes agents

Date: 2026-07-25
Status: Approved for planning

## Problem

Lyra (the isolated Hermes stack on jetson.lab) is complaining her memory
module is disabled. Her `hermes.yaml.j2` has `memory.memory_enabled: false`,
while Raclette (the other Hermes agent, also on jetson.lab) has it `true`
but with `memory.provider: ''` — i.e. no external provider wired up either.

Rather than just flipping the built-in flag, we're standing up
[Mem0](https://mem0.ai) as a shared, self-hosted memory backend for both
Hermes agents, since the `nousresearch/hermes-agent` image already ships a
pluggable memory-provider system with a bundled `mem0` plugin.

## Findings from the Hermes image

Inspected `nousresearch/hermes-agent:latest` directly (`/opt/hermes/agent/memory_provider.py`,
`/opt/hermes/plugins/memory/mem0/`):

- Hermes's `MemoryManager` enforces one external memory provider at a time,
  registered via `memory.provider` in `hermes.yaml`.
- The bundled `mem0` plugin (`plugins/memory/mem0`, v1.3.0) supports three
  connection modes:
  - **Platform** — Mem0's hosted SaaS (`api.mem0.ai`), needs `MEM0_API_KEY`.
  - **Self-hosted server** — a Mem0 server you run yourself (FastAPI +
    pgvector, Docker-shipped), the plugin just talks HTTP (`X-API-Key`) to
    it. Config: `host`, `api_key`, `user_id`, `agent_id` in
    `$HERMES_HOME/mem0.json`.
  - **OSS in-process** — `mem0ai` SDK runs inside the Hermes container
    itself with its own LLM/embedder/vector store.
- Self-hosted server mode is the only one that gives us a shared store
  multiple agents can point at with distinct `agent_id`/`user_id` — this is
  the mode we're using.
- Tools exposed: `mem0_search`, `mem0_add`, `mem0_update`, `mem0_delete`.

## Architecture

```
                         ┌─────────────────────────────┐
                         │  Unraid (192.168.20.14)     │
                         │  mem0-server stack           │
                         │  ┌────────┐  ┌─────────────┐│
                         │  │  api   │  │  dashboard  ││
                         │  │ :8888  │  │   :8889     ││
                         │  └───┬────┘  └─────────────┘│
                         │      │                       │
                         │  ┌───▼─────────┐             │
                         │  │ postgres +   │             │
                         │  │  pgvector    │ (internal)  │
                         │  └──────────────┘             │
                         └───────────┬───────────────────┘
                                     │ LAN, HTTP + X-API-Key
                 ┌───────────────────┴───────────────────┐
                 │                                        │
      ┌──────────▼──────────┐                 ┌──────────▼──────────┐
      │ hermes-lyra (jetson) │                 │ raclette (jetson)   │
      │ agent_id: lyra       │                 │ agent_id: raclette  │
      └──────────────────────┘                 └──────────────────────┘

Both agents' chat + mem0's own LLM/embedder calls go to:
      goudai llama-swap (192.168.20.150:8010, OpenAI-compatible)
      + new embedding model entry (nomic-embed-text, --embedding mode)
```

## Components

### 1. `mem0-server` stack (new, Unraid)

- New Ansible role `ansible/roles/mem0-server/`, playbook
  `ansible/playbooks/ai/deploy-mem0-server.yml`, secrets slug `mem0-server`.
- Docker Compose: `api` (FastAPI, published `8888`), `postgres`/pgvector
  (internal network only, no host port), `dashboard` (published `8889`).
  **No Neo4j container** — the Hermes plugin only uses `/search` and
  `/memories`, graph memory is unused; adding it later is a additive change,
  not a migration.
- Secrets (resolved via `run-playbook.sh mem0-server ...`, stored in
  1Password, templated into `.env`):
  - `JWT_SECRET` (generated, `openssl rand -base64 48`)
  - `POSTGRES_PASSWORD` (generated)
  - `ADMIN_API_KEY` (generated) — used once to bootstrap the admin account
    and issue per-agent API keys via the dashboard; not used by the agents
    themselves.
- LAN-only. No NPM proxy entry for either port — matches the `comfyui-mcp`
  precedent (agent-to-service and admin traffic only, not user-facing).

### 2. LLM/embedder backend (goudai llama-swap)

- Add a new entry to `llama_swap_models` in
  `ansible/roles/llama-swap/defaults/main.yml`: an embedding model (e.g.
  `nomic-embed-text` GGUF) run via `llama-server --embedding`, its own
  alias through llama-swap alongside the existing chat models.
- In the mem0 dashboard's runtime LLM/embedder configuration (persisted to
  mem0's own Postgres DB, not re-templated by Ansible), set the `openai`
  provider's base URL to `http://192.168.20.150:8010/v1` for both the
  extraction LLM and the embedder, using the respective llama-swap model
  aliases. This is a one-time manual bootstrap step (documented in the
  playbook's post-deploy notes), not something Ansible drives — the
  dashboard is the only interface Mem0 exposes for it.
- **Open risk**: if the dashboard's provider override does not accept a
  custom `openai_base_url` for a self-hosted server once inspected in
  detail, the fallback is rebuilding the mem0 server image with an
  Ollama-compatible provider (the bundled providers are OpenAI/
  Anthropic/Gemini only; Ollama requires adding to
  `server/requirements.txt` and rebuilding). This will be confirmed early
  in implementation, before the rest of the work depends on it.

### 3. Client wiring — Lyra

In `ansible/files/jetson/hermes-lyra/config/hermes.yaml.j2`:
```yaml
memory:
  memory_enabled: true
  user_profile_enabled: true
  provider: mem0
  ...
```
New `ansible/files/jetson/hermes-lyra/config/mem0.json.j2`:
```json
{
  "mode": "selfhosted",
  "host": "http://192.168.20.14:8888",
  "user_id": "lyra",
  "agent_id": "lyra"
}
```
mounted into `{{ lyra_state_dir }}` alongside `hermes.yaml`. New
`MEM0_API_KEY` in `ansible/files/jetson/hermes-lyra/.env.j2`, issued from
the mem0 dashboard for Lyra specifically, stored via the existing
`lyra_env` secrets mechanism (same pattern as `API_SERVER_KEY`).

### 4. Client wiring — Raclette

Same shape as Lyra, in the `jetson-raclette` role/files:
- `memory.provider: mem0` (role already has `memory_enabled: true`).
- New `mem0.json.j2` with `agent_id: raclette`, distinct `user_id`.
- New `MEM0_API_KEY` for Raclette, issued separately from the dashboard.

Distinct `agent_id`/`user_id` per agent on the shared server keeps Lyra's
and Raclette's memories from cross-contaminating while both use the same
backing Postgres/pgvector store.

## Rollout / verification

1. Deploy `mem0-server` on Unraid, verify `curl http://192.168.20.14:8888/docs`
   and dashboard login.
2. Add the embedding model to llama-swap on goudai, verify
   `curl http://192.168.20.150:8010/v1/models` lists it and a direct
   embeddings call succeeds.
3. Bootstrap the mem0 dashboard's LLM/embedder override to point at
   llama-swap; confirm with a manual `mem0_add`/`mem0_search` round-trip
   via the dashboard or API before touching either agent.
4. Issue API keys for `lyra` and `raclette`, deploy the Lyra config change,
   verify `mem0_search`/`mem0_add` tool calls work from a live Lyra session.
5. Deploy the Raclette config change, same verification.

## Out of scope

- Neo4j / graph memory.
- Exposing mem0 (API or dashboard) outside the LAN.
- Migrating any existing built-in-memory state — this is a fresh store.
