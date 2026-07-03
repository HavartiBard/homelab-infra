# Open WebUI + ComfyUI Image Generation

## Scope
This runbook deploys ComfyUI on `spraycheese` (NVIDIA), wires Open WebUI to it, and documents the remaining one-time Open WebUI admin steps to upload the workflow and map FLUX-specific nodes.

## Files
- `ansible/playbooks/ai/deploy-comfyui.yml`
- `ansible/playbooks/ai/deploy-open-webui.yml`
- `ansible/files/spraycheese/comfyui/docker-compose.yml`
- `ansible/files/spraycheese/comfyui/workflows/open-webui-flux-schnell-api.json`
- `ansible/files/goudai/open-webui/docker-compose.yml`

## Storage layout on `spraycheese`
- ComfyUI compose: `/opt/comfyui/docker-compose.yml`
- Models: `/mnt/ai-models/comfyui/models`
- Custom nodes: `/mnt/ai-models/comfyui/custom-nodes`
- Outputs: `/mnt/ai-models/comfyui/output`
- Workflow exports: `/mnt/ai-models/comfyui/workflows`
- Container home: `/mnt/ai-models/comfyui/home`

## Required FLUX.1-schnell model files
Place these files on `spraycheese` before testing image generation:

```text
/mnt/ai-models/comfyui/models/diffusion_models/flux1-schnell.safetensors
/mnt/ai-models/comfyui/models/text_encoders/clip_l.safetensors
/mnt/ai-models/comfyui/models/text_encoders/t5xxl_fp8_e4m3fn.safetensors
/mnt/ai-models/comfyui/models/vae/ae.safetensors
```

Reference downloads:
- `flux1-schnell.safetensors`: <https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/flux1-schnell.safetensors>
- `clip_l.safetensors`: <https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors?download=true>
- `t5xxl_fp8_e4m3fn.safetensors`: <https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors?download=true>
- `ae.safetensors`: <https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/ae.safetensors?download=true>

## Deploy
Run from `ansible/`:

```bash
ansible-playbook playbooks/ai/deploy-comfyui.yml --syntax-check
ansible-playbook playbooks/ai/deploy-open-webui.yml --syntax-check
ansible-playbook playbooks/ai/deploy-comfyui.yml --check --diff --limit unraid,spraycheese
ansible-playbook playbooks/ai/deploy-open-webui.yml --check --diff --limit goudai
ansible-playbook playbooks/ai/deploy-comfyui.yml --diff --limit unraid,spraycheese -v
ansible-playbook playbooks/ai/deploy-open-webui.yml --diff --limit goudai -v
```

**For spraycheese (NVIDIA):** The playbook uses the existing `yanwk/comfyui-boot:cu130-slim` image which has CUDA 13.0 support. No manual pull required.

`deploy-comfyui.yml` also prepares `/mnt/user/ai-models/comfyui` on Unraid and enforces shared-write permissions (`0777` on directories, `0666` on files) so the SMB share remains writable from Windows.

`deploy-comfyui.yml` validates the required FLUX files by default. On `goudai` it is configured for an AMD ROCm container image and also performs a HIP availability preflight before starting the stack.

To ask Ansible to download the FLUX artifacts before validation:

```bash
export HUGGINGFACE_RO=hf_...   # repo-standard name; HF_TOKEN and HUGGINGFACE_HUB_TOKEN also work
ansible-playbook playbooks/ai/deploy-comfyui.yml --diff --limit goudai -e comfyui_download_models=true -v
```

To stage ComfyUI before the model files are present, temporarily override the validation guard:

```bash
ansible-playbook playbooks/ai/deploy-comfyui.yml --diff --limit goudai -e comfyui_validate_models=false -v
```

## One-time Open WebUI admin setup
1. Log into `https://chat.klsll.com` as an admin.
2. Go to **Admin Panel → Settings → Images**.
3. Confirm **Image Generation** is enabled.
4. Under **Create Image**:
   - Engine: `ComfyUI`
   - ComfyUI Base URL: `http://host.docker.internal:8188/`
   - Model: `flux1-schnell.safetensors`
5. Upload workflow file:
   - `/mnt/ai-models/comfyui/workflows/open-webui-flux-schnell-api.json`
6. Map the workflow nodes:
   - Prompt → node `19`, key `text`
   - Model → node `10`, key `unet_name`
   - Width → node `18`, key `width`
   - Height → node `18`, key `height`
   - Steps → node `20`, key `steps`
   - Seed → node `20`, key `seed`
7. Save settings.

## Verify
### ComfyUI host health
```bash
curl http://spraycheese.lab.klsll.com:8188/
```

### Open WebUI health
```bash
curl http://<goudai-ip>:8080/health
```

### Connectivity from the Open WebUI container
```bash
ssh goudai 'docker exec open-webui wget -qO- http://spraycheese.lab.klsll.com:8188/ >/dev/null && echo ok'
```

### Container status on `goudai`
```bash
ssh goudai 'docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "open-webui|comfyui"'
```

### Manual app verification
1. Ask the chat model for an image prompt.
2. Edit the message so it contains only the image prompt text.
3. Click the image generation action under the message.
4. Confirm the image renders in chat and can be downloaded.
5. Repeat once to confirm repeat generations succeed.

## Notes
- `ENABLE_IMAGE_GENERATION=True` and `COMFYUI_BASE_URL=http://spraycheese.lab.klsll.com:8188/` are persisted through the Open WebUI compose template.
- The shipped workflow is FLUX-specific, so the model mapping uses `unet_name` instead of the default `ckpt_name`.
- `deploy-comfyui.yml` now targets `spraycheese` with NVIDIA CUDA support via `gpus: all` and the `yanwk/comfyui-boot:cu130-slim` image (CUDA 13.0).
- The ComfyUI share prep step runs on `unraid`, so use `--limit unraid,spraycheese` when deploying ComfyUI if you want the SMB permission fix applied.
- spraycheese is reachable via its LAN hostname: `spraycheese.lab.klsll.com`.
