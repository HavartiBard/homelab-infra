# Quick Start: Deploy DeepSeek-R1-Distill Reasoning LLM to Jetson Nano

**Total Time: ~20 minutes (plus ~30 min engine build)**

## Prerequisites Checklist
- [ ] HuggingFace token with deepseek-ai access
- [ ] SSH access to jetson.lab (192.168.20.169)
- [ ] Build host with GPU (pve-01 or Unraid) OR local Docker with GPU
- [ ] 30GB+ free disk space on build host

## 1. Deploy Container to Jetson (5 min)

```bash
cd /home/james/projects/homelab-infra
export HUGGINGFACE_RO=$(op read "op://AI Wedge/HuggingFace Token/credential")

# Validate
ansible-playbook playbooks/misc/deploy-jetson-reasoning-llm.yml --syntax-check

# Dry-run
ansible-playbook playbooks/misc/deploy-jetson-reasoning-llm.yml \
  --check --diff --limit jetson.lab

# Deploy
ansible-playbook playbooks/misc/deploy-jetson-reasoning-llm.yml \
  --diff --limit jetson.lab -v
```

**Verify:**
```bash
ssh james@jetson.lab "docker ps | grep reasoning"
# Expected: reasoning-llm-dev running
```

## 2. Build TensorRT Engine (30 min, on build host)

**Option A: Using Docker (recommended)**
```bash
docker run --gpus all -it \
  -v /home/james/models:/models \
  -v /home/james/.cache/huggingface:/hf \
  -e HUGGINGFACE_HUB_TOKEN=$HUGGINGFACE_RO \
  dustynv/tensorrt_llm:0.12-r36.4.0 /bin/bash

# Inside container:
mkdir -p /models/reasoning-llm/deepseek-r1-distill-qwen-1.5b/{checkpoint,engine}
MODEL_DIR=$(huggingface-downloader "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B")

# Convert
python3 /opt/TensorRT-LLM/examples/llama/convert_checkpoint.py \
  --model_dir "$MODEL_DIR" \
  --output_dir /models/reasoning-llm/deepseek-r1-distill-qwen-1.5b/checkpoint \
  --dtype float16

# Build
trtllm-build \
  --checkpoint_dir /models/reasoning-llm/deepseek-r1-distill-qwen-1.5b/checkpoint \
  --output_dir /models/reasoning-llm/deepseek-r1-distill-qwen-1.5b/engine \
  --gemm_plugin float16 \
  --max_batch_size 1 \
  --max_input_len 2048 \
  --max_seq_len 8192
```

**Option B: Using Ansible (automated)**
```bash
# If build host has TensorRT container already set up:
HUGGINGFACE_RO=$YOUR_TOKEN \
ansible-playbook playbooks/misc/convert-jetson-reasoning-llm.yml --limit localhost
```

**Verify:**
```bash
ls -lh /home/james/models/reasoning-llm/deepseek-r1-distill-qwen-1.5b/engine/
# Expected: rank0.engine (~1.2GB)
```

## 3. Transfer Engine to Jetson (2 min)

```bash
rsync -avz --delete \
  /home/james/models/reasoning-llm/deepseek-r1-distill-qwen-1.5b/engine/ \
  james@jetson.lab:/home/james/models/reasoning-llm/deepseek-r1-distill-qwen-1.5b/engine/

# Verify
ssh james@jetson.lab "ls -lh /home/james/models/reasoning-llm/deepseek-r1-distill-qwen-1.5b/engine/"
```

## 4. Validate Deployment (3 min)

```bash
# Run validation
ansible-playbook playbooks/misc/validate-jetson-reasoning-llm.yml --limit jetson.lab

# Manual validation
ssh james@jetson.lab << 'EOF'
docker ps | grep reasoning
docker exec reasoning-llm-dev nvidia-smi
docker exec reasoning-llm-dev python3 -c "import tensorrt_llm; print(tensorrt_llm.__version__)"
ls -lh /home/james/models/reasoning-llm/deepseek-r1-distill-qwen-1.5b/engine/
EOF
```

## 5. Test Inference (Optional)

```bash
ssh james@jetson.lab "docker exec -it reasoning-llm-dev /bin/bash"

# Inside container:
python3 << 'EOF'
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B")
prompt = "Step-by-step: What is 2+2?"
tokens = tokenizer(prompt, return_tensors="pt")
print(f"✓ Tokenization works: {tokens.input_ids.shape[1]} tokens")
EOF
```

## 6. Integrate with OpenClaw

Model is now ready for OpenClaw integration at:
- **Host**: `jetson.lab` (192.168.20.169)
- **Model**: `deepseek-r1-distill-qwen-1.5b`
- **Container**: `reasoning-llm-dev`
- **Model Path**: `/home/james/models/reasoning-llm/deepseek-r1-distill-qwen-1.5b/engine`

Configure OpenClaw to use this model for agent reasoning tasks.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| nvidia-runtime not found | `ssh james@jetson.lab "sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker"` |
| HF token access denied | Ensure token has `deepseek-ai` model access |
| Engine build OOM | Use build host with >32GB RAM, not Jetson |
| Slow inference (<50 tok/s) | Check GPU memory usage with `nvidia-smi` |

## Rollback

```bash
ssh james@jetson.lab "docker compose -f /opt/reasoning-llm/docker-compose.yml down"
ssh james@jetson.lab "sudo rm -rf /opt/reasoning-llm"
```

## Documentation

Full docs: `/home/james/projects/homelab-infra/docs/jetson-reasoning-llm.md`
