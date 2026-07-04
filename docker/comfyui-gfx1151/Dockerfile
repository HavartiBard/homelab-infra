# ComfyUI for AMD Strix Halo (Ryzen AI MAX+ 395 / Radeon 8060S, gfx1151) on goudai.
#
# Base image bundles AMD's pre-built environment: ROCm 7.2 + PyTorch 2.9.1 +
# flash-attention with *native* gfx1151 support (no HSA_OVERRIDE masquerade, no
# custom wheels). The older aidockorg/comfyui-rocm image shipped ROCm 6.0, which
# predates Strix Halo entirely and segfaults on `import torch` even with
# HSA_OVERRIDE_GFX_VERSION=11.0.0.
#
# This derived image:
#   1. Bakes a vanilla ComfyUI into /opt/ComfyUI so the runtime bind mounts
#      (models / output / custom node / workflows) overlay cleanly with no
#      startup copy step.
#   2. Adds the python deps the ComfyUI_LTX2_SM node imports beyond its own
#      requirements.txt (cv2, einops, av, imageio, scipy, peft, diffusers,
#      accelerate, gguf, omegaconf).
#   3. Pins transformers <5. The LTX2_SM gemma encoder reads
#      Gemma3Config.text_config.rope_local_base_freq, which exists in
#      transformers 4.5x (the node requires >=4.52) but was removed/restructured
#      in transformers 5.x (the base image ships 5.2.0).
#
# Build (on goudai):
#   docker build -t comfyui-gfx1151-ltx:local docker/comfyui-gfx1151
FROM ignatberesnev/comfyui-gfx1151:v0.2

RUN cp -a /opt/ComfyUI-pre-cloned /opt/ComfyUI \
 && pip3 install --no-cache-dir \
      "transformers>=4.52,<5" \
      diffusers accelerate gguf omegaconf peft \
      opencv-python-headless einops av imageio imageio-ffmpeg scipy \
 && mkdir -p /opt/ComfyUI/user/default/workflows /opt/ComfyUI/models/gguf
