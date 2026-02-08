# Reasoning LLM Deployment on Jetson Orin Nano

Complete guide for deploying reasoning LLMs on the Jetson Orin Nano 8GB via Ansible and TensorRT-LLM.

## Overview

This deployment provides:
- **TensorRT-LLM stack** on Jetson Orin Nano (Ubuntu 22.04 with JetPack 6.0)
- **GPU-accelerated inference** via NVIDIA TensorRT optimization
- **Reasoning model support** (Qwen QwQ, DeepSeek-R1, Phi-3.5, etc.)
- **Container-based deployment** for reproducible, portable setup
- **Model versioning** with per-model TensorRT engine compilation

## Prerequisites

### Host Setup
- **Jetson Orin Nano** (8GB RAM) or compatible device
- **Ubuntu 22.04** with **JetPack 6.0** or later
- **Docker & Docker Compose plugin** (installed via ansible)
- **NVIDIA Container Runtime** (installed via ansible)

### Credentials & Secrets
- **HuggingFace Read-Only Token**: Export as `HUGGINGFACE_RO` env var
  ```bash
  export HUGGINGFACE_RO=$(op read "op://AI Wedge/Hugging Face Read-Only Token/credential")
  ```

### Disk Space
- **50-100GB** minimum for models, engines, and cache
  - Model download: ~5-20GB (depends on model size)
  - TensorRT engine compilation: ~10-30GB (temporary)
  - Persistent cache: ~20GB (for model files and compiled engines)

### Ansible Setup
- SSH access to `jetson.lab` with appropriate key (`~/.ssh/id_ed25519`)
- Host defined in `ansible/inventory/hosts.yml` under `edge_devices` group
- Python 3.8+ on Jetson (not required, playbooks use `raw` module)

## Deployment Workflow

### 1. Initial Deployment (One-time Setup)

```bash
cd /home/james/projects/homelab-infra/ansible

# Syntax check
ansible-playbook playbooks/jetson/deploy-reasoning-llm-base.yml --syntax-check

# Dry-run to preview changes
ansible-playbook playbooks/jetson/deploy-reasoning-llm-base.yml \
  --limit jetson.lab --check --diff

# Apply deployment
ansible-playbook playbooks/jetson/deploy-reasoning-llm-base.yml \
  --limit jetson.lab -v
```

**Expected output:**
- Docker and NVIDIA container toolkit installed
- TensorRT-LLM container running as `trtllm-dev`
- Persistent directories created
- HuggingFace token validated

### 2. Convert & Deploy a Reasoning Model

Use the template playbook to convert any HuggingFace model:

```bash
# Example: Convert Qwen QwQ-1B
ansible-playbook playbooks/jetson/convert-reasoning-llm-template.yml \
  -e "trtllm_conversion_model='Qwen/Qwen-QwQ-1B'" \
  -e "trtllm_conversion_alias='qwen-qwq-1b'" \
  -e "trtllm_conversion_convert_script='/opt/TensorRT-LLM/examples/qwen/convert_checkpoint.py'" \
  --limit jetson.lab --check --diff

# Apply conversion (WARNING: takes 1-2 hours on Jetson)
ansible-playbook playbooks/jetson/convert-reasoning-llm-template.yml \
  -e "trtllm_conversion_model='Qwen/Qwen-QwQ-1B'" \
  -e "trtllm_conversion_alias='qwen-qwq-1b'" \
  -e "trtllm_conversion_convert_script='/opt/TensorRT-LLM/examples/qwen/convert_checkpoint.py'" \
  --limit jetson.lab -v
```

### 3. Validate Deployment

```bash
# Test model loading and inference
ansible-playbook playbooks/jetson/validate-reasoning-llm.yml \
  -e "trtllm_model_to_validate=qwen-qwq-1b" \
  --limit jetson.lab -v
```

### 4. Monitor Health (Ongoing)

```bash
# Run health checks (memory, GPU, uptime, etc.)
ansible-playbook playbooks/jetson/health-check-reasoning-llm.yml \
  --limit jetson.lab
```

## Model Configuration Parameters

