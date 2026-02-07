# Jetson TensorRT-LLM Deployment

## Overview
- Deploys a persistent `dustynv/tensorrt_llm:0.12-r36.4.0` container on Jetson Orin Nano with Docker Compose managed by Ansible.
- Model/cache directories persist under `/home/james/models/tensorrt_llm` and `/home/james/.cache/huggingface`.
- Hugging Face token needs to be supplied via `HUGGINGFACE_RO` or a 1Password item named `TensorRT LLM Hugging Face Token`.

## Runbook
1. Ensure you can SSH to Jetson (inventory host `jetson.lab`, user `james`).
2. Run the deployment:

```
HUGGINGFACE_RO=$TOKEN ansible-playbook playbooks/misc/deploy-jetson-trtllm.yml --limit jetson.lab
```

3. Interactive conversion steps (execute after deployment):

```
docker compose exec trtllm-dev /bin/bash
MODEL="meta-llama/Llama-3.2-3B-Instruct"
OUT="/data/models/tensorrt_llm/llama-3.2-3b-instruct"
MODEL_DIR="$(huggingface-downloader "$MODEL")"
python3 /opt/TensorRT-LLM/examples/llama/convert_checkpoint.py \
  --model_dir "$MODEL_DIR" \
  --output_dir "$OUT/checkpoint" \
  --dtype float16
trtllm-build \
  --checkpoint_dir "$OUT/checkpoint" \
  --output_dir "$OUT/engine" \
  --gemm_plugin float16 \
  --max_batch_size 1 \
  --max_input_len 2048 \
  --max_seq_len 8192
```

4. Validate conversion artifacts exist under `/home/james/models/tensorrt_llm/llama-3.2-3b-instruct`.
5. Optionally automate conversion via Ansible (keeps arguments in sync with the documented workflow)

```
ANSIBLE_SSH_ARGS='-o ControlMaster=no -o ControlPersist=0' \
ANSIBLE_VAULT_PASSWORD_FILE="$ANSIBLE_VAULT_PASSWORD" \
HUGGINGFACE_RO="$HUGGINGFACE_RO" \
ansible-playbook playbooks/misc/convert-jetson-trtllm.yml --limit jetson.lab
```

The `convert-jetson-trtllm` playbook runs the same download/convert/build pipeline inside `trtllm-dev`, placing checkpoints at `/home/james/models/tensorrt_llm/llama-3.2-3b-instruct/checkpoint` and engines under `/home/james/models/tensorrt_llm/llama-3.2-3b-instruct/engine`.

### Qwen coder fallback
For the Orin Nano’s 8 GB GPU, `EasierAI/Qwen-2.5-Coder-3B-Instruct` is a fully open-source coder workload that fits in float16 and is accessible without gating (the instruct variant matches what Jetson-LLM consumes). Run the dedicated playbook:

```
ANSIBLE_SSH_ARGS='-o ControlMaster=no -o ControlPersist=0' \
ANSIBLE_VAULT_PASSWORD_FILE="$ANSIBLE_VAULT_PASSWORD" \
HUGGINGFACE_RO="$HUGGINGFACE_RO" \
ansible-playbook playbooks/misc/convert-jetson-qwen3b.yml --limit jetson.lab
```

Check the engine output under `/home/james/models/tensorrt_llm/qwen-2.5-coder-3b/engine` and use the same runbook steps to serve it once the conversion finishes.

## Troubleshooting
- If `huggingface-cli whoami` fails inside container, ensure `HUGGINGFACE_RO` grants model access and retry.
- `huggingface-downloader` requires `HF_HOME` pointing to `/data/hf`; ensure this path has write permissions and enough space.
- If `docker compose exec` reports permission errors, rerun with `sudo` on the Jetson host or add your user to the `docker` group (already attempted by the role).

## Credential management & secrets handling
- The Jetson role reads `HUGGINGFACE_RO` exclusively from the controller environment (`lookup('env', 'HUGGINGFACE_RO')`). There is no built-in call to 1Password; set the variable yourself (e.g., by exporting it from your shell or reading from a secret store prior to running the playbook) so the Docker Compose `.env` can source it without embedding secrets in version control.
- Because `inventory/host_vars/jetson.lab.yml` is encrypted (ANSIBLE_VAULT), the playbook still requires `ANSIBLE_VAULT_PASSWORD_FILE` or `OP_SERVICE_ACCOUNT_TOKEN` to decrypt any host-specific vars before tasks run. Export this token on the control host prior to invoking `ansible-playbook`.

## Environment variable passing rules
- Ansible resolves `lookup('env', ...)` variables on the controller, so ensure `HUGGINGFACE_RO` is exported (or read from 1Password) *before* invoking `ansible-playbook`. Remote hosts do not inherit those environment variables automatically.
- If a task needs an environment variable on the remote host, explicitly set it via the task’s `environment:` block or via a rendered file/template that Docker Compose consumes (`.env` in this case). Relying on the remote shell’s environment (e.g., adding exports to `~/.bashrc`) is fragile and not used in these playbooks.
- Keep `.env`/`host_vars` in git-free directories for this deployment; use templating and Ansible variables to drive config without inserting secrets directly.

## Rollback
- `docker compose down` from `/opt/trtllm` to stop the service and clean the network.
