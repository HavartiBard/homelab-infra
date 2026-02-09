# OpenClaw + Jetson Integration Guide

**Status:** Production Ready
**Last Updated:** 2026-02-08
**Jetson Endpoint:** http://192.168.20.169:11434

---

## Overview

This guide provides comprehensive instructions for integrating OpenClaw agents with the Jetson Orin Nano Ollama deployment. The integration enables AI agents to leverage edge GPU inference for reasoning and code generation tasks.

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│  OpenClaw Agent Framework                                │
│  - Reasoning agents                                      │
│  - Code generation agents                                │
│  - Multi-step problem solving                            │
└─────────────────┬────────────────────────────────────────┘
                  │
                  ▼
         HTTP REST API (OpenAI-compatible)
                  │
                  ▼
┌──────────────────────────────────────────────────────────┐
│  Jetson Orin Nano (192.168.20.169:11434)                │
│  ├─ Ollama 0.13.5                                        │
│  ├─ Llama 3.1 8B Instruct (Q4_K_M) - Reasoning           │
│  ├─ Qwen 2.5 Coder 7B Instruct (Q4_K_M) - Code gen       │
│  └─ VRAM: 8GB shared (unified memory)                    │
└──────────────────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Verify Jetson Endpoint

```bash
curl http://192.168.20.169:11434/api/version
# Expected: {"version":"0.13.5"}

curl http://192.168.20.169:11434/api/tags
# Expected: Both models listed (llama3.1:8b-instruct-q4_K_M, qwen2.5-coder:7b-instruct-q4_K_M)
```

### 2. Run Integration Tests

```bash
cd /home/james/projects/homelab-infra/ansible

# Full integration test suite
ansible-playbook playbooks/jetson/test-openclaw-integration.yml \
  -i localhost, --connection=local

# Expected: All 6 tests passing (connectivity, models, reasoning, code gen, performance, OpenAI compat)
```

### 3. Configure OpenClaw Agents

#### Option A: Using OpenAI-Compatible API

```python
from openai import OpenAI

# Initialize client
client = OpenAI(
    base_url="http://192.168.20.169:11434/v1",
    api_key="ollama"  # Required but not validated
)

# Reasoning agent
reasoning_response = client.chat.completions.create(
    model="llama3.1:8b-instruct-q4_K_M",
    messages=[
        {"role": "system", "content": "You are a helpful assistant that thinks step-by-step."},
        {"role": "user", "content": "Solve this problem: A train travels 120 miles in 2 hours. What is its average speed?"}
    ]
)

print(reasoning_response.choices[0].message.content)

# Code generation agent
code_response = client.chat.completions.create(
    model="qwen2.5-coder:7b-instruct-q4_K_M",
    messages=[
        {"role": "system", "content": "You are an expert Python programmer."},
        {"role": "user", "content": "Write a function to check if a number is prime. Include docstring."}
    ]
)

print(code_response.choices[0].message.content)
```

#### Option B: Direct Ollama API

```python
import requests

def query_ollama(model: str, prompt: str, stream: bool = False) -> dict:
    """Query Jetson Ollama endpoint."""
    response = requests.post(
        "http://192.168.20.169:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": stream
        }
    )
    return response.json()

# Use reasoning model
result = query_ollama(
    model="llama3.1:8b-instruct-q4_K_M",
    prompt="Think step-by-step: What is 15 * 23?"
)
print(result["response"])

# Use code generation model
result = query_ollama(
    model="qwen2.5-coder:7b-instruct-q4_K_M",
    prompt="Write a Python function for binary search with type hints."
)
print(result["response"])
```

### 4. Test with Example Script

```bash
# Install dependencies
pip install openai requests

# Run demo
python /home/james/projects/homelab-infra/scripts/openclaw_jetson_example.py --task all

# Or run specific demos
python scripts/openclaw_jetson_example.py --task reasoning
python scripts/openclaw_jetson_example.py --task coding
python scripts/openclaw_jetson_example.py --task auto
```

---
### 5. Deploy OpenClaw Gateway via Ansible

```bash
cd /home/james/projects/homelab-infra/ansible

# Supply LMStudio/Slack credentials via env or vault before running.
ansible-playbook playbooks/jetson/deploy-openclaw.yml \
  --limit jetson.lab
```