When converting models, customize these parameters per model:

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `trtllm_conversion_model` | string | `meta-llama/Llama-3.2-3B-Instruct` | HuggingFace model ID |
| `trtllm_conversion_alias` | string | `reasoning-model` | Friendly name for directory |
| `trtllm_conversion_convert_script` | string | `/opt/TensorRT-LLM/examples/llama/convert_checkpoint.py` | Model family converter script |
| `trtllm_conversion_dtype` | string | `float16` | `float16` or `bfloat16` |
| `trtllm_conversion_gemm` | string | `float16` | GEMM plugin dtype: `float16` or `int8` |
| `trtllm_conversion_max_batch_size` | int | `1` | 1-4 for 8GB Jetson |
| `trtllm_conversion_max_input_len` | int | `2048` | Context window (tokens) |
| `trtllm_conversion_max_seq_len` | int | `8192` | Max total sequence length |

### Example Configurations

**Qwen QwQ-1B (Reasoning optimized)**
```bash
trtllm_conversion_model='Qwen/Qwen-QwQ-1B'
trtllm_conversion_alias='qwen-qwq-1b'
trtllm_conversion_convert_script='/opt/TensorRT-LLM/examples/qwen/convert_checkpoint.py'
trtllm_conversion_dtype='float16'
trtllm_conversion_max_input_len='2048'
trtllm_conversion_max_seq_len='8192'
```

**DeepSeek-R1-Distill-1.5B**
```bash
trtllm_conversion_model='deepseek-ai/DeepSeek-R1-Distill-1.5B'
trtllm_conversion_alias='deepseek-r1-distill-1.5b'
trtllm_conversion_convert_script='/opt/TensorRT-LLM/examples/llama/convert_checkpoint.py'
trtllm_conversion_dtype='float16'
trtllm_conversion_max_input_len='1024'
trtllm_conversion_max_seq_len='4096'
```

## File Structure

```
ansible/
├── playbooks/jetson/
│   ├── deploy-reasoning-llm-base.yml              # Initial setup (run once)
│   ├── convert-reasoning-llm-template.yml          # Convert any model to TensorRT
│   ├── validate-reasoning-llm.yml                  # Test model loading & inference
│   ├── health-check-reasoning-llm.yml              # Monitor health
│   ├── rollback-reasoning-llm.yml                  # Remove models/stack
│   └── README-reasoning-llm-deployment.md          # This file
├── roles/jetson-trtllm/                            # Base deployment role
│   ├── defaults/main.yml                           # Default variables
│   ├── tasks/main.yml                              # Deployment tasks
│   └── templates/
│       ├── docker-compose.yml.j2
│       └── env.j2
├── roles/jetson-trtllm-convert/                    # Model conversion role
│   ├── defaults/main.yml                           # Conversion defaults
│   └── tasks/main.yml                              # Conversion tasks
└── inventory/
    └── host_vars/jetson.lab.yml                    # Jetson-specific vars
```

## Troubleshooting

### Conversion Hangs or Runs Out of Memory

**Issue**: Conversion process killed or hangs at trtllm-build step

**Solution**:
1. Check available GPU memory: `docker exec trtllm-dev nvidia-smi`
2. Reduce batch size and max sequence length
3. Use `float16` for dtype/gemm (smaller than bfloat16)
4. Monitor disk space: `df -h /home/james/models/tensorrt_llm`

### HuggingFace Token Issues

**Issue**: "Token is invalid" or "Access denied" during model download

**Solution**:
```bash
# Verify token is set
echo $HUGGINGFACE_RO

# Verify inside container
docker exec trtllm-dev huggingface-cli whoami

# Re-export and retry conversion
export HUGGINGFACE_RO=$(op read "op://AI Wedge/Hugging Face Read-Only Token/credential")
ansible-playbook playbooks/jetson/convert-reasoning-llm-template.yml ...
```

### Model Load Fails During Validation

**Issue**: ModelRunner fails to load engine

**Solution**:
1. Verify engine directory exists: `ls -la /home/james/models/tensorrt_llm/<model>/engine/`
2. Check conversion completed: Look for `trtllm_engine_<model>.plan` files
3. Inspect container logs: `docker logs trtllm-dev | tail -50`
4. Re-run conversion if interrupted

### GPU Memory Insufficient

**Issue**: "CUDA out of memory" during conversion or inference

