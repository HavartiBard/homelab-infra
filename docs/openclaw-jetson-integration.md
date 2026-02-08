# OpenClaw + Jetson Ollama Integration

**Status:** Ready for Integration
**Date:** 2026-02-08T09:49:00-07:00
**Ollama Version:** 0.13.5

## Infrastructure

### Jetson Ollama Endpoint
- **Host:** jetson.lab (192.168.20.169)
- **Port:** 11434
- **Protocol:** HTTP REST (OpenAI-compatible)
- **Service:** systemd-managed, auto-starts on boot
- **Models:**
  - `llama3.1:8b-instruct-q4_K_M` - General reasoning (8.0B params, Q4_K_M quantization)
  - `qwen2.5-coder:7b-instruct-q4_K_M` - Code generation (7.6B params, Q4_K_M quantization)

### Network Configuration
- **Binding:** `0.0.0.0:11434` (all interfaces)
- **Systemd Override:** `/etc/systemd/system/ollama.service.d/override.conf`
- **Environment:** `OLLAMA_HOST=0.0.0.0:11434`

## OpenClaw Configuration

### Recommended Setup
```python
from openclaw import Agent

# General reasoning agent
reasoning_agent = Agent(
    model="llama3.1:8b-instruct-q4_K_M",
    provider="ollama",
    base_url="http://192.168.20.169:11434",
    reasoning_budget=2000,
)

# Code generation agent
code_agent = Agent(
    model="qwen2.5-coder:7b-instruct-q4_K_M",
    provider="ollama",
    base_url="http://192.168.20.169:11434",
    reasoning_budget=2000,
)
```

### Performance Expectations
- **Latency:** 15-25s per reasoning chain (includes ~10s gateway overhead)
- **Throughput:** 9-12 tokens/sec
- **Use Cases:** Agent loops, code generation, analysis (NOT real-time chat)
- **Memory:** ~4.7GB VRAM per model (Q4_K_M quantization)

### Streaming Configuration
```python
# Enable streaming for natural chunks
response = reasoning_agent.reason(
    "Your prompt here",
    stream=True  # 800-2500ms chunks
)

# Process streaming response
for chunk in response:
    print(chunk, end="", flush=True)
```

## Testing Checklist
- [x] Remote API accessible from OpenClaw host
- [x] Both models respond successfully
- [x] Streaming works correctly
- [ ] Latency within acceptable range (to be verified in production)
- [ ] Reasoning quality verified (to be validated with OpenClaw workloads)

## Quick Test Commands

### List Available Models
```bash
curl http://192.168.20.169:11434/api/tags
```

### Test Llama 3.1 Reasoning
```bash
curl http://192.168.20.169:11434/api/generate -d '{
  "model": "llama3.1:8b-instruct-q4_K_M",
  "prompt": "Think step-by-step: What is the capital of France and why?",
  "stream": false
}'
```

### Test Qwen Coder
```bash
curl http://192.168.20.169:11434/api/generate -d '{
  "model": "qwen2.5-coder:7b-instruct-q4_K_M",
  "prompt": "Write a Python function to calculate fibonacci numbers recursively.",
  "stream": false
}'
```

### Health Check
```bash
curl http://192.168.20.169:11434/api/version
# Expected: {"version":"0.13.5"}
```

## OpenAI-Compatible API

Ollama provides OpenAI-compatible endpoints for drop-in replacement:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://192.168.20.169:11434/v1",
    api_key="ollama"  # Required but not validated
)

response = client.chat.completions.create(
    model="llama3.1:8b-instruct-q4_K_M",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain quantum computing."}
    ]
)

print(response.choices[0].message.content)
```

## Architecture Notes

### Hardware
- **Platform:** NVIDIA Jetson Orin Nano
- **VRAM:** 8GB
- **Architecture:** Ampere (Compute Capability 8.6)
- **Max Concurrent Models:** 1 (limited by VRAM)

### Model Selection Strategy
```python
def select_model(task_type: str) -> str:
    """Route tasks to appropriate models."""
    if task_type in ["code", "debug", "refactor"]:
        return "qwen2.5-coder:7b-instruct-q4_K_M"
    else:
        return "llama3.1:8b-instruct-q4_K_M"
```

### Monitoring
```bash
# Watch GPU memory
ssh james@jetson.lab "watch -n 1 tegrastats"

# Monitor Ollama logs
ssh james@jetson.lab "sudo journalctl -u ollama.service -f"

# Check service status
ssh james@jetson.lab "systemctl status ollama.service"
```

## Deployment Details

### Service Management
```bash
# Restart service
sudo systemctl restart ollama.service

# View configuration
systemctl cat ollama.service

# Check override
cat /etc/systemd/system/ollama.service.d/override.conf
```

### Model Management
```bash
# Pull new model
curl http://192.168.20.169:11434/api/pull -d '{"name":"model:tag"}'

# Remove model
curl http://192.168.20.169:11434/api/delete -d '{"name":"model:tag"}'

# List loaded models
curl http://192.168.20.169:11434/api/ps
```

## Next Steps
1. ✅ Enable remote API access
2. ✅ Verify connectivity from host
3. [ ] Update OpenClaw configuration with Jetson endpoint
4. [ ] Test integration end-to-end with OpenClaw
5. [ ] Monitor performance in production
6. [ ] Implement task-based model auto-switching
7. [ ] Consider deploying DeepSeek-R1-Distill-Qwen-1.5B for enhanced reasoning

## Future Enhancements

### Potential Model Upgrades
Based on MEMORY.md research, consider deploying:

1. **Qwen3-1.7B-Thinking** (Best fit for reasoning)
   - Native thinking mode support
   - 100-120 tokens/sec estimated
   - ~3-4GB VRAM (more headroom)

2. **DeepSeek-R1-Distill-Qwen-1.5B** (Proven alternative)
   - 800k CoT samples
   - 80-120 tokens/sec estimated
   - ~2.5GB VRAM (most conservative)

3. **DeepSeek-R1-Distill-Qwen3-8B** (If memory allows)
   - Best reasoning quality
   - Ties 235B model on AIME 2024
   - ~6-7GB VRAM (tight but viable)

### TensorRT-LLM Optimization
For 16x speedup on reasoning models, consider building TensorRT engines:
- Build on host (pve-01 GPU or Unraid)
- Deploy to jetson.lab via Ansible
- Use NVIDIA NIM containers for serving

## References
- Ollama API Documentation: https://github.com/ollama/ollama/blob/main/docs/api.md
- OpenClaw Documentation: [Insert URL]
- Jetson Deployment Playbook: `/home/james/projects/homelab-infra/ansible/playbooks/edge/deploy-jetson-ollama.yml`
- Memory Research: `/home/james/.claude/projects/-home-james-projects-homelab-infra/memory/MEMORY.md`
