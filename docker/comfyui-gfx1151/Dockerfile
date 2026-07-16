# ComfyUI for AMD Strix Halo (Ryzen AI MAX+ 395 / Radeon 8060S, gfx1151) on goudai.
#
# Base image bundles AMD's pre-built environment: ROCm 7.2 + PyTorch 2.9.1 +
# flash-attention with *native* gfx1151 support (no HSA_OVERRIDE masquerade, no
# custom wheels). The older aidockorg/comfyui-rocm image shipped ROCm 6.0, which
# predates Strix Halo entirely and segfaults on `import torch` even with
# HSA_OVERRIDE_GFX_VERSION=11.0.0.
#
# This derived image:
#   1. Bakes ComfyUI into /opt/ComfyUI so the runtime bind mounts
#      (models / output / custom node / workflows) overlay cleanly with no
#      startup copy step.
#   2. Checks out COMFYUI_VERSION over the base image's baked v0.15.0 clone.
#      Krea2 ConvRot int8mixed checkpoints need the comfy/ops.py quant support
#      added in v0.26+ (v0.15.0 can't detect the architecture at all); pinned
#      to v0.27.0 to match spraycheese for apples-to-apples comparisons.
#      comfy-kitchen's ROCm/Triton fast path isn't auto-enabled until v0.28.0
#      (matrix-core GPUs only, which gfx1151 isn't), so this runs the plain
#      PyTorch fallback path on goudai — correct, just not kernel-accelerated.
#   3. Reinstalls ComfyUI's own requirements.txt for the new version, but
#      strips the unpinned torch/torchvision/torchaudio lines first so pip
#      doesn't clobber the ROCm 7.2 wheels the base image ships.
#   4. Adds the python deps the ComfyUI_LTX2_SM node imports beyond its own
#      requirements.txt (cv2, einops, av, imageio, scipy, peft, diffusers,
#      accelerate, gguf, omegaconf).
#   5. Pins transformers <5. The LTX2_SM gemma encoder reads
#      Gemma3Config.text_config.rope_local_base_freq, which exists in
#      transformers 4.5x (the node requires >=4.52) but was removed/restructured
#      in transformers 5.x (the base image ships 5.2.0).
#
# Build (on goudai):
#   docker build -t comfyui-gfx1151-ltx:local docker/comfyui-gfx1151
FROM ignatberesnev/comfyui-gfx1151:v0.2

ARG COMFYUI_VERSION=v0.27.0

RUN cp -a /opt/ComfyUI-pre-cloned /opt/ComfyUI \
 && cd /opt/ComfyUI \
 && git fetch --tags origin \
 && git checkout "${COMFYUI_VERSION}" \
 && grep -vE '^(torch|torchvision|torchaudio)([><=~ ]|$)' requirements.txt > /tmp/requirements-no-torch.txt \
 && pip3 install --no-cache-dir -r /tmp/requirements-no-torch.txt \
 && rm /tmp/requirements-no-torch.txt \
 && pip3 install --no-cache-dir \
      "transformers>=4.52,<5" \
      diffusers accelerate gguf omegaconf peft \
      opencv-python-headless einops av imageio imageio-ffmpeg scipy \
 && mkdir -p /opt/ComfyUI/user/default/workflows /opt/ComfyUI/models/gguf