This playbook copies the upstream `docker-compose.yml`, renders `.env` with the current `OLLAMA_*`, `LMSTUDIO_*`, and Slack variables, and starts `openclaw-gateway` together with its `llama-server` companion. The gateway is now configured to prefer the local Ollama endpoint (`ollama/llama3.1` and `ollama/qwen2.5`) for reasoning/coder workloads while keeping the heavier LMStudio models as fallbacks. Once the stack is up, the Jetson host listens on port 18789 and `openclaw.klsll.com` can reach it through the proxy we set earlier.

## Model Selection Strategy

### Automatic Routing

```python
def select_model(task_type: str) -> str:
    """
    Route tasks to optimal models based on type.

    Args:
        task_type: "reasoning", "code", or "auto"

    Returns:
        Model name to use
    """
    if task_type == "code" or any(keyword in task_description.lower()
                                   for keyword in ["function", "class", "python", "javascript", "code"]):
        return "qwen2.5-coder:7b-instruct-q4_K_M"
    else:
        return "llama3.1:8b-instruct-q4_K_M"

# Example usage
task = "Write a Python function to calculate fibonacci"
model = select_model("code")  # Returns qwen2.5-coder

task = "Explain step-by-step how recursion works"
model = select_model("reasoning")  # Returns llama3.1
```

### Model Characteristics

| Model | Best For | Tokens/sec | VRAM | Strength |
|-------|----------|------------|------|----------|
| Llama 3.1 8B Instruct | General reasoning, explanations, multi-step problems | 8-12 | 4.9 GB | Step-by-step thinking, clear explanations |
| Qwen 2.5 Coder 7B Instruct | Code generation, debugging, technical docs | 9-12 | 4.7 GB | Production-quality code, docstrings, best practices |

---

## Performance Expectations

### Latency

| Scenario | Time Range | Suitability |
|----------|------------|-------------|
| Direct Ollama API | 10-35s per response | Agent loops, analysis |
| With OpenClaw Gateway | 20-45s (includes ~10s overhead) | Background processing |
| Real-time chat | NOT RECOMMENDED | Too slow for interactive use |

### Throughput

- **Tokens/sec:** 8-12 tokens/sec (measured)
- **Typical response:** 100-400 tokens
- **Sustained throughput:** 2-4 complete responses/minute
- **Concurrent requests:** Sequential only (single GPU)

### Resource Constraints

- **VRAM:** 4.7-4.9 GB per loaded model
- **Total VRAM:** 8 GB (unified memory with CPU)
- **Available headroom:** ~2.5-3 GB for system operations
- **Model switching:** 5-10s per switch (unload/reload cycle)

---

## Monitoring and Health Checks

### Automated Health Monitoring

```bash
cd /home/james/projects/homelab-infra/ansible

# Run health check
ansible-playbook playbooks/jetson/monitor-openclaw-health.yml

# Expected: Overall Status: PASS
```

**Health checks performed:**
1. Endpoint connectivity
2. Model availability (both Llama and Qwen)
3. Reasoning performance (min 7.0 tokens/sec)
4. Code generation performance (min 7.0 tokens/sec)
5. Jetson service status

### Manual Monitoring

```bash
# Check service status
ssh james@jetson.lab "systemctl status ollama.service"

# Watch GPU memory
ssh james@jetson.lab "watch -n 2 tegrastats"

# Monitor logs
ssh james@jetson.lab "sudo journalctl -u ollama.service -f"

# Check loaded models
curl http://192.168.20.169:11434/api/ps
```

### Setting Up Continuous Monitoring

Add to crontab for periodic health checks:

```bash
# Run health check every 15 minutes
*/15 * * * * cd /home/james/projects/homelab-infra/ansible && ansible-playbook playbooks/jetson/monitor-openclaw-health.yml >> /var/log/openclaw-health.log 2>&1
```

---

## Troubleshooting

### Issue: Connection Refused

**Symptoms:** `curl: (7) Failed to connect to 192.168.20.169:11434`

**Resolution:**
```bash
# Verify Ollama is running
ssh james@jetson.lab "systemctl status ollama.service"

# Check if binding to all interfaces
ssh james@jetson.lab "ss -tlnp | grep 11434"
# Expected: 0.0.0.0:11434 (not 127.0.0.1:11434)

# If bound to localhost only, reconfigure:
ssh james@jetson.lab "sudo systemctl edit ollama.service"
# Add: Environment="OLLAMA_HOST=0.0.0.0:11434"
ssh james@jetson.lab "sudo systemctl restart ollama.service"
```

### Issue: Model Not Found

**Symptoms:** API returns `{"error":"model not found"}`

**Resolution:**
```bash
# List available models
curl http://192.168.20.169:11434/api/tags

# If model missing, pull it:
curl http://192.168.20.169:11434/api/pull -d '{"name":"llama3.1:8b-instruct-q4_K_M"}'
```

