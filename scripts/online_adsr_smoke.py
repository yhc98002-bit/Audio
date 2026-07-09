#!/usr/bin/env python
"""Batch 3 feasibility smoke: validate the hook-abort ONLINE-restart primitive on ONE prompt.

Confirms (riskiest mechanisms) that we can, INSIDE the diffusion loop at σ0.8:
  (1) compute the Tweedie z0 = x_σ − σ·v, decode to early audio, mel-summary, run the FIXED EVPD;
  (2) RAISE to abort the pipeline early → real compute savings (step count < full).
Also times a full run for the compute-savings ratio. No restart loop yet — just the primitive.
"""
from __future__ import annotations
import sys, time, json
from pathlib import Path
import numpy as np
import torch, joblib, librosa

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
EVPD = REPO / "orbit-research/adsr_phase2_20260604/batch2/evpd_sigma08_online.joblib"
MANIFEST = REPO / "orbit-research/EARLY_TWEEDIE_VALIDATION_512_PROMPTS.json"
SIGMA_TARGET = 0.8


def mel_summary(audio_np, sr):
    y = audio_np.mean(0) if audio_np.ndim == 2 else audio_np
    M = librosa.feature.melspectrogram(y=y.astype("float32"), sr=sr, n_mels=64, hop_length=512)
    logM = librosa.power_to_db(M + 1e-9)
    return np.concatenate([logM.mean(1), logM.std(1), logM.max(1),
                           np.percentile(logM, 25, 1), np.percentile(logM, 75, 1)])


class EarlyStop(Exception):
    def __init__(self, nsteps):
        self.nsteps = nsteps


def main():
    from mprm.common.seeding import seed_everything
    from mprm.inference.ace_step import AceStepModel
    from scripts.collect_early_tweedie_validation import _load_manifest, _load_prompt_rows, _prompt_from_row
    from acestep.schedulers.scheduling_flow_match_euler_discrete import FlowMatchEulerDiscreteScheduler

    print("loading model...", flush=True); t = time.time()
    model = AceStepModel()
    bundle = joblib.load(EVPD)
    print(f"model+evpd loaded in {time.time()-t:.1f}s; evpd thr={bundle['threshold']:.3f}", flush=True)

    rows = _load_manifest(MANIFEST)[:1]
    prow = _load_prompt_rows(rows)[(str(rows[0]["prompt_source"]), str(rows[0]["prompt_id"]))]
    prompt = _prompt_from_row(prow)
    print(f"prompt {rows[0]['prompt_id']} loaded", flush=True)
    orig_step = FlowMatchEulerDiscreteScheduler.step
    SAMPLE_KW = dict(cfg_scale=5.0, steps=30,
                     extras={"cfg_type": "apg", "guidance_interval": 0.5,
                             "use_erg_tag": False, "use_erg_lyric": False, "use_erg_diffusion": False})

    def run(mode):
        """mode: 'full' | 'decide' (decode+EVPD at σ0.8, continue) | 'abort' (decode+EVPD then raise)."""
        st = {"decided": False, "nsteps": 0, "evpd_p": None, "pred_present": None, "decode_s": 0.0}

        def step(sched_self, model_output, timestep, sample, **kw):
            if sched_self.step_index is None:
                sched_self._init_step_index(timestep)
            si = sched_self.step_index; sigma = float(sched_self.sigmas[si]); st["nsteps"] = si + 1
            if mode != "full" and not st["decided"] and sigma <= SIGMA_TARGET:
                st["decided"] = True
                d0 = time.time()
                z0 = sample.to(torch.float32) - sigma * model_output.to(torch.float32)
                early = model.decode(z0)
                ea = early.detach().cpu().numpy() if hasattr(early, "detach") else np.asarray(early)
                feat = mel_summary(ea, 48000)
                p = float(bundle["model"].predict_proba(bundle["scaler"].transform(feat.reshape(1, -1)))[0, 1])
                st["evpd_p"] = p; st["pred_present"] = int(p >= bundle["threshold"])
                st["decision_sigma"] = sigma; st["decode_s"] = time.time() - d0
                if mode == "abort":
                    raise EarlyStop(si + 1)
            return orig_step(sched_self, model_output, timestep, sample, **kw)

        FlowMatchEulerDiscreteScheduler.step = step
        seed_everything(12345)
        t0 = time.time(); aborted = False
        try:
            res = model.sample(prompt, seed=12345, return_trajectory=False, **SAMPLE_KW)
        except EarlyStop:
            aborted = True; res = None
        finally:
            FlowMatchEulerDiscreteScheduler.step = orig_step
        st["wall_s"] = round(time.time() - t0, 2); st["aborted"] = aborted
        return st

    print("=== RUN full ==="); full = run("full"); print(json.dumps(full, default=str))
    print("=== RUN decide (decode+EVPD at σ0.8, continue) ==="); dec = run("decide"); print(json.dumps(dec, default=str))
    print("=== RUN abort (raise at σ0.8) ==="); ab = run("abort"); print(json.dumps(ab, default=str))
    print(json.dumps({
        "FEASIBILITY": {
            "decode_evpd_in_hook_ok": dec["evpd_p"] is not None,
            "abort_stops_early": ab["nsteps"] < full["nsteps"],
            "full_steps": full["nsteps"], "abort_steps": ab["nsteps"],
            "step_savings_frac": round(1 - ab["nsteps"] / full["nsteps"], 3) if full["nsteps"] else None,
            "decision_sigma": dec.get("decision_sigma"), "decode_overhead_s": dec.get("decode_s"),
            "full_wall_s": full["wall_s"], "abort_wall_s": ab["wall_s"],
            "wall_savings_frac": round(1 - ab["wall_s"] / full["wall_s"], 3) if full["wall_s"] else None,
            "evpd_p": dec["evpd_p"], "pred_present": dec["pred_present"],
        }}, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
