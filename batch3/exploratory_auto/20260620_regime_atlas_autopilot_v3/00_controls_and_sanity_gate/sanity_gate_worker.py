#!/usr/bin/env python
"""Mandatory ACE-Step sanity gate worker (Section 13/26). NON-LLM detached batch worker.

~20 control prompts × 8 seeds. Reuses the EXACT Batch-3 generation+label+score stack so the
smoke is comparable to the frozen evidence:
  - generation: AceStepModel.sample (cfg 5.0, 30 steps, apg/guidance_interval 0.5)
  - type label: GateLabeler (htdemucs vocal-energy ratio, thr 0.1791) from batch3_online_harness
  - scoring:    _score_common_metrics with gate_v2.yaml.draft + r2_bon.yaml (Batch-3 config)
  - PANNs vocal score (best-effort second detector)
Keeps ALL smoke audio as FLAC (protocol). Transient WAV in /dev/shm. Resumable. Sharded.

Usage: CUDA_VISIBLE_DEVICES=g python sanity_gate_worker.py --worker-index W --num-workers N
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

REPO = Path("/HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
NEW_SEED_BASE = 2026200000          # new namespace, disjoint from Batch-3 (2026062000)
THR = 0.1791
SAMPLE_KW = dict(cfg_scale=5.0, steps=30)
BASE_EXTRAS = {"cfg_type": "apg", "guidance_interval": 0.5,
               "use_erg_tag": False, "use_erg_lyric": False, "use_erg_diffusion": False}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker-index", type=int, default=0)
    ap.add_argument("--num-workers", type=int, default=1)
    ap.add_argument("--seeds", type=int, default=8)
    args = ap.parse_args()

    import soundfile as sf
    from mprm.common.config import load_config
    from mprm.common.seeding import seed_everything
    from mprm.data.audio_io import save_audio
    from mprm.inference.ace_step import AceStepModel
    from collect_early_tweedie_validation import _prompt_from_row, _score_common_metrics
    from launch_baseline import _build_reward_models, load_gate_eval_policy
    from batch3_online_harness import GateLabeler

    gate_policy, _ = load_gate_eval_policy(REPO / "configs/eval/gate_v2.yaml.draft")
    cfg = load_config(REPO / "configs/baselines/r2_bon.yaml")
    reward_models = _build_reward_models(cfg.reward)
    model = AceStepModel()
    gate = GateLabeler("cuda")
    # PANNs (best-effort 2nd detector)
    panns = None
    try:
        from panns_inference import AudioTagging
        from panns_inference.config import labels as plabels
        VC = ["Singing", "Speech", "Male singing", "Female singing", "Child singing",
              "Choir", "Rapping", "Human voice", "Vocal music", "A capella"]
        pidx = [i for i, l in enumerate(plabels) if l in VC]
        panns = (AudioTagging(checkpoint_path=None, device="cuda"), pidx)
    except Exception as e:
        print(f"PANNs unavailable: {e}", flush=True)

    rows = [json.loads(l) for l in open(HERE / "CONTROL_PROMPTS.jsonl")]
    tasks = [(r, s) for r in rows for s in range(args.seeds)]
    mine = tasks[args.worker_index::args.num_workers]
    keep = HERE / "keep"; keep.mkdir(exist_ok=True)
    led_f = HERE / f"ledger_w{args.worker_index}.jsonl"
    done = set()
    if led_f.exists():
        for l in open(led_f):
            try:
                d = json.loads(l); done.add((d["prompt_id"], d["seed_index"]))
            except Exception:
                pass
    shm = Path("/dev/shm/sanity_gate"); shm.mkdir(exist_ok=True)
    led = led_f.open("a")
    n = 0; t0 = time.time()
    import librosa, numpy as np
    for r, si in mine:
        if (r["prompt_id"], si) in done:
            continue
        seed = NEW_SEED_BASE + r["prompt_index"] * 100000 + 0 * 1000 + si
        prompt = _prompt_from_row(r)
        req_vocal = int(r["vocal_stratum"] == "vocal")
        seed_everything(seed)
        t1 = time.time()
        try:
            res = model.sample(prompt, seed=seed, cfg_scale=SAMPLE_KW["cfg_scale"],
                               steps=SAMPLE_KW["steps"], return_trajectory=False, extras=BASE_EXTRAS)
        except Exception as e:
            led.write(json.dumps({"prompt_id": r["prompt_id"], "seed_index": si, "seed": seed,
                                  "error": f"gen:{type(e).__name__}:{e}"}) + "\n"); led.flush()
            continue
        ratio, near_sil = gate.ratio(res.waveform, res.sample_rate)
        present = int((ratio >= THR) and not near_sil)
        # PANNs
        pv = None
        if panns is not None:
            try:
                at, pidx = panns
                wav = res.waveform.mean(0) if res.waveform.dim() == 2 else res.waveform
                y = librosa.resample(wav.cpu().numpy().astype("float32"),
                                     orig_sr=res.sample_rate, target_sr=32000)
                clip, _ = at.inference(y[None, :]); pv = float(np.max(clip[0][pidx]))
            except Exception:
                pv = None
        scores = _score_common_metrics(reward_models=reward_models, waveform=res.waveform,
                                       sample_rate=res.sample_rate, prompt=prompt,
                                       gate_policy=gate_policy)
        # keep ALL smoke audio as FLAC
        kd = keep / r["prompt_id"]; kd.mkdir(exist_ok=True)
        fp = kd / f"seed{si}_{seed}.flac"
        tmp = shm / f"{r['prompt_id']}_{si}.wav"
        save_audio(tmp, res.waveform, res.sample_rate)
        data, sr = sf.read(str(tmp)); sf.write(str(fp), data, sr, format="FLAC")
        try:
            tmp.unlink()
        except OSError:
            pass
        rec = {"prompt_id": r["prompt_id"], "control_category": r["control_category"],
               "requested_vocal": req_vocal, "seed_index": si, "seed": seed,
               "vocal_energy_ratio": round(ratio, 5), "near_silent": near_sil,
               "present": present, "type_correct": int(present == req_vocal),
               "panns_vocal": (round(pv, 5) if pv is not None else None),
               "flac": str(fp.relative_to(HERE)), "wall_s": round(time.time() - t1, 1),
               **{f"score_{k}": v for k, v in scores.items()
                  if k in ("common_robust_lcb", "semantic_fit", "aesthetic_pq", "lyric_intelligibility")}}
        led.write(json.dumps(rec) + "\n"); led.flush(); n += 1
        if n % 10 == 0:
            print(f"w{args.worker_index}: {n} done ({(time.time()-t0)/60:.1f}min)", flush=True)
    led.close()
    print(f"SANITY_WORKER_DONE w{args.worker_index} n={n}", flush=True)


if __name__ == "__main__":
    main()