### Issue: Slow Performance (<7 tokens/sec)

**Symptoms:** Responses taking >60s for short prompts

**Diagnosis:**
```bash
# Check system load
ssh james@jetson.lab "uptime"

# Check memory pressure
ssh james@jetson.lab "free -h"

# Check if multiple models loaded
curl http://192.168.20.169:11434/api/ps
```

**Resolution:**
- Unload unused models to free VRAM
- Restart Ollama service to clear memory
- Check for other GPU-intensive processes

### Issue: OOM Errors

**Symptoms:** Service crashes with "Out of memory" in logs

**Resolution:**
```bash
# Reduce model size by using smaller quantizations
# OR ensure only one model loaded at a time
# OR add memory limits in systemd service:
ssh james@jetson.lab "sudo systemctl edit ollama.service"
# Add: MemoryMax=6G
```

---

## Production Best Practices

### 1. Error Handling

```python
import requests
from requests.exceptions import RequestException
import time

def query_with_retry(model: str, prompt: str, max_retries: int = 3) -> dict:
    """Query Ollama with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            response = requests.post(
                "http://192.168.20.169:11434/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=60
            )
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt
            print(f"Request failed, retrying in {wait_time}s...")
            time.sleep(wait_time)
```

### 2. Timeout Configuration

- **Short prompts (<50 tokens):** 30s timeout
- **Medium prompts (50-200 tokens):** 60s timeout
- **Long prompts (>200 tokens):** 90s timeout

### 3. Streaming for Long Responses

```python
def query_streaming(model: str, prompt: str):
    """Stream responses for better UX."""
    response = requests.post(
        "http://192.168.20.169:11434/api/generate",
        json={"model": model, "prompt": prompt, "stream": True},
        stream=True
    )

    for line in response.iter_lines():
        if line:
            chunk = json.loads(line)
            if "response" in chunk:
                print(chunk["response"], end="", flush=True)
            if chunk.get("done"):
                break
```

### 4. Monitoring Metrics

Track these metrics for production:
- **Requests per minute**
- **Average response time**
- **Tokens per second** (target: >8 t/s)
- **Error rate**
- **Model load time**
- **Memory usage**

---

## Future Enhancements

### 1. TensorRT-LLM Optimization

For 16x speedup on reasoning models:
- Build TensorRT engines on host (pve-01 GPU or Unraid)
- Deploy compiled engines to Jetson via Ansible
- Use NVIDIA NIM containers for serving
- Expected: 80-120 tokens/sec (vs current 8-12 t/s)

### 2. Additional Models

Consider deploying via Ollama:
- **Qwen3-1.7B-Thinking:** Native thinking mode, 100-120 t/s estimated
- **DeepSeek-R1-Distill-1.5B:** Explicit CoT, 2.5GB VRAM (most conservative)
- **DeepSeek-R1-Distill-8B:** Best reasoning quality, 6-7GB VRAM (tight)

### 3. Load Balancing

For higher throughput:
- Deploy Ollama on additional Jetson/GPU devices
- Implement round-robin or least-loaded routing
- Use HAProxy or Nginx for load distribution

### 4. Task Queue Integration

For async agent workloads:
- Integrate with Celery/Redis task queue
- Queue reasoning tasks during high load
- Process in background with result callbacks

---

## Reference

### Files

- **Integration test:** `ansible/playbooks/jetson/test-openclaw-integration.yml`
- **Health monitoring:** `ansible/playbooks/jetson/monitor-openclaw-health.yml`
- **Example script:** `scripts/openclaw_jetson_example.py`
- **Validation report:** `docs/jetson-ollama-validation.md`
- **Deployment guide:** `docs/jetson-reasoning-llm.md`

### API Documentation

- **Ollama API:** https://github.com/ollama/ollama/blob/main/docs/api.md
- **OpenAI API:** https://platform.openai.com/docs/api-reference

### Related Documentation

- Memory research: `/home/james/.claude/projects/-home-james-projects-homelab-infra/memory/MEMORY.md`
- Jetson deployment playbook: `ansible/playbooks/misc/deploy-jetson-reasoning-llm.yml`
- OpenClaw integration doc: `docs/openclaw-jetson-integration.md`

---

**Last Validated:** 2026-02-08
**Integration Status:** ✅ Production Ready
**Performance:** 8-12 tokens/sec (validated)
**Uptime:** Managed by systemd, auto-starts on boot
