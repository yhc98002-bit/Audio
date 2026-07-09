#!/usr/bin/env python
"""Large-N BoN / condition worker (v3.2 spine). DETACHED non-LLM worker.

Per prompt × N seeds: plain ACE-Step generation (or a condition intervention) → label EVERY draw
with Demucs ratio + PANNs (continuous + binary type label) → ledger. Full reward-score + keep
audio (FLAC) only on a SAMPLE (storage discipline §2): seed_idx < KEEP_PER_PROMPT, OR
Demucs↔PANNs detector-disagreement. Transient WAV in /dev/shm, deleted after labeling.

Reuses the exact Batch-3 gen+label+score stack (sanity-gate-passed). Sharded, resumable.
seed = NEW_SEED_BASE + prompt_index*100000 + condition_index*1000 + seed_idx  (BoN: condition 0).

Usage: CUDA_VISIBLE_DEVICES=g python core_largeN_worker.py --prompts P.jsonl --n-seeds 256 \
         --condition none --out <dir> --tag bon256 --worker-index W --num-workers N
"""
from __future__ import annotations
import argparse, dataclasses, glob, json, sys, time
from pathlib import Path

REPO = Path("/HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion")
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts"))
NEW_SEED_BASE = 2026200000
THR, PANNS_THR = 0.1791, 0.0654
KEEP_PER_PROMPT = 4
BASE_EXTRAS = {"cfg_type": "apg", "guidance_interval": 0.5,
               "use_erg_tag": False, "use_erg_lyric": False, "use_erg_diffusion": False}
# condition interventions (frozen RESPAWN_LADDER families + anti-vocal ladder)
COND_IDX = {"none": 0, "V1": 1, "V3": 2, "I1": 3, "I3": 4, "I_strong": 5}


