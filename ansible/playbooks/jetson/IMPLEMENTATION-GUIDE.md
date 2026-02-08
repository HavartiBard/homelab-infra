# Implementation Guide: Reasoning LLM Playbooks for Jetson Orin Nano

**Status**: Ready for integration with llm-researcher recommendations (Task #4)

**Date**: February 2026

## Overview

This guide documents the Ansible playbook infrastructure created for deploying and managing reasoning LLMs on the Jetson Orin Nano via TensorRT-LLM. The playbooks are modular, reusable, and designed to work with any HuggingFace model that has TensorRT example converters.

## Created Playbooks & Roles

### Base Infrastructure (No Changes Needed)

#### Role: `jetson-trtllm`
- **Location**: `ansible/roles/jetson-trtllm/`
- **Purpose**: Initial Jetson setup and TensorRT-LLM stack deployment
- **Existing**: Pre-configured and tested
- **Key tasks**:
  - Install Docker + NVIDIA container toolkit
  - Configure NVIDIA container runtime
  - Create persistent directories for models and cache
  - Deploy TensorRT-LLM development container
  - Validate HuggingFace token and TensorRT version

#### Role: `jetson-trtllm-convert`
- **Location**: `ansible/roles/jetson-trtllm-convert/`
- **Purpose**: Convert HuggingFace models to TensorRT engines
- **Existing**: Pre-configured and tested
- **Key variables** (overridable per model):
  - `trtllm_conversion_model`: HuggingFace model ID
  - `trtllm_conversion_alias`: Friendly name for local storage
  - `trtllm_conversion_convert_script`: Path to model-specific converter
  - `trtllm_conversion_dtype`, `max_input_len`, `max_seq_len`: Optimization params

### New Playbooks

#### 1. `deploy-reasoning-llm-base.yml`
**Purpose**: One-time initial deployment of TensorRT-LLM stack

**Status**: ✓ Ready to run

**Usage**:
```bash
ansible-playbook playbooks/jetson/deploy-reasoning-llm-base.yml \
  --limit jetson.lab -v
```

**What it does**:
- Ensures Docker and NVIDIA runtime installed
- Creates persistent directories
- Starts TensorRT-LLM container

**Expected duration**: 5-10 minutes

---

#### 2. `convert-reasoning-llm-template.yml`
**Purpose**: Template playbook for converting any model to TensorRT

**Status**: ✓ Ready to customize per-model

**Usage Pattern**:
```bash
ansible-playbook playbooks/jetson/convert-reasoning-llm-template.yml \
  -e "trtllm_conversion_model='Qwen/Qwen-QwQ-1B'" \
  -e "trtllm_conversion_alias='qwen-qwq-1b'" \
  -e "trtllm_conversion_convert_script='/opt/TensorRT-LLM/examples/qwen/convert_checkpoint.py'" \
  --limit jetson.lab -v
```

**Required Variables** (override per model):
| Variable | Example | Notes |
|----------|---------|-------|
| `trtllm_conversion_model` | `Qwen/Qwen-QwQ-1B` | HuggingFace model ID |
| `trtllm_conversion_alias` | `qwen-qwq-1b` | Directory name (no spaces) |
| `trtllm_conversion_convert_script` | `/opt/TensorRT-LLM/examples/qwen/convert_checkpoint.py` | Model-family converter |

**Optional Variables** (reasonable defaults provided):
| Variable | Default | For 8GB Jetson |
|----------|---------|------|
| `trtllm_conversion_dtype` | `float16` | ✓ Recommended |
| `trtllm_conversion_gemm` | `float16` | ✓ Recommended |
| `trtllm_conversion_max_batch_size` | `1` | ✓ Optimal |
| `trtllm_conversion_max_input_len` | `2048` | ✓ Good balance |
| `trtllm_conversion_max_seq_len` | `8192` | ✓ Sufficient |

**Expected duration**: 60-180 minutes (depends on model size)

---

#### 3. `validate-reasoning-llm.yml`
**Purpose**: Verify successful model deployment and basic functionality

**Status**: ✓ Ready to use

**Usage**:
```bash
ansible-playbook playbooks/jetson/validate-reasoning-llm.yml \
  -e "trtllm_model_to_validate=qwen-qwq-1b" \
  --limit jetson.lab -v
```

**Checks performed**:
1. ✓ Container is running
2. ✓ GPU memory available
3. ✓ Model engine files exist
4. ✓ Model loads in Python (ModelRunner instantiation)
5. ✓ Basic inference test completes

**Expected duration**: 2-5 minutes

---

#### 4. `health-check-reasoning-llm.yml`
**Purpose**: Ongoing monitoring of deployment health

**Status**: ✓ Ready to use and schedule

**Usage**:
```bash
# Run once
ansible-playbook playbooks/jetson/health-check-reasoning-llm.yml \
  --limit jetson.lab

# Schedule via cron
0 */6 * * * ansible-playbook playbooks/jetson/health-check-reasoning-llm.yml --limit jetson.lab >> /var/log/jetson-health.log 2>&1
```

**Metrics collected**:
- Container uptime and restart count
- GPU temperature and utilization
- GPU memory usage
- Available disk space
- TensorRT-LLM version
- Recent error/warning logs

**Expected duration**: 1-2 minutes

---

#### 5. `rollback-reasoning-llm.yml`
**Purpose**: Safe removal of models or entire stack

**Status**: ✓ Ready to use

**Usage Modes**:

Remove single model:
```bash
ansible-playbook playbooks/jetson/rollback-reasoning-llm.yml \
  -e "trtllm_rollback_mode=model" \
  -e "trtllm_model_to_remove=qwen-qwq-1b" \
  --limit jetson.lab -v
```

Remove entire stack:
```bash
ansible-playbook playbooks/jetson/rollback-reasoning-llm.yml \
  -e "trtllm_rollback_mode=all" \
  --limit jetson.lab -v
```

**What's removed**:
- `model` mode: Single model directory and engine
- `all` mode: All models, but preserves Docker config and HF cache for recovery

**Expected duration**: 1-5 minutes

---

#### 6. `deploy-all-reasoning-models.yml`
**Purpose**: Orchestrate deployment of multiple models in sequence

**Status**: ⚠️ Template with placeholders (needs model list)

**Usage** (after llm-researcher recommendations):
```bash
# Using built-in model list (after updating playbook vars)
ansible-playbook playbooks/jetson/deploy-all-reasoning-models.yml \
  --limit jetson.lab -v

# Or override with external model list
ansible-playbook playbooks/jetson/deploy-all-reasoning-models.yml \
  -e '{"reasoning_models": [
    {"model_id": "Qwen/Qwen-QwQ-1B", "alias": "qwen-qwq-1b", "convert_script": "/opt/TensorRT-LLM/examples/qwen/convert_checkpoint.py"},
    {"model_id": "deepseek-ai/DeepSeek-R1-Distill-1.5B", "alias": "deepseek-r1-1.5b", "convert_script": "/opt/TensorRT-LLM/examples/llama/convert_checkpoint.py"}
  ]}' \
  --limit jetson.lab -v
```

**What it does**:
1. Deploys base TensorRT-LLM stack (one-time)
2. Converts each model sequentially
3. Validates each model loads correctly
4. Outputs deployment summary

**Expected duration**: 180-360 minutes (depends on model count/sizes)

---

### Documentation

#### `README-reasoning-llm-deployment.md`
Comprehensive guide covering:
- Prerequisites and environment setup
- Complete deployment workflow
- Model configuration parameters
- Troubleshooting common issues
- Performance expectations
- Integration with OpenClaw
- Rollback and recovery procedures

## Next Steps: Integration with Recommendations

### After llm-researcher completes Task #4

**Deliverable**: Top 3 reasoning models with specs
```
Example format:
1. Qwen QwQ-1B (1B params, 2.5GB VRAM)
   - HF ID: Qwen/Qwen-QwQ-1B
   - Converter: /opt/TensorRT-LLM/examples/qwen/convert_checkpoint.py
   - Recommended: max_input_len=2048, dtype=float16

2. DeepSeek-R1-Distill-1.5B (1.5B params, 3.5GB VRAM)
   - HF ID: deepseek-ai/DeepSeek-R1-Distill-1.5B
   - Converter: /opt/TensorRT-LLM/examples/llama/convert_checkpoint.py
   - Recommended: max_input_len=1024, dtype=float16

3. Phi-3.5-Mini-Instruct (3.8B params, 4GB VRAM)
   - HF ID: microsoft/Phi-3.5-mini-instruct
   - Converter: /opt/TensorRT-LLM/examples/llama/convert_checkpoint.py
   - Recommended: max_input_len=2048, dtype=float16
```

### Then: Create Model-Specific Playbooks

For each recommended model, create a thin wrapper:

**Example: `convert-qwen-qwq-1b.yml`**
```yaml
---
- name: Convert Qwen QwQ-1B to TensorRT engine
  hosts: jetson.lab
  gather_facts: no
  become: true
  vars:
    trtllm_conversion_model: Qwen/Qwen-QwQ-1B
    trtllm_conversion_alias: qwen-qwq-1b
    trtllm_conversion_convert_script: /opt/TensorRT-LLM/examples/qwen/convert_checkpoint.py
    trtllm_conversion_max_input_len: 2048
  roles:
    - jetson-trtllm-convert
```

**Advantages**:
- One-liner to deploy known model: `ansible-playbook playbooks/jetson/convert-qwen-qwq-1b.yml`
- Clear documentation for users
- Tested parameters baked in

### Then: Update Multi-Model Orchestrator

Update `deploy-all-reasoning-models.yml` with final model list:
```yaml
reasoning_models:
  - model_id: "Qwen/Qwen-QwQ-1B"
    alias: "qwen-qwq-1b"
    convert_script: "/opt/TensorRT-LLM/examples/qwen/convert_checkpoint.py"
  - model_id: "deepseek-ai/DeepSeek-R1-Distill-1.5B"
    alias: "deepseek-r1-1.5b"
    convert_script: "/opt/TensorRT-LLM/examples/llama/convert_checkpoint.py"
  - model_id: "microsoft/Phi-3.5-mini-instruct"
    alias: "phi-3.5-mini"
    convert_script: "/opt/TensorRT-LLM/examples/llama/convert_checkpoint.py"
```

## Testing & Validation Checklist

Before running in production, test each playbook component:

- [ ] **Syntax**: All playbooks pass `--syntax-check`
- [ ] **Dry-run**: All playbooks pass `--check --diff` on target host
- [ ] **Single-model conversion**: Convert one test model successfully
- [ ] **Validation**: Validation playbook passes for test model
- [ ] **Health check**: Health check returns expected metrics
- [ ] **Rollback**: Single-model rollback succeeds
- [ ] **Re-deploy**: Re-deployment after rollback succeeds
- [ ] **Multi-model**: Multi-model orchestrator works end-to-end
- [ ] **Idempotence**: Re-running playbooks with `--check` shows `changed=0`

## Monitoring & Maintenance

### Recommended Automation

**Health check every 6 hours**:
```bash
# Add to crontab
0 */6 * * * cd /home/james/projects/homelab-infra/ansible && \
  ansible-playbook playbooks/jetson/health-check-reasoning-llm.yml \
  --limit jetson.lab 2>&1 | logger -t jetson-health
```

**Weekly validation**:
```bash
# Add to crontab (Sunday 2 AM)
0 2 * * 0 cd /home/james/projects/homelab-infra/ansible && \
  ansible-playbook playbooks/jetson/validate-reasoning-llm.yml \
  -e "trtllm_model_to_validate=primary-reasoning-model" \
  --limit jetson.lab 2>&1 | logger -t jetson-validate
```

## Troubleshooting Guide

### Issue: Conversion hangs during trtllm-build
**Solution**: Reduce `max_batch_size` to 1, lower `max_seq_len` to 4096

### Issue: HuggingFace token not found
**Solution**: `export HUGGINGFACE_RO=$(op read "op://AI Wedge/Hugging Face Read-Only Token/credential")`

### Issue: GPU out of memory
**Solution**: Increase `trtllm_shm_size` or reduce model size variant

### Issue: Model validation fails
**Solution**: Check container logs: `docker logs trtllm-dev | tail -50`

## File Locations

```
ansible/
├── playbooks/jetson/
│   ├── deploy-reasoning-llm-base.yml
│   ├── convert-reasoning-llm-template.yml
│   ├── validate-reasoning-llm.yml
│   ├── health-check-reasoning-llm.yml
│   ├── rollback-reasoning-llm.yml
│   ├── deploy-all-reasoning-models.yml
│   ├── README-reasoning-llm-deployment.md
│   └── IMPLEMENTATION-GUIDE.md
├── roles/jetson-trtllm/ (existing)
├── roles/jetson-trtllm-convert/ (existing)
└── inventory/
    └── host_vars/jetson.lab.yml
```

## Success Criteria

Deployment is considered successful when:

1. ✓ Base TensorRT-LLM container runs on Jetson
2. ✓ At least one reasoning model converts successfully
3. ✓ Model validation playbook passes (model loads, inference works)
4. ✓ Health check shows normal GPU/memory metrics
5. ✓ Models can be converted, validated, and rolled back without errors
6. ✓ Playbooks are idempotent (re-running shows `changed=0`)

## Support & Next Actions

1. **Wait for Task #4**: llm-researcher provides model recommendations
2. **Create model-specific playbooks**: One per recommended model
3. **Update orchestrator**: Add models to `deploy-all-reasoning-models.yml`
4. **Test end-to-end**: Run full deployment and validation suite
5. **Document integration**: Add OpenClaw integration examples
6. **Schedule monitoring**: Set up health checks and alerting

---

**Ready to proceed upon receiving model recommendations from llm-researcher.**