**Solution**:
1. Increase shared memory: `trtllm_shm_size: 8gb` → `16gb` in role defaults
2. Reduce max_batch_size to 1
3. Lower max_input_len and max_seq_len
4. Wait for other GPU processes to release memory

## Rollback & Recovery

### Remove a Single Model

```bash
ansible-playbook playbooks/jetson/rollback-reasoning-llm.yml \
  -e "trtllm_rollback_mode=model" \
  -e "trtllm_model_to_remove=qwen-qwq-1b" \
  --limit jetson.lab --check --diff
```

### Remove Entire Stack

```bash
ansible-playbook playbooks/jetson/rollback-reasoning-llm.yml \
  -e "trtllm_rollback_mode=all" \
  --limit jetson.lab --check --diff
```

**Note**: This removes all models and stops the container, but preserves Docker Compose files and HuggingFace cache for quick recovery.

## Integration with OpenClaw

Once deployed, the reasoning LLM is available for OpenClaw integration:

1. **Model discovery**: Query model directory
   ```bash
   ls -la /home/james/models/tensorrt_llm/*/engine/
   ```

2. **HTTP API**: Expose via vLLM or OpenAI-compatible wrapper
   ```bash
   # Inside container or via port mapping
   python -m vllm.entrypoints.openai.api_server \
     --model-dir /data/models/tensorrt_llm/qwen-qwq-1b/engine \
     --dtype float16
   ```

3. **Chain-of-thought parsing**: Models like QwQ output reasoning steps directly

## Performance Expectations

| Model | VRAM | Latency | Tokens/sec | Notes |
|-------|------|---------|-----------|-------|
| Qwen QwQ-1B | 2.5GB | 200-400ms | 5-10 | Reasoning output expands token count |
| DeepSeek-R1-Distill-1.5B | 3.5GB | 300-500ms | 3-8 | Heavy reasoning overhead |
| Phi-3.5-Mini-Instruct | 2GB | 150-300ms | 8-15 | Good balance of speed/quality |

*Measured on Jetson Orin Nano with TensorRT optimization, max_batch_size=1*

## Advanced: Custom Model Additions

To add a new model family with custom converter:

1. **Check if TensorRT example exists**:
   ```bash
   docker exec trtllm-dev ls -la /opt/TensorRT-LLM/examples/
   ```

2. **Identify converter script**:
   - Llama family: `/opt/TensorRT-LLM/examples/llama/convert_checkpoint.py`
   - Qwen family: `/opt/TensorRT-LLM/examples/qwen/convert_checkpoint.py`
   - Custom: May need adaptation

3. **Test conversion with template**:
   ```bash
   ansible-playbook playbooks/jetson/convert-reasoning-llm-template.yml \
     -e "trtllm_conversion_model='<model-id>'" \
     -e "trtllm_conversion_alias='<alias>'" \
     -e "trtllm_conversion_convert_script='/opt/TensorRT-LLM/examples/<family>/convert_checkpoint.py'" \
     --limit jetson.lab -v
   ```

## Support & Escalation

### Health check shows issues?
1. Run `health-check-reasoning-llm.yml`
2. Check container logs: `docker logs trtllm-dev`
3. Verify GPU: `docker exec trtllm-dev nvidia-smi`

### Need to troubleshoot conversion?
1. SSH to jetson.lab: `ssh -i ~/.ssh/id_ed25519 james@jetson.lab`
2. Enter container: `docker exec -it trtllm-dev /bin/bash`
3. Check logs in `/tmp/` and `/var/log/`

### Need to reset and start fresh?
```bash
# Full cleanup and redeploy
ansible-playbook playbooks/jetson/rollback-reasoning-llm.yml \
  -e "trtllm_rollback_mode=all" \
  --limit jetson.lab

# Redeploy base
ansible-playbook playbooks/jetson/deploy-reasoning-llm-base.yml \
  --limit jetson.lab -v

# Reconvert model
ansible-playbook playbooks/jetson/convert-reasoning-llm-template.yml \
  -e "trtllm_conversion_model='...'" \
  ...
```

## References

- TensorRT-LLM: https://github.com/NVIDIA/TensorRT-LLM
- NVIDIA JetPack: https://developer.nvidia.com/embedded/jetpack
- Docker on Jetson: https://docs.nvidia.com/jetson/
