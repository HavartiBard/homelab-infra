# comfyui-gfx1151

ComfyUI image for **goudai** — an AMD Strix Halo box (Ryzen AI MAX+ 395 / Radeon
8060S iGPU, `gfx1151`, 61 GiB unified memory). Purpose-built as a long-form /
high-quality LTX-2.3 video render node (the `ComfyUI_LTX2_SM` "Sulphur" workflow
family).

## Why a custom image

| | aidockorg/comfyui-rocm (old) | this image |
|---|---|---|
| ROCm | 6.0.0 (pre–Strix Halo) | 7.2 (native gfx1151) |
| PyTorch | segfaults on `import torch` | 2.9.1, `cuda.is_available()` → True |
| GPU id | `gfx1100` via `HSA_OVERRIDE` masquerade | native `gfx1151`, no override |

Base: [`ignatberesnev/comfyui-gfx1151`](https://github.com/IgnatBeresnev/comfyui-gfx1151)
(AMD `rocm/pytorch` ROCm 7.2 + flash-attention, no custom wheels).

## Build & run

The deployment (image build + compose + gemma symlink + validation) is automated:

```bash
cd ansible
ansible-playbook playbooks/ai/deploy-comfyui-ltx-goudai.yml --limit goudai
```

Manual equivalent on goudai:

```bash
docker build -t comfyui-gfx1151-ltx:local docker/comfyui-gfx1151
cd /opt/comfyui && docker compose up -d
```

URL: <http://192.168.20.150:8188> (container `comfyui`, port 8188).

## Notes

- Models / custom node / output / workflows are bind-mounted from the Unraid NFS
  share `/mnt/ai-models/comfyui` (shared homelab model library).
- `ComfyUI_LTX2_SM` lists the gemma text encoder from the **`gguf`** folder, so
  `models/gguf/gemma-3-12b-it-qat-Q4_0.gguf` must exist (a symlink to the copy in
  `models/text_encoders/`). The playbook ensures this.
- Launch flags: `--use-pytorch-cross-attention --disable-mmap` (mmap above 64 GB
  is slow on Strix Halo; pytorch cross-attention avoids flaky AOTriton flash
  kernels — the model is memory-bound, not attention-bound).
