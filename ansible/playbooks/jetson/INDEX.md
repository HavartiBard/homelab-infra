# Jetson Reasoning LLM Deployment - Complete Playbook Index

**Status**: ✓ Ready for execution (Phase 2 - Model Deployment)

**Completion**: All playbooks created, syntax-checked, and documented

---

## Quick Start (5-minute read)

1. **Start here**: [DEPLOYMENT-EXECUTION.md](DEPLOYMENT-EXECUTION.md)
   - Step-by-step execution instructions
   - Timeline and expected outputs
   - Troubleshooting quick reference

2. **Choose your model**: [RECOMMENDED-MODELS.md](RECOMMENDED-MODELS.md)
   - Qwen3-1.7B-Thinking (BEST - recommended)
   - DeepSeek-R1-Distill-1.5B (safe alternative)
   - DeepSeek-R1-Distill-8B (premium quality)

3. **Deploy**: Run playbooks in order
   ```bash
   cd /home/james/projects/homelab-infra/ansible

   # Step 1: Base infrastructure (30 min)
   ansible-playbook playbooks/jetson/deploy-reasoning-llm-base.yml --limit jetson.lab -v

   # Step 2: Convert primary model (90-120 min)
   ansible-playbook playbooks/jetson/convert-qwen3-1.7b-thinking.yml --limit jetson.lab -v

   # Step 3: Validate (5 min)
   ansible-playbook playbooks/jetson/validate-reasoning-llm.yml \
     -e "trtllm_model_to_validate=qwen3-1.7b-thinking" \
     --limit jetson.lab -v
   ```

---

## Playbook Reference

### Foundation Playbooks (Phase 1)

#### `deploy-reasoning-llm-base.yml` (30-45 min)
**Purpose**: One-time setup of TensorRT-LLM stack

**What it does**:
- Install Docker and NVIDIA container toolkit
- Configure NVIDIA container runtime
- Create persistent directories for models
- Deploy TensorRT-LLM container
- Validate HuggingFace token

**Status**: ✓ Tested, ready to run
**Run once**: Yes

**Command**:
```bash
ansible-playbook playbooks/jetson/deploy-reasoning-llm-base.yml --limit jetson.lab -v
```

---

### Model Conversion Playbooks (Phase 2)

#### `convert-qwen3-1.7b-thinking.yml` ⭐ RECOMMENDED
**Purpose**: Deploy primary reasoning model (best balance)

**Model specs**:
- Parameters: 1.7B
- VRAM: 3-4GB
- Speed: 100-120 tokens/sec
- Quality: Excellent reasoning
- Memory margin: 4-5GB free ✓

**Command**:
```bash
ansible-playbook playbooks/jetson/convert-qwen3-1.7b-thinking.yml --limit jetson.lab -v
```

**Duration**: 90-120 minutes

---

#### `convert-deepseek-r1-distill-1.5b.yml`
**Purpose**: Deploy conservative alternative (memory-safe)

**Model specs**:
- Parameters: 1.5B
- VRAM: 2.5GB (FP16) or 1.2GB (INT8)
- Speed: 80-120 tokens/sec
- Quality: Excellent reasoning
- Memory margin: 5.5GB free ✓✓ (safest)

**Command**:
```bash
ansible-playbook playbooks/jetson/convert-deepseek-r1-distill-1.5b.yml --limit jetson.lab -v
```

**Duration**: 60-90 minutes

**When to use**:
- Memory is tight (other services present)
- Want most conservative margins
- Need explicit CoT outputs
- Official NVIDIA support important

---

#### `convert-deepseek-r1-distill-8b.yml`
**Purpose**: Deploy premium model (best reasoning, risky memory)

**Model specs**:
- Parameters: 8B
- VRAM: 6-7GB (4-bit quantized - AGGRESSIVE)
- Speed: 30-40 tokens/sec
- Quality: Best-in-class reasoning
- Memory margin: 1GB free ⚠️ (high risk)

**Command**:
```bash
ansible-playbook playbooks/jetson/convert-deepseek-r1-distill-8b.yml --limit jetson.lab -v
```

**Duration**: 180+ minutes (very long)

**⚠️ Only use if**:
- Jetson fully dedicated to inference
- No competing services
- Swap space configured (4GB minimum)
- Acceptable to manage potential OOM
- Reasoning quality critical

---

#### `convert-reasoning-llm-template.yml`
**Purpose**: Generic template for any HuggingFace model

**Use case**: Deploy custom models not in the three recommended variants

