---
service: personal-agent-llm
type: utility
host: goudai
ports: [8010]
status: active
---

# Personal Agent LLM

## Overview

Dedicated OpenAI-compatible `llama-server` endpoint on goudai for personal coding agents. This keeps Open WebUI on native Ollama while giving agents a separately tunable Qwen3.6 MTP runtime.

## Configuration

- Host: `goudai` (`192.168.20.150`)
- API: `http://192.168.20.150:8010/v1`
- Service: `personal-agent-llm.service`
- Runtime: `/usr/local/bin/llama-server`
- Model: `ggml-org/Qwen3.6-27B-MTP-GGUF:BF16`
- Alias: `qwen/qwen3.6-27b-mtp`
- Context window: `131072`
- Speculative decode: `--spec-type draft-mtp --spec-draft-n-max 5`
- Cache: `/var/lib/personal-agent-llm/huggingface`

Defaults live in `ansible/roles/personal-agent-llm/defaults/main.yml`.

## Deployment

```bash
cd ansible
ansible-playbook playbooks/ai/deploy-personal-agent-llm.yml --syntax-check
ansible-playbook playbooks/ai/deploy-personal-agent-llm.yml --check --diff --limit goudai
ansible-playbook playbooks/ai/deploy-personal-agent-llm.yml --diff --limit goudai -v
```

Re-run LiteLLM after deployment if clients should discover the model through the central proxy:

```bash
cd ansible
ansible-playbook playbooks/ai/deploy-litellm.yml --diff --limit unraid -v --vault-password-file ~/.vault-pass
```

## Health Check

```bash
curl -s http://192.168.20.150:8010/v1/models
curl -s http://192.168.20.14:4000/models
```

## Troubleshooting

```bash
ssh -i ~/.ssh/id_ed25519_homelab james@192.168.20.150
systemctl status personal-agent-llm
journalctl -u personal-agent-llm -f
```

If `llama-server` is missing, run `ansible/playbooks/bootstrap/setup-goudai-host.yml` first. If the initial model load times out, check free space under `/var/lib/personal-agent-llm` and restart the service after the Hugging Face download finishes.
