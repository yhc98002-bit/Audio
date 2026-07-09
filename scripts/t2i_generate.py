#!/usr/bin/env python
"""Phase-3 T2I transfer — SDXL generation with stepwise x0-preview capture (music-method analog).

Same mechanism as the audio harness: monkeypatch scheduler.step to capture
`pred_original_sample` (the Tweedie/x0 analog) at fixed step indices {6,10,14,16,20}/30,
VAE-decode them as JPEG previews + save the final image. 8 seeds per prompt, deterministic
(seed = 20260612000 + pidx*100 + cand). Sharded by --worker-index/--num-workers. Resumable.

Env: t2i-adsr.  Output: orbit-research/adsr_phase2_20260604/t2i/images/{prompt_id}/
  cand{k}_final.jpg + cand{k}_step{S}.jpg ; gen ledger per worker.
"""
from __future__ import annotations
import argparse, json, time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
T2I = REPO / "orbit-research/adsr_phase2_20260604/t2i"
CAPTURE_STEPS = [6, 10, 14, 16, 20]
STEPS = 30
SEED_BASE = 20260612000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker-index", type=int, default=0)
    ap.add_argument("--num-workers", type=int, default=1)
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--res", type=int, default=768)
    args = ap.parse_args()

    import torch
    from diffusers import StableDiffusionXLPipeline
    pipe = StableDiffusionXLPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0", torch_dtype=torch.float16,
        variant="fp16", use_safetensors=True).to("cuda")
    # SDXL fp16 VAE is numerically unstable (NaN -> black previews). Keep the pipeline's own
    # fp16 VAE + internal upcast for finals (works), and use a SEPARATE fp32 VAE copy for our
    # manual x0-preview decodes (upcasting pipe.vae itself breaks the pipeline's fp16 decode path).
    import copy
    vae32 = copy.deepcopy(pipe.vae).to(torch.float32)
    pipe.set_progress_bar_config(disable=True)
    sched_cls = type(pipe.scheduler)
    orig_step = sched_cls.step

    prompts = [json.loads(l) for l in open(T2I / "t2i_prompts.jsonl")]
    mine = prompts[args.worker_index::args.num_workers]
    led_f = T2I / f"gen_ledger_w{args.worker_index}.jsonl"
    done = set()
    if led_f.exists():
        for l in open(led_f):
            try:
                d = json.loads(l); done.add((d["prompt_id"], d["cand"]))
            except Exception:
                pass
    led = led_f.open("a")

    def decode_x0(x0_lat):
        with torch.no_grad():
            img = vae32.decode(x0_lat.to(torch.float32) /
                               vae32.config.scaling_factor).sample
        img = torch.nan_to_num(img)
        img = ((img / 2 + 0.5).clamp(0, 1)[0].permute(1, 2, 0).float().cpu().numpy() * 255)
        from PIL import Image
        return Image.fromarray(img.astype("uint8"))

    n = 0; t0 = time.time()
    for row in mine:
        pid = row["prompt_id"]
        pdir = T2I / "images" / pid
        for k in range(args.seeds):
            if (pid, k) in done:
                continue
            seed = SEED_BASE + int(pid.split("_")[1]) * 100 + k
            cap = {}

            def step(self_, model_output, timestep, sample, *a, **kw):
                # SDXL calls step(..., return_dict=False) -> tuple, so pred_original_sample is
                # unavailable from the output. Compute the x0/Tweedie estimate directly BEFORE
                # delegating (epsilon-prediction: x0 = sample - sigma * eps).
                if self_.step_index is None:
                    self_._init_step_index(timestep)
                si = int(self_.step_index)
                if si in CAPTURE_STEPS and si not in cap:
                    sigma = self_.sigmas[si]
                    cap[si] = (sample - sigma * model_output).detach().clone()
                return orig_step(self_, model_output, timestep, sample, *a, **kw)

            sched_cls.step = step
            t1 = time.time()
            try:
                g = torch.Generator("cuda").manual_seed(seed)
                img = pipe(prompt=row["text"], num_inference_steps=STEPS,
                           guidance_scale=6.0, height=args.res, width=args.res,
                           generator=g).images[0]
            finally:
                sched_cls.step = orig_step
            pdir.mkdir(parents=True, exist_ok=True)
            img.save(pdir / f"cand{k}_final.jpg", quality=92)
            for si, lat in cap.items():
                decode_x0(lat).save(pdir / f"cand{k}_step{si:02d}.jpg", quality=85)
            led.write(json.dumps({"prompt_id": pid, "cand": k, "seed": seed,
                                  "captured_steps": sorted(cap), "wall_s": round(time.time() - t1, 2)}) + "\n")
            led.flush(); n += 1
            if n % 25 == 0:
                print(f"w{args.worker_index}: {n} gens ({n/max(time.time()-t0,1)*60:.1f}/min)", flush=True)
    led.close()
    print(f"T2I_WORKER_DONE w{args.worker_index} n={n}", flush=True)


if __name__ == "__main__":
    main()
