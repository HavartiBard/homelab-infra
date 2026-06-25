# Open WebUI + ComfyUI Image Generation Plan

## Goal
Enable image generation inside the existing Open WebUI chat experience in the homelab.

## Recommended Architecture
- **Chat UI:** Open WebUI on `goudai`
- **Image backend:** ComfyUI on `goudai`
- **Starter model:** `FLUX.1-schnell`
- **Integration path:** Open WebUI image generation settings pointed at ComfyUI

## Why spraycheese (NVIDIA) approach
- Open WebUI already exists in repo and is deployed on `goudai`
- Open WebUI supports in-chat image generation via ComfyUI
- Repo already contains prior ComfyUI-related patterns in `ansible/playbooks/ai/deploy-sprite-smith.yml`
- spraycheese has proven NVIDIA CUDA support (verified via `nvidia-smi`)
- ROCm path on goudai fails (PyTorch/ComfyUI segfaults even with HSA override)

## Current Repo Facts
- Existing Open WebUI playbook:
  - `ansible/playbooks/ai/deploy-open-webui.yml`
- Existing Open WebUI compose template:
  - `ansible/files/goudai/open-webui/docker-compose.yml`
- Existing ComfyUI references:
  - `ansible/playbooks/ai/deploy-sprite-smith.yml` (deploys to Unraid, uses spraycheese as backend)
  - `ansible/files/sprite-smith/workflows/`
  - `ansible/files/goudai/comfyui/` (original ROCm attempt, now superseded by spraycheese)

## Implementation Plan

### Phase 1 — Design + deployment shape
1. Decide how ComfyUI will run
   - spraycheese (NVIDIA) via Docker Compose
   - ROCm path on goudai abandoned due to segfault issues
2. Choose storage locations for:
   - ComfyUI app/config
   - models/checkpoints
   - workflows
   - outputs
3. Network path: spraycheese LAN hostname (`spraycheese.lab.klsll.com`)

### Phase 2 — Add ComfyUI deployment to repo
1. Feature branch already exists: `feature/open-webui-comfyui-image-generation`
2. Playbook created:
   - `ansible/playbooks/ai/deploy-comfyui.yml` (targets `windows_gpu` = spraycheese)
3. Compose/template files under:
   - `ansible/files/spraycheese/comfyui/`
4. Include:
   - pinned image/version if using Docker
   - persistent volumes
   - port `8188`
   - `--listen 0.0.0.0`
   - timezone where applicable

### Phase 3 — Model provisioning
1. Start with `FLUX.1-schnell`
2. Decide whether model download is:
   - pre-seeded manually, or
   - automated in playbook/bootstrap step
3. Ensure model storage has enough space and a predictable path
4. Verify ComfyUI can load the selected checkpoint successfully

### Phase 4 — Workflow provisioning
1. Add one minimal text-to-image workflow for Open WebUI
2. Ensure workflow is exported in API format if required by Open WebUI
3. Store workflow JSON in repo
4. Keep initial workflow simple:
   - prompt
   - negative prompt (optional)
   - width/height
   - steps
   - sampler
   - save image output

### Phase 5 — Open WebUI integration
1. Update `ansible/files/goudai/open-webui/docker-compose.yml` as needed
2. Add env/config for image generation, likely:
   - `ENABLE_IMAGE_GENERATION=True`
   - `COMFYUI_BASE_URL=http://host.docker.internal:8188/`
3. Re-deploy Open WebUI
4. Enable image generation in Open WebUI admin settings if not fully env-driven

### Phase 6 — Verification
1. Verify ComfyUI health from `goudai`
2. Verify Open WebUI container can reach ComfyUI
3. Generate a test image in a chat window
4. Confirm output is visible/downloadable in chat
5. Confirm repeated generations work without manual intervention

## Validation Commands

### ComfyUI
```bash
curl http://<goudai-or-container-reachable-host>:8188/
```

### Open WebUI health
```bash
curl http://<goudai-ip>:8080/health
```

### Connectivity from Open WebUI container
```bash
docker exec open-webui wget -qO- http://host.docker.internal:8188/
```

## Risks / Open Questions
- Whether FLUX model files can be downloaded (requires HuggingFace token for gated files)
- Whether Open WebUI image settings need manual admin UI steps after deploy

## Suggested Next Session Task
Implement the first working version:
1. feature branch already exists: `feature/open-webui-comfyui-image-generation`
2. playbook already created: `ansible/playbooks/ai/deploy-comfyui.yml`
3. ComfyUI files/templates already created under `ansible/files/spraycheese/comfyui/`
4. Open WebUI already wired to ComfyUI via `open_webui_comfyui_base_url`
5. deploy ComfyUI to `spraycheese` and Open WebUI to `goudai`
6. verify in-chat image generation with `FLUX.1-schnell`
