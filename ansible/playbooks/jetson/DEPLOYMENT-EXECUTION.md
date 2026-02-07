# Jetson Reasoning LLM Deployment Execution Guide

**Target**: Jetson Orin Nano (jetson.lab)
**Deployment Type**: TensorRT-LLM with recommended reasoning models
**Timeline**: ~30 minutes (base) + 60-180 minutes per model conversion

---

## Prerequisites Checklist

Before starting deployment, verify:

- [ ] SSH access to jetson.lab: `ssh -i ~/.ssh/id_ed25519 james@jetson.lab`
- [ ] HuggingFace read-only token exported:
  ```bash
  export HUGGINGFACE_RO=$(op read "op://AI Wedge/Hugging Face Read-Only Token/credential")
  echo $HUGGINGFACE_RO  # Should show token value
  ```
- [ ] Sufficient disk space: `ssh jetson.lab df -h` (need 50GB+ free)
- [ ] Jetson host online: `ping jetson.lab`
- [ ] Ansible inventory has jetson.lab: `grep jetson.lab ansible/inventory/hosts.yml`

---

## Execution Plan

### Phase 1: Base Infrastructure (30-45 minutes)

Deploy TensorRT-LLM stack (one-time):

```bash
cd /home/james/projects/homelab-infra/ansible

# 1. Syntax check
ansible-playbook playbooks/jetson/deploy-reasoning-llm-base.yml --syntax-check

# 2. Dry-run to preview
ansible-playbook playbooks/jetson/deploy-reasoning-llm-base.yml \
  --limit jetson.lab --check --diff

# 3. Apply deployment
ansible-playbook playbooks/jetson/deploy-reasoning-llm-base.yml \
  --limit jetson.lab -v

# 4. Verify completion
# Expected:
#   - Container 'trtllm-dev' running
#   - /opt/trtllm/ directory created with docker-compose.yml
#   - /home/james/models/tensorrt_llm/ ready for model storage
#   - HuggingFace token validated
```

**Expected output snippet**:
```
TASK [jetson-trtllm : Validate TensorRT LLM container is running]
ok: [jetson.lab]

TASK [jetson-trtllm : Check tensorrt_llm module version inside container]
ok: [jetson.lab]
stdout: 0.12.0.dev0

TASK [jetson-trtllm : Validate Hugging Face authentication inside container]
ok: [jetson.lab]
```

### Phase 2: Deploy Primary Model - Qwen3-1.7B-Thinking (90-120 minutes)

Convert and deploy recommended primary model:

```bash
cd /home/james/projects/homelab-infra/ansible

# 1. Start conversion (LONG-RUNNING)
echo "Starting Qwen3-1.7B-Thinking conversion..."
ansible-playbook playbooks/jetson/convert-qwen3-1.7b-thinking.yml \
  --limit jetson.lab -v 2>&1 | tee qwen3_conversion.log

# This will take ~90-120 minutes on Jetson hardware
# You can monitor progress in another terminal:
# ssh jetson.lab docker logs -f trtllm-dev | grep -E "Downloaded|Downloaded|trtllm-build"
```

**While conversion runs, monitor in parallel**:
```bash
# In another terminal:
ssh jetson.lab 'watch -n 5 "free -h && echo --- && docker exec trtllm-dev nvidia-smi"'
```

**Expected final output**:
```
TASK [jetson-trtllm-convert : Download/convert model inside trtllm container]
changed: [jetson.lab]

TASK [Display conversion completion info]
Qwen3-1.7B-Thinking conversion complete!
```

### Phase 3: Validation - Qwen3-1.7B-Thinking (5-10 minutes)

Verify model loads and inference works:

```bash
cd /home/james/projects/homelab-infra/ansible

# Run validation
ansible-playbook playbooks/jetson/validate-reasoning-llm.yml \
  -e "trtllm_model_to_validate=qwen3-1.7b-thinking" \
  --limit jetson.lab -v

# Expected output:
#   ✓ Container running: true
#   ✓ GPU memory available: XXXX MB
#   ✓ Model engine directory present
#   ✓ Model loads successfully
#   ✓ Inference test completed
```

**Troubleshooting if validation fails**:
```bash
# Check container logs
ssh jetson.lab docker logs trtllm-dev | tail -50

# Check model directory
ssh jetson.lab ls -lah /home/james/models/tensorrt_llm/qwen3-1.7b-thinking/engine/

# Check GPU
ssh jetson.lab docker exec trtllm-dev nvidia-smi
```

---

## Optional: Deploy Additional Models

### Option A: Add Conservative Alternative (DeepSeek-R1-Distill-1.5B)

For memory safety or comparison:

```bash
# 1. Convert (60-90 minutes)
ansible-playbook playbooks/jetson/convert-deepseek-r1-distill-1.5b.yml \
  --limit jetson.lab -v 2>&1 | tee deepseek_1.5b_conversion.log

# 2. Validate
ansible-playbook playbooks/jetson/validate-reasoning-llm.yml \
  -e "trtllm_model_to_validate=deepseek-r1-distill-1.5b" \
  --limit jetson.lab -v

# 3. Compare (optional)
echo "Available models:"
ssh jetson.lab ls -la /home/james/models/tensorrt_llm/*/engine/
```

### Option B: Add Premium Variant (DeepSeek-R1-Distill-8B) ⚠️

**ONLY if**: Jetson fully dedicated, no competing services

```bash
# READ WARNING FIRST
cat playbooks/jetson/convert-deepseek-r1-distill-8b.yml | grep -A 20 "WARNING"

# 1. Confirm memory strategy
ssh jetson.lab 'free -h'  # Check available swap

# 2. Optional: Add swap space (4GB)
ssh jetson.lab 'sudo dd if=/dev/zero of=/swapfile bs=1G count=4 && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile'

# 3. Convert (3+ hours, VERY LONG)
ansible-playbook playbooks/jetson/convert-deepseek-r1-distill-8b.yml \
  --limit jetson.lab -v 2>&1 | tee deepseek_8b_conversion.log

# 4. CONTINUOUS MONITORING during inference test
ssh jetson.lab 'watch -n 1 "free -h && echo --- && docker exec trtllm-dev nvidia-smi dmon"' &

# 5. Validate (with memory watch)
ansible-playbook playbooks/jetson/validate-reasoning-llm.yml \
  -e "trtllm_model_to_validate=deepseek-r1-distill-8b" \
  --limit jetson.lab -v

# Kill monitoring watch
pkill -f "watch -n 1"
```

---

## Post-Deployment Steps

### 1. Health Check (5 minutes)

```bash
ansible-playbook playbooks/jetson/health-check-reasoning-llm.yml \
  --limit jetson.lab
```

**Expected output**:
```
✓ Container running: true
✓ GPU memory available: XXXX MB
✓ GPU temperature: XX°C
✓ Disk space: XGb available
✓ TensorRT-LLM version: 0.12.0.dev0
✓ No errors/warnings found
```

### 2. List Deployed Models

```bash
ssh jetson.lab 'ls -lah /home/james/models/tensorrt_llm/*/engine/ | head -20'
```

**Example output**:
```
qwen3-1.7b-thinking/engine/:
total 4.5G
-rw-r--r-- model.plan
-rw-r--r-- config.json

deepseek-r1-distill-1.5b/engine/:
total 3.2G
-rw-r--r-- model.plan
-rw-r--r-- config.json
```

### 3. Verify Inference Speed (Optional)

```bash
# Quick speed test
ssh jetson.lab 'docker exec trtllm-dev python3 << "EOF"
from tensorrt_llm.runtime import ModelRunner
import time

engine_dir = "/data/models/tensorrt_llm/qwen3-1.7b-thinking/engine"
runner = ModelRunner.from_dir(engine_dir, rank=0)

# Time 100 token generation
start = time.time()
outputs = runner.generate([[1,2,3]], max_new_tokens=100)
elapsed = time.time() - start

print(f"Generated 100 tokens in {elapsed:.2f}s ({100/elapsed:.1f} tokens/sec)")
EOF
'
```

**Expected**:
- Qwen3-1.7B: ~100-120 tokens/sec
- DeepSeek-1.5B: ~80-120 tokens/sec
- DeepSeek-8B: ~30-40 tokens/sec

---

## Schedule Ongoing Monitoring

### Health checks (every 6 hours)

```bash
# Add to crontab
crontab -e

# Add this line:
0 */6 * * * cd /home/james/projects/homelab-infra/ansible && \
  ansible-playbook playbooks/jetson/health-check-reasoning-llm.yml \
  --limit jetson.lab >> /tmp/jetson-health.log 2>&1
```

### Weekly validation

```bash
# Add to crontab:
0 2 * * 0 cd /home/james/projects/homelab-infra/ansible && \
  ansible-playbook playbooks/jetson/validate-reasoning-llm.yml \
  -e "trtllm_model_to_validate=qwen3-1.7b-thinking" \
  --limit jetson.lab >> /tmp/jetson-validation.log 2>&1
```

---

## Success Criteria

Deployment successful when:

- [ ] Base infrastructure deployed and container running
- [ ] Primary model (Qwen3-1.7B-Thinking) converted and validated
- [ ] Model loads without errors in validation playbook
- [ ] GPU memory usage matches expectations (3-4GB)
- [ ] Inference speed ~100-120 tokens/sec achieved
- [ ] Health check shows no errors
- [ ] Monitoring scheduled and operational

