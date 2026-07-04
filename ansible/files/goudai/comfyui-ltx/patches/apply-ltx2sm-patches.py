#!/usr/bin/env python3
"""Apply local fixes to the ComfyUI_LTX2_SM custom node for the HQ / two-stage
Sulphur workflows on goudai.

The node works out of the box for the single-stage "Minimal" workflow, but its
HQ (twostages_hq) + STG + block-streaming paths carry two upstream bugs that
crash the BestQuality/HQ 30s workflows:

  1. samplers.py  -- res2s_audio_video_denoising_loop() does not accept the
     `gpu_manager` kwarg, yet blocks.py passes it on the cached-transformer /
     streaming branch (its sibling euler_denoising_loop does accept it). Add the
     parameter and forward it to the three denoiser() calls, mirroring euler.

  2. LTX2_node.py -- the `video_stg_blocks` / `audio_stg_blocks` widgets are
     io.Int (scalars), but the pipeline expects list[int] (the node's own
     constants.py uses stg_blocks=[29]). When STG is enabled the bare int is
     passed through, and Perturbation.is_perturbed() then does `block in <int>`
     -> "TypeError: argument of type 'int' is not iterable". Wrap in a list.

  3. blocks.py -- DiffusionStage leaks its transformer in the gguf+offload
     path; two-stage modes then hold stage 1's weights while building stage
     2's, OOM-killing the host at stage-2 entry. Free it after each stage.

  4. merge_pipeline.py -- the twostages_hq stage-2 call passes the res2s
     denoising loop but no stepper, so the default EulerDiffusionStep is
     rejected by the res2s loop's isinstance guard. Pass Res2sDiffusionStep.

  5. constants.py -- STAGE_2_DISTILLED_SIGMA_VALUES starts at sigma=0.909,
     so twostages_hq stage 2 regenerates ~91% of the frame from scratch
     under a CFG-less SimpleDenoiser (the negative prompt has no effect).
     At portrait resolutions this reliably produces a translucent duplicate
     subject offset ~1/3 frame height, blended with the correctly-anchored
     stage-1 upscale. Root-caused by an isolated test that ruled out the
     upsampler/VAE round-trip, the res2s sampler math, and the SDPA
     attention kernel (all verified geometry/numerically exact) -- the
     ghost is painted by stage-2 diffusion itself. Trimming the schedule to
     a single low-sigma refinement step removes the artifact (confirmed on
     goudai 2026-07-02/03): single subject, no duplication, and stage 2
     runs ~3x faster (1 step vs 3).

Idempotent and version-safe: for each edit, if the patched text is already
present it is skipped; if neither the original nor patched text is found the
script exits non-zero so a node update that moved this code is caught loudly
instead of silently leaving a broken install.

Usage: apply-ltx2sm-patches.py <ComfyUI_LTX2_SM root dir>
Prints "CHANGED" if it modified anything, "UNCHANGED" otherwise.
"""
import sys
import os
import py_compile