**Command**:
```bash
ansible-playbook playbooks/jetson/convert-reasoning-llm-template.yml \
  -e "trtllm_conversion_model='<model-id>'" \
  -e "trtllm_conversion_alias='<alias>'" \
  -e "trtllm_conversion_convert_script='/opt/TensorRT-LLM/examples/<family>/convert_checkpoint.py'" \
  --limit jetson.lab -v
```

**Status**: ✓ Template ready for customization

---

### Validation & Monitoring (Phase 3)

#### `validate-reasoning-llm.yml` (5-10 min)
**Purpose**: Test model loading and inference

**Checks**:
- Container running
- GPU memory available
- Model engine files exist
- Model loads in Python
- Basic inference works

**Command**:
```bash
ansible-playbook playbooks/jetson/validate-reasoning-llm.yml \
  -e "trtllm_model_to_validate=qwen3-1.7b-thinking" \
  --limit jetson.lab -v
```

**Status**: ✓ Ready for use after each model deployment

**Run**: After each model conversion

---

#### `health-check-reasoning-llm.yml` (1-2 min)
**Purpose**: Monitor ongoing deployment health

**Metrics**:
- Container uptime and restart count
- GPU temperature and utilization
- Memory usage (host and GPU)
- Available disk space
- TensorRT version
- Recent error logs

**Command**:
```bash
ansible-playbook playbooks/jetson/health-check-reasoning-llm.yml --limit jetson.lab
```

**Status**: ✓ Ready for scheduled execution

**Recommended schedule**:
- Every 6 hours (cron)
- Before/after critical operations
- When troubleshooting issues

---

### Maintenance (Phase 4)

#### `rollback-reasoning-llm.yml`
**Purpose**: Safe removal of models or entire stack

**Modes**:

Remove single model:
```bash
ansible-playbook playbooks/jetson/rollback-reasoning-llm.yml \
  -e "trtllm_rollback_mode=model" \
  -e "trtllm_model_to_remove=qwen3-1.7b-thinking" \
  --limit jetson.lab -v
```

Remove entire stack:
```bash
ansible-playbook playbooks/jetson/rollback-reasoning-llm.yml \
  -e "trtllm_rollback_mode=all" \
  --limit jetson.lab -v
```

**Status**: ✓ Ready for recovery/cleanup

---

#### `deploy-all-reasoning-models.yml`
**Purpose**: Orchestrate deployment of all three recommended models

**What it does**:
1. Deploy base infrastructure
2. Convert each model sequentially
3. Validate each model
4. Report summary

**Command**:
```bash
ansible-playbook playbooks/jetson/deploy-all-reasoning-models.yml --limit jetson.lab -v
```

**Duration**: 4-5 hours (all three models)

**Status**: ✓ Ready for full deployment

**Use case**: Full deployment for comparison/testing

---

## Documentation

### Essential References

#### `DEPLOYMENT-EXECUTION.md` (START HERE)
- Step-by-step execution guide
- Prerequisites checklist
- Expected outputs at each phase
- Troubleshooting quick reference
- Timeline and success criteria
- **Action**: Read before first deployment

#### `RECOMMENDED-MODELS.md`
- Model selection guide
- Detailed specs for each model
- Performance expectations
- Integration with OpenClaw
- Deployment strategy (3 phases)
- **Action**: Read to choose primary model

#### `README-reasoning-llm-deployment.md`
- Comprehensive reference
- All configuration parameters
- Model family specifics
- Advanced customization
- Integration examples
- **Action**: Reference during deployment

#### `IMPLEMENTATION-GUIDE.md`
- Technical architecture
- Role structure and inheritance
- Variable hierarchy
- Testing checklist
- Success criteria
- **Action**: Reference for customization

---

## Deployment Workflow

### Recommended 3-Phase Approach

**Phase 1: Base Infrastructure**
```bash
ansible-playbook playbooks/jetson/deploy-reasoning-llm-base.yml --limit jetson.lab -v
# Duration: 30-45 min
# Run once
```

**Phase 2: Primary Model**
```bash
# Choose ONE:
# - Qwen3-1.7B-Thinking (RECOMMENDED)
# - DeepSeek-R1-Distill-1.5B (safe)
# - DeepSeek-R1-Distill-8B (advanced)

ansible-playbook playbooks/jetson/convert-qwen3-1.7b-thinking.yml --limit jetson.lab -v
# Duration: 90-120 min
```