---

## Rollback / Recovery

### Remove single model

```bash
ansible-playbook playbooks/jetson/rollback-reasoning-llm.yml \
  -e "trtllm_rollback_mode=model" \
  -e "trtllm_model_to_remove=qwen3-1.7b-thinking" \
  --limit jetson.lab -v
```

### Remove entire stack (if needed)

```bash
ansible-playbook playbooks/jetson/rollback-reasoning-llm.yml \
  -e "trtllm_rollback_mode=all" \
  --limit jetson.lab -v

# Then redeploy
ansible-playbook playbooks/jetson/deploy-reasoning-llm-base.yml \
  --limit jetson.lab -v
```

---

## Estimated Timeline

| Phase | Duration | Action |
|-------|----------|--------|
| Phase 1: Base | 30-45 min | Deploy infrastructure |
| Phase 2: Primary | 90-120 min | Convert Qwen3-1.7B |
| Phase 3: Validate | 5-10 min | Test model loading |
| Health check | 5 min | Verify ongoing health |
| **Total** | **2-3 hours** | Complete setup |

*Each additional model adds 60-180 minutes depending on size*

---

## Troubleshooting Common Issues

### Conversion hangs at trtllm-build

**Problem**: Playbook seems frozen for >2 hours

**Solution**:
```bash
# Check actual progress in container
ssh jetson.lab docker logs -f trtllm-dev | grep -E "trtllm-build|built|checkpoint"

# If nothing happens for 30+ min, likely OOM or disk full:
ssh jetson.lab 'free -h && df -h /home/james/'

# Restart if needed
ssh jetson.lab docker restart trtllm-dev
```

### Validation fails with "ModelRunner not found"

**Problem**: Model engine directory exists but ModelRunner.from_dir() fails

**Solution**:
```bash
# Verify engine files complete
ssh jetson.lab 'ls -lah /home/james/models/tensorrt_llm/qwen3-1.7b-thinking/engine/'

# If model.plan is 0 bytes or missing, re-run conversion
ansible-playbook playbooks/jetson/convert-qwen3-1.7b-thinking.yml \
  --limit jetson.lab -v
```

### GPU memory insufficient (OOM during inference)

**Problem**: Memory error during validation test

**Solution**:
```bash
# Check current usage
ssh jetson.lab docker exec trtllm-dev nvidia-smi

# Reduce model size:
# - Use 1.5B instead of 8B
# - Use float16 instead of bfloat16

# Or add swap:
ssh jetson.lab 'sudo dd if=/dev/zero of=/swapfile bs=1G count=4 && \
  sudo chmod 600 /swapfile && \
  sudo mkswap /swapfile && \
  sudo swapon /swapfile'
```

### HuggingFace token error

**Problem**: "Access denied" or "Invalid token"

**Solution**:
```bash
# Verify token exported locally
echo $HUGGINGFACE_RO

# Re-authenticate
export HUGGINGFACE_RO=$(op read "op://AI Wedge/Hugging Face Read-Only Token/credential")

# Verify inside container
ansible-playbook playbooks/jetson/deploy-reasoning-llm-base.yml \
  --limit jetson.lab -v | grep "huggingface-cli whoami"
```

---

## File Locations

All playbooks in: `/home/james/projects/homelab-infra/ansible/playbooks/jetson/`

**Key files**:
- `deploy-reasoning-llm-base.yml` - Base infrastructure
- `convert-qwen3-1.7b-thinking.yml` - Primary model
- `convert-deepseek-r1-distill-1.5b.yml` - Alternative (safe)
- `convert-deepseek-r1-distill-8b.yml` - Premium (aggressive)
- `validate-reasoning-llm.yml` - Model testing
- `health-check-reasoning-llm.yml` - Health monitoring
- `rollback-reasoning-llm.yml` - Cleanup/removal
- `RECOMMENDED-MODELS.md` - Model selection guide
- `README-reasoning-llm-deployment.md` - Comprehensive reference

---

## Next: OpenClaw Integration

Once deployment is complete:

1. **Expose API**: Configure port mapping or HTTP wrapper
2. **Test inference**: Manual prompts to verify output quality
3. **Integrate with OpenClaw**: Configure streaming endpoint
4. **Monitor chains**: Track reasoning token usage and latency
5. **Optimize**: Tune max_batch_size, quantization, etc. based on workload

---

**Ready to execute. Questions?**

For detailed info, see:
- `RECOMMENDED-MODELS.md` - Model selection
- `README-reasoning-llm-deployment.md` - Full reference
- `IMPLEMENTATION-GUIDE.md` - Technical details
