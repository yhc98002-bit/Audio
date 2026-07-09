"""PI listening-packet generator (Phase B prep §D follow-up, 2026-05-22).

Re-decodes σ ∈ {0.9, 0.7, 0.5} intermediate audio + final audio for 3 calibration
prompts (dev_0010 / dev_0026 / dev_0044) using the same deterministic config the
v2 calibration run used (seeds = base + sorted-index, formal Phase B sampler
binding: cfg_type='cfg', ERG=False, guidance_interval=0.5, infer_step=30,
cfg_scale=5.0). This is not a new experiment — it is the audio-save step that
was missing from the v2 calibration script. Trajectories are bit-identical to
the v2 run.

PI candidate decision rule:
- If σ=0.9 remains musically interpretable → K=3 = {0.9, 0.7, 0.5}
- If σ=0.9 is too degraded → K=3 = {0.8, 0.7, 0.5}
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

from mprm.common.seeding import seed_everything
from mprm.data.audio_io import save_audio
from mprm.data.prompts import Prompt


def _pick(target, sigmas):
    return min(range(len(sigmas)), key=lambda k: abs(sigmas[k] - target))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompts-json", default="orbit-research/SIGMA_CALIBRATION_PROMPTS.json")
    parser.add_argument("--dev-jsonl", default="configs/prompts/dev.jsonl")
    parser.add_argument("--prompt-ids", default="dev_0010,dev_0026,dev_0044")
    parser.add_argument("--target-sigmas", default="0.9,0.7,0.5")
    parser.add_argument("--out-dir", default="papers/diagnostic/pi_listening_packet")
    parser.add_argument("--seed-base", type=int, default=42)
    parser.add_argument("--cfg-scale", type=float, default=5.0)
    parser.add_argument("--infer-step", type=int, default=30)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target_sigmas = [float(x) for x in args.target_sigmas.split(",") if x.strip()]
    target_pids = [x.strip() for x in args.prompt_ids.split(",") if x.strip()]

    # The v2 calibration used: seed = args.seed_base + p_idx where p_idx is the
    # index of the prompt in the SORTED excluded_prompt_ids list. To reproduce
    # the same trajectories we must use the same (prompt, seed) pairs.
    cal = json.loads(Path(args.prompts_json).read_text())
    sorted_ids = sorted(cal["excluded_prompt_ids"])
    seed_for_pid = {pid: args.seed_base + i for i, pid in enumerate(sorted_ids)}

    prompts_by_id: dict[str, dict] = {}
    with open(args.dev_jsonl) as f:
        for line in f:
            p = json.loads(line)
            prompts_by_id[p["prompt_id"]] = p

    from mprm.inference.ace_step import AceStepModel
    model = AceStepModel()

    manifest = {
        "schema_version": "pi_listening_packet_v1",
        "generated": "2026-05-22",
        "purpose": (
            "PI listening packet for σ K=3 decision. Audio re-decoded from the "
            "same deterministic config used in σ_calibration_v2 (seeds = "
            "base + sorted-prompt-index). Trajectories are bit-identical to "
            "the v2 calibration run."
        ),
        "scope": {
            "cfg_type": "cfg",
            "erg": False,
            "guidance_interval": 0.5,
            "cfg_scale": args.cfg_scale,
            "infer_step": args.infer_step,
        },
        "items": [],
    }

    for pid in target_pids:
        if pid not in prompts_by_id:
            print(f"WARN: {pid} not in dev set, skipping", flush=True)
            continue
        if pid not in seed_for_pid:
            print(f"WARN: {pid} not in SIGMA_CALIBRATION_PROMPTS.json, skipping", flush=True)
            continue
        pd = prompts_by_id[pid]
        prompt = Prompt(
            prompt_id=pid,
            text=pd.get("text", ""),
            lyrics=pd.get("lyrics"),
            structure_hint=pd.get("structure_hint"),
            duration_target=float(pd.get("duration_target", 30.0)),
        )
        seed = seed_for_pid[pid]
        print(f"[{pid}] seed={seed} text='{prompt.text[:60]}{'...' if len(prompt.text)>60 else ''}'",
              flush=True)
        seed_everything(seed)
        res = model.sample(
            prompt, seed=seed, cfg_scale=args.cfg_scale, steps=args.infer_step,
            return_trajectory=True,
            extras={"cfg_type": "cfg",
                     "use_erg_tag": False,
                     "use_erg_lyric": False,
                     "use_erg_diffusion": False},
        )
        traj = res.trajectory or []
        traj_sigmas = (res.extras or {}).get("trajectory_sigmas", [])
        traj_vs = (res.extras or {}).get("trajectory_model_outputs", [])
        cfg_active_flags = (res.extras or {}).get("trajectory_cfg_active", [])
        final_audio = res.waveform

        files: list[dict] = []
        # Save final audio
        final_path = out_dir / f"{pid}__final.wav"
        save_audio(final_path, final_audio, res.sample_rate)
        files.append({
            "sigma": None,
            "label": "final",
            "step": None,
            "cfg_active": None,
            "file": str(final_path.relative_to(Path("."))),
        })
        for s in target_sigmas:
            k = _pick(s, traj_sigmas)
            sigma_actual = float(traj_sigmas[k])
            v_eff = traj_vs[k]
            z_k = traj[k]
            z0 = z_k.to(torch.float32) - sigma_actual * v_eff.to(torch.float32)
            ahat = model.decode(z0)
            cfg_active = bool(cfg_active_flags[k])
            fname = f"{pid}__sigma{s:.2f}_step{k:02d}.wav"
            fpath = out_dir / fname
            save_audio(fpath, ahat, res.sample_rate)
            files.append({
                "sigma_target": s,
                "sigma_actual": sigma_actual,
                "step": int(k),
                "cfg_active": cfg_active,
                "cfg_branch": "CFG-mixed" if cfg_active else "cond-only",
                "file": str(fpath.relative_to(Path("."))),
            })
            print(f"    σ_tgt={s:.2f} σ_act={sigma_actual:.4f} step={k:>2} "
                  f"cfg_active={cfg_active!s:>5} → {fname}", flush=True)

        manifest["items"].append({
            "prompt_id": pid,
            "text": prompt.text,
            "lyrics": prompt.lyrics,
            "duration_target_s": prompt.duration_target,
            "structure_hint": prompt.structure_hint,
            "seed": seed,
            "sample_rate": res.sample_rate,
            "files": files,
        })

    manifest_path = out_dir / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nPacket manifest: {manifest_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