def apply_condition(prompt, cond):
    extras, cfg = {}, 5.0
    if cond in ("V1", "V3"):
        extras = {"guidance_scale_text": 5.0, "guidance_scale_lyric": 7.5}
        if cond == "V3" and not (prompt.structure_hint or "").strip():
            prompt = dataclasses.replace(prompt, structure_hint="[verse]\n[chorus]\n[verse]\n[chorus]")
    elif cond in ("I1", "I3", "I_strong"):
        anti = ", pure instrumental, no vocals, no singing, no voice"
        if cond == "I_strong":
            anti = (", pure instrumental backing track, absolutely no vocals, no singing, no voice, "
                    "no choir, no rap, no spoken word, no humming, no vocal chops")
        prompt = dataclasses.replace(prompt, text=prompt.text.rstrip(". ") + anti, lyrics=None)
        if cond in ("I3", "I_strong"):
            cfg = 7.5
    return prompt, extras, cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", required=True)
    ap.add_argument("--n-seeds", type=int, default=256)
    ap.add_argument("--condition", default="none")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="bon256")
    ap.add_argument("--worker-index", type=int, default=0)
    ap.add_argument("--num-workers", type=int, default=1)
    args = ap.parse_args()
    cond_i = COND_IDX[args.condition]
    OUT = Path(args.out); (OUT / "ledgers").mkdir(parents=True, exist_ok=True)
    keepd = OUT / "keep" / args.tag; keepd.mkdir(parents=True, exist_ok=True)

    import soundfile as sf, librosa, numpy as np
    from mprm.common.config import load_config
    from mprm.common.seeding import seed_everything
    from mprm.data.audio_io import save_audio
    from mprm.inference.ace_step import AceStepModel
    from collect_early_tweedie_validation import _prompt_from_row, _score_common_metrics
    from launch_baseline import _build_reward_models, load_gate_eval_policy
    from batch3_online_harness import GateLabeler
    gate_policy, _ = load_gate_eval_policy(REPO / "configs/eval/gate_v2.yaml.draft")
    rcfg = load_config(REPO / "configs/baselines/r2_bon.yaml")
    reward_models = _build_reward_models(rcfg.reward)
    model = AceStepModel(); gate = GateLabeler("cuda")
    try:
        from panns_inference import AudioTagging
        from panns_inference.config import labels as plabels
        VC = {"Singing", "Speech", "Male singing", "Female singing", "Child singing", "Choir",
              "Rapping", "Human voice", "Vocal music", "A capella"}
        pidx = [i for i, l in enumerate(plabels) if l in VC]
        at = AudioTagging(checkpoint_path=None, device="cuda")
    except Exception as e:
        at = None; print(f"PANNs unavailable: {e}", flush=True)

    rows = [json.loads(l) for l in open(args.prompts)]
    tasks = [(r, s) for r in rows for s in range(args.n_seeds)]
    mine = tasks[args.worker_index::args.num_workers]
    led_f = OUT / "ledgers" / f"{args.tag}_w{args.worker_index}.jsonl"
    # Codex D-review fix: resume must scan ALL {tag}_w*.jsonl shards, not just this worker's —
    # otherwise a different --num-workers on resume regenerates rows another shard already did,
    # creating duplicate (prompt_id, seed_idx). Also: extension jobs MUST use the canonical prompt
    # list (stable prompt_index) so seeds are consistent across runs.
    done = set()
    for f in glob.glob(str(OUT / "ledgers" / f"{args.tag}_w*.jsonl")):
        for l in open(f):
            try:
                d = json.loads(l); done.add((d["prompt_id"], d.get("seed_idx")))
            except Exception:
                pass
    shm = Path(f"/dev/shm/largeN_{args.tag}_{args.worker_index}"); shm.mkdir(parents=True, exist_ok=True)
    led = led_f.open("a"); n = 0; t0 = time.time()
    for r, si in mine:
        if (r["prompt_id"], si) in done:
            continue
        seed = NEW_SEED_BASE + r["prompt_index"] * 100000 + cond_i * 1000 + si
        prompt = _prompt_from_row(r)
        prompt, ex, cfg = apply_condition(prompt, args.condition)
        req_vocal = int(r["vocal_stratum"] == "vocal")
        seed_everything(seed)
        try:
            res = model.sample(prompt, seed=seed, cfg_scale=cfg, steps=30,
                               return_trajectory=False, extras={**BASE_EXTRAS, **ex})
        except Exception as e:
            led.write(json.dumps({"prompt_id": r["prompt_id"], "seed_idx": si,
                                  "error": f"{type(e).__name__}:{e}"}) + "\n"); led.flush(); continue
        ratio, near_sil = gate.ratio(res.waveform, res.sample_rate)
        present = int((ratio >= THR) and not near_sil)
        pv = None
        if at is not None:
            try:
                wav = res.waveform.mean(0) if res.waveform.dim() == 2 else res.waveform
                y = librosa.resample(wav.cpu().numpy().astype("float32"), orig_sr=res.sample_rate, target_sr=32000)
                clip, _ = at.inference(y[None, :]); pv = float(np.max(clip[0][pidx]))
            except Exception:
                pv = None
        disagree = (pv is not None) and (int(pv >= PANNS_THR) != present)
        keep = (si < KEEP_PER_PROMPT) or disagree
        rec = {"prompt_id": r["prompt_id"], "source": r.get("source"), "condition": args.condition,
               "requested_vocal": req_vocal, "seed_idx": si, "seed": seed,
               "vocal_energy_ratio": round(ratio, 5), "near_silent": near_sil, "present": present,
               "type_correct": int(present == req_vocal),
               "panns_vocal": (round(pv, 5) if pv is not None else None),
               "detector_disagree": int(disagree), "kept": int(keep)}
        if keep:
            sc = _score_common_metrics(reward_models=reward_models, waveform=res.waveform,
                                       sample_rate=res.sample_rate, prompt=prompt, gate_policy=gate_policy)
            for k in ("common_robust_lcb", "semantic_fit", "aesthetic_pq", "lyric_intelligibility"):
                rec[f"score_{k}"] = sc.get(k)
            kd = keepd / r["prompt_id"]; kd.mkdir(exist_ok=True)
            tmp = shm / f"{r['prompt_id']}_{si}.wav"; fp = kd / f"{args.condition}_s{si}_{seed}.flac"
            save_audio(tmp, res.waveform, res.sample_rate)
            data, sr = sf.read(str(tmp)); sf.write(str(fp), data, sr, format="FLAC")
            try:
                tmp.unlink()
            except OSError:
                pass
            rec["flac"] = str(fp.relative_to(OUT))
        led.write(json.dumps(rec) + "\n"); led.flush(); n += 1
        if n % 50 == 0:
            print(f"w{args.worker_index} {args.tag}: {n} ({(time.time()-t0)/60:.1f}min)", flush=True)
    led.close()
    print(f"LARGEN_DONE w{args.worker_index} tag={args.tag} n={n}", flush=True)


if __name__ == "__main__":
    main()