**Phase 3: Validation**
```bash
ansible-playbook playbooks/jetson/validate-reasoning-llm.yml \
  -e "trtllm_model_to_validate=qwen3-1.7b-thinking" \
  --limit jetson.lab -v
# Duration: 5-10 min
```

**Phase 4: Monitoring Setup**
```bash
# Schedule health checks
crontab -e
# Add: 0 */6 * * * cd /home/james/projects/homelab-infra/ansible && \
#   ansible-playbook playbooks/jetson/health-check-reasoning-llm.yml --limit jetson.lab
```

**Total time**: 2-3 hours

---

## File Organization

```
playbooks/jetson/
├── FOUNDATION (Deploy once)
│   └── deploy-reasoning-llm-base.yml
├── MODELS (Deploy per model)
│   ├── convert-qwen3-1.7b-thinking.yml ⭐ PRIMARY
│   ├── convert-deepseek-r1-distill-1.5b.yml (alternative)
│   ├── convert-deepseek-r1-distill-8b.yml (advanced)
│   ├── convert-reasoning-llm-template.yml (custom)
│   └── deploy-all-reasoning-models.yml (all 3)
├── VALIDATION (Run after each model)
│   ├── validate-reasoning-llm.yml
│   ├── health-check-reasoning-llm.yml
│   └── rollback-reasoning-llm.yml
└── DOCUMENTATION
    ├── INDEX.md (this file)
    ├── DEPLOYMENT-EXECUTION.md (START HERE)
    ├── RECOMMENDED-MODELS.md (model selection)
    ├── README-reasoning-llm-deployment.md (full reference)
    └── IMPLEMENTATION-GUIDE.md (technical details)
```

---

## Success Criteria

Deployment successful when:

- [ ] Base infrastructure deployed (container running)
- [ ] Primary model converted (engine files present)
- [ ] Model validation passes (loads without errors)
- [ ] Health check shows normal metrics
- [ ] Can list models: `ssh jetson.lab ls /home/james/models/tensorrt_llm/*/engine/`
- [ ] Health checks scheduled in cron

---

## Common Tasks

### Deploy Qwen3-1.7B-Thinking (Recommended)
```bash
cd /home/james/projects/homelab-infra/ansible
ansible-playbook playbooks/jetson/convert-qwen3-1.7b-thinking.yml --limit jetson.lab -v
ansible-playbook playbooks/jetson/validate-reasoning-llm.yml \
  -e "trtllm_model_to_validate=qwen3-1.7b-thinking" --limit jetson.lab -v
```

### Add Second Model (Conservative Alternative)
```bash
ansible-playbook playbooks/jetson/convert-deepseek-r1-distill-1.5b.yml --limit jetson.lab -v
ansible-playbook playbooks/jetson/validate-reasoning-llm.yml \
  -e "trtllm_model_to_validate=deepseek-r1-distill-1.5b" --limit jetson.lab -v
```

### Check Health Status
```bash
ansible-playbook playbooks/jetson/health-check-reasoning-llm.yml --limit jetson.lab
```

### Remove Model
```bash
ansible-playbook playbooks/jetson/rollback-reasoning-llm.yml \
  -e "trtllm_rollback_mode=model" \
  -e "trtllm_model_to_remove=qwen3-1.7b-thinking" \
  --limit jetson.lab -v
```

### Full Reset (if needed)
```bash
ansible-playbook playbooks/jetson/rollback-reasoning-llm.yml \
  -e "trtllm_rollback_mode=all" --limit jetson.lab -v
ansible-playbook playbooks/jetson/deploy-reasoning-llm-base.yml --limit jetson.lab -v
```

---

## Next Steps

1. **Read**: [DEPLOYMENT-EXECUTION.md](DEPLOYMENT-EXECUTION.md)
2. **Choose**: Primary model from [RECOMMENDED-MODELS.md](RECOMMENDED-MODELS.md)
3. **Deploy**: Follow Phase 1-4 steps
4. **Validate**: Run health check
5. **Monitor**: Schedule health checks
6. **Integrate**: Connect with OpenClaw

---

## Support & Escalation

- **Syntax errors**: All playbooks pass `--syntax-check`
- **Dry-run fails**: Check prerequisites in DEPLOYMENT-EXECUTION.md
- **Conversion hangs**: Monitor with `docker logs trtllm-dev`
- **Memory issues**: See RECOMMENDED-MODELS.md troubleshooting
- **Validation fails**: Check container and engine files with SSH

---

**Ready to begin deployment. See DEPLOYMENT-EXECUTION.md for step-by-step instructions.**