# (relative path, original snippet, patched snippet)
EDITS = [
    # --- samplers.py: accept + forward gpu_manager in res2s ---
    (
        "LTX2/ltx_pipelines/utils/samplers.py",
        "    legacy_mode: bool = True,\n) -> tuple[LatentState | None, LatentState | None]:",
        "    legacy_mode: bool = True,\n    gpu_manager=None,\n) -> tuple[LatentState | None, LatentState | None]:",
    ),
    (
        "LTX2/ltx_pipelines/utils/samplers.py",
        "denoised_video_1, denoised_audio_1 = denoiser(transformer, video_state, audio_state, sigmas, step_idx)",
        "denoised_video_1, denoised_audio_1 = denoiser(transformer, video_state, audio_state, sigmas, step_idx, gpu_manager)",
    ),
    (
        "LTX2/ltx_pipelines/utils/samplers.py",
        "            sigmas=torch.stack([sub_sigma]).to(sigmas.device),\n            step_index=0,\n        )",
        "            sigmas=torch.stack([sub_sigma]).to(sigmas.device),\n            step_index=0,\n            gpu_manager=gpu_manager,\n        )",
    ),
    (
        "LTX2/ltx_pipelines/utils/samplers.py",
        "denoised_video_1, denoised_audio_1 = denoiser(transformer, video_state, audio_state, sigmas, n_full_steps)",
        "denoised_video_1, denoised_audio_1 = denoiser(transformer, video_state, audio_state, sigmas, n_full_steps, gpu_manager)",
    ),
    # --- LTX2_node.py: wrap STG block index in a list ---
    (
        "LTX2_node.py",
        "            video_stg_blocks=video_stg_blocks if video_stg_blocks>=0 else [],",
        "            video_stg_blocks=[video_stg_blocks] if video_stg_blocks>=0 else [],",
    ),
    (
        "LTX2_node.py",
        "            audio_stg_blocks=audio_stg_blocks if audio_stg_blocks>=0 else [],",
        "            audio_stg_blocks=[audio_stg_blocks] if audio_stg_blocks>=0 else [],",
    ),
    # --- samplers.py: drive ComfyUI's ProgressBar from the diffusion step
    #     loops so long renders show a live progress bar in the web UI. tqdm
    #     only writes a \r bar to stderr, which the ComfyUI frontend never
    #     sees; this wraps the same loops to also push progress events. (4th
    #     tuple element = expected match count.)
    (
        "LTX2/ltx_pipelines/utils/samplers.py",
        "from tqdm import tqdm\n",
        "from tqdm import tqdm\n\n\n"
        "def tqdm_ui(iterable, *args, **kwargs):\n"
        "    # Mirror tqdm's progress onto ComfyUI's ProgressBar (visible in the\n"
        "    # web UI). Falls back to plain tqdm if ComfyUI is unavailable.\n"
        "    seq = iterable if hasattr(iterable, \"__len__\") else list(iterable)\n"
        "    _pbar = None\n"
        "    try:\n"
        "        from comfy.utils import ProgressBar\n"
        "        _pbar = ProgressBar(len(seq))\n"
        "    except Exception:\n"
        "        _pbar = None\n"
        "    for _item in tqdm(seq, *args, **kwargs):\n"
        "        yield _item\n"
        "        if _pbar is not None:\n"
        "            try:\n"
        "                _pbar.update(1)\n"
        "            except Exception:\n"
        "                pass\n",
    ),
    (
        "LTX2/ltx_pipelines/utils/samplers.py",
        "tqdm(sigmas[:-1])",
        "tqdm_ui(sigmas[:-1])",
        2,
    ),
    (
        "LTX2/ltx_pipelines/utils/samplers.py",
        "tqdm(range(n_full_steps))",
        "tqdm_ui(range(n_full_steps))",
        1,
    ),
    # --- blocks.py: free the transformer after each diffusion stage ---
    # The gguf+offload branch of DiffusionStage.__call__ rebuilds
    # self._transformer unconditionally on every call, so the copy retained on
    # the instance is never reused -- it is a pure leak. In two-stage modes,
    # stage 1's weights stay resident while stage 2 dequantizes + LoRA-merges
    # its own copy, and the combined spike OOM-kills the 64 GB unified-memory
    # host right at "start inferS Stage 2" (kernel oom-killer, exit 137).
    (
        "LTX2/ltx_pipelines/utils/blocks.py",
        "        if gpu_manager is not None:\n"
        "                gpu_manager.unload_all_blocks_to_cpu()   \n"
        "        return video_state, audio_state",
        "        if gpu_manager is not None:\n"
        "                gpu_manager.unload_all_blocks_to_cpu()\n"
        "        if self._transformer is not None:\n"
        "            self._transformer = None\n"
        "            cleanup_memory()\n"
        "            try:\n"
        "                if hasattr(torch._C, \"_host_emptyCache\"):\n"
        "                    torch._C._host_emptyCache()\n"
        "            except Exception:\n"
        "                logger.warning(\"Host empty cache cleanup failed; ignoring.\", exc_info=True)\n"
        "        return video_state, audio_state",
    ),
    # --- merge_pipeline.py: stage 2 of twostages_hq needs a res2s stepper ---
    # The stage-2 call passes loop=res2s_audio_video_denoising_loop but omits
    # `stepper`, so DiffusionStage.__call__ defaults to EulerDiffusionStep and
    # the res2s loop raises "ValueError: stepper must be an instance of
    # Res2sDiffusionStep" (samplers.py guard). Pass the right stepper. Only
    # reachable once patch #3 stops the stage-2 OOM that used to hide it.
    (
        "LTX2/ltx_pipelines/merge_pipeline.py",
        "            state_outputs = self.stage_2(\n"
        "                denoiser=SimpleDenoiser(v_context_p, a_context_p),\n"
        "                sigmas=stage_2_sigmas,",
        "            state_outputs = self.stage_2(\n"
        "                denoiser=SimpleDenoiser(v_context_p, a_context_p),\n"
        "                stepper=Res2sDiffusionStep() if self.infer_mode == \"twostages_hq\" else None,\n"
        "                sigmas=stage_2_sigmas,",
    ),
    # --- constants.py: shorten the stage-2 sigma schedule ---
    (
        "LTX2/ltx_pipelines/utils/constants.py",
        "STAGE_2_DISTILLED_SIGMA_VALUES = [0.909375, 0.725, 0.421875, 0.0]",
        "STAGE_2_DISTILLED_SIGMA_VALUES = [0.421875, 0.0]",
    ),
]


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: apply-ltx2sm-patches.py <ComfyUI_LTX2_SM root dir>")
    root = sys.argv[1]
    changed = False
    touched = set()

    for edit in EDITS:
        rel, old, new = edit[0], edit[1], edit[2]
        want = edit[3] if len(edit) > 3 else 1
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            sys.exit(f"ERROR: {path} not found (unexpected node layout)")
        text = open(path, encoding="utf-8").read()
        if new in text:
            continue  # already patched (replacement present)
        if old not in text:
            sys.exit(
                f"ERROR: anchor not found in {rel}; node version changed, "
                "review apply-ltx2sm-patches.py before re-running"
            )
        if text.count(old) != want:
            sys.exit(
                f"ERROR: anchor in {rel} matched {text.count(old)} times, "
                f"expected {want}"
            )
        text = text.replace(old, new)
        if path not in touched and not os.path.exists(path + ".orig"):
            # one-time pristine backup
            with open(path + ".orig", "w", encoding="utf-8") as fh:
                fh.write(open(path, encoding="utf-8").read())
        open(path, "w", encoding="utf-8").write(text)
        touched.add(path)
        changed = True

    for path in touched:
        py_compile.compile(path, doraise=True)

    print("CHANGED" if changed else "UNCHANGED")


if __name__ == "__main__":
    main()
