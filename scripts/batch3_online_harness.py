#!/usr/bin/env python
"""Batch 3 — ONLINE generation harness (per-GPU worker).

Runs the 8 pre-registered arms on a slice of the 256 held_out prompts with real online
restart at the σ0.8 decision point, matched step budgets, CRN seeds, inline gate labeling +
full reward scoring, per-candidate JSONL ledger, and the frozen storage policy.

Arms (BATCH3_PRELAUNCH_PROTOCOL.md): 1 BoN-Budget | 2 random-restart (yoked to arm 4) |
3 common-score restart (abort if early-σ0.8 common < dev-Q40 1.4667; overhead ledgered) |
4 ADSR+EVPD seed-only (frozen melsumm_logit_s0.8, thr 0.728, ≤6 aborts) | 6 ADSR+EVPD +
conditioned respawn (RESPAWN_LADDER.json: restart1=new seed, restart2=L1, restart3+=L2) |
7 BoN-8 ref (240) | 8 BoN-4 anchor (120). Arm 5 (lyric-defer) = selection-only over arm-4
candidates — no extra generation; computed in analysis.

Budget: probe=12 steps, continuation=+18 (completion of probed candidate = 30 total);
non-probing completion = 30. Dual ledger: nominal steps + measured wall overhead. CRN: seed =
SEED_B3 + manifest_index*1000 + rep*100 + attempt (arm-independent → identical initial noise).

Storage policy: after each (prompt, arm, rep) unit, keep only the gate-selected wav (+ ALL wavs
for E2-subgroup prompts); delete the rest (scores/ledgers persist everything analytic).

Usage:
  CUDA_VISIBLE_DEVICES=g python scripts/batch3_online_harness.py \
      --worker-index W --num-workers N [--prompts-limit K] [--out-tag dryrun] [--reps 2]
"""
from __future__ import annotations
import argparse, dataclasses, glob, json, os, sys, time
from collections import defaultdict
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
B3 = REPO / "orbit-research/adsr_phase2_20260604/batch3"
SEED_B3 = 2026062000
SIGMA_DECIDE = 0.8
PROBE_COST, CONT_COST, FULL_COST = 12, 18, 30
MAX_ABORTS = 6
EVPD_THR_FILE = B3.parent / "batch2/evpd_sigma08_online.joblib"
ARM3_THR = 1.4667           # dev Q40 of early-0.8 common (DEV_CALIBRATIONS.json)
BUDGETS = {1: 168, 2: 168, 3: 168, 4: 168, 6: 168, 7: 240, 8: 120,
           9: 168}  # arm 9 = probe-on-evidence (Phase-2 offline winner, confirmatory run)
ARM_ORDER = [4, 6, 3, 1, 7, 8, 2]   # arm 2 last: yoked to arm 4's abort count


def mel_summary(audio_np, sr=48000):
    import librosa
    y = audio_np.mean(0) if audio_np.ndim == 2 else audio_np
    M = librosa.feature.melspectrogram(y=y.astype("float32"), sr=sr, n_mels=64, hop_length=512)
    logM = librosa.power_to_db(M + 1e-9)
    return np.concatenate([logM.mean(1), logM.std(1), logM.max(1),
                           np.percentile(logM, 25, 1), np.percentile(logM, 75, 1)])


class EarlyAbort(Exception):
    pass


class GateLabeler:
    """Exact replica of adsr_downstream._label_one's stem-energy ratio (htdemucs), on GPU."""
    def __init__(self, device="cuda"):
        import torch
        from demucs.pretrained import get_model
        self.torch = torch
        self.m = get_model("htdemucs").to(device).eval()
        self.device = device
        self.sr = int(getattr(self.m, "samplerate", 44100))

    def ratio(self, wav_t, sr):
        import torchaudio
        from demucs.apply import apply_model
        t = self.torch
        x = wav_t if wav_t.dim() == 2 else t.stack([wav_t, wav_t])
        x = x.unsqueeze(0).to(t.float32)
        if sr != self.sr:
            x = torchaudio.functional.resample(x, sr, self.sr)
        rms = float(t.sqrt((x ** 2).mean()))
        with t.no_grad():
            out = apply_model(self.m, x.to(self.device), device=self.device,
                              split=True, overlap=0.1)[0]
        idx = {s: i for i, s in enumerate(self.m.sources)}
        en = {s: float((out[idx[s]] ** 2).mean()) for s in self.m.sources}
        tot = sum(en.values()) + 1e-12
        return en["vocals"] / tot, rms < 1e-3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker-index", type=int, required=True)
    ap.add_argument("--num-workers", type=int, required=True)
    ap.add_argument("--prompts-limit", type=int, default=None)
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--out-tag", default="run")
    ap.add_argument("--only-arm", type=int, default=None,
                    help="run a single arm (e.g. 9 for the probe-on-evidence confirmatory)")
    ap.add_argument("--prompts-file", default=None,
                    help="override prompt subset (jsonl, same schema)")
    args = ap.parse_args()

    import joblib, torch
    from mprm.common.config import load_config
    from mprm.common.seeding import seed_everything
    from mprm.data.audio_io import save_audio
    from mprm.inference.ace_step import AceStepModel
    from scripts.collect_early_tweedie_validation import (_load_manifest, _load_prompt_rows,
                                                          _prompt_from_row, _score_common_metrics,
                                                          _pick_sigma_index)
    from scripts.launch_baseline import (_assert_reward_axes_match_policy, _build_reward_models,
                                         load_gate_eval_policy)
    from acestep.schedulers.scheduling_flow_match_euler_discrete import (
        FlowMatchEulerDiscreteScheduler)

    OUT = B3 / f"online_{args.out_tag}"
    (OUT / "keep").mkdir(parents=True, exist_ok=True)
    # PI decision 2026-06-10 (quota): TRANSIENT wavs go to node-local /dev/shm (tmpfs on
    # current compute nodes — zero Lustre quota); only the keep-set lands on Lustre, re-encoded as lossless
    # FLAC (~50% size). runs/** untouched.
    SCRATCH = Path(os.environ.get("BATCH3_SCRATCH", "/dev/shm/batch3_adsr")) / args.out_tag
    SCRATCH.mkdir(parents=True, exist_ok=True)
    ledger_f = OUT / f"ledger_w{args.worker_index}.jsonl"
    # resume state: prior ledger rows grouped per (prompt, arm, rep) so budget/aborts/attempt
    # are REPLAYED exactly (not just skipped) — otherwise a resumed worker would restart the
    # arm with a fresh budget and over-generate.
    prior = defaultdict(list)
    if ledger_f.exists():
        # Codex BLOCKING #5: the ledger is the single source of truth — fail CLOSED on
        # corruption. Only a truncated FINAL line (abrupt kill mid-write) is auto-repaired,
        # with an explicit side record; any other malformed row aborts the worker.
        lines = ledger_f.read_text().splitlines()
        for i, l in enumerate(lines):
            if not l.strip():
                continue
            try:
                d = json.loads(l)
            except json.JSONDecodeError:
                if i == len(lines) - 1:
                    repaired = "\n".join(lines[:i]) + ("\n" if i else "")
                    (ledger_f.parent / f"{ledger_f.name}.truncation_repair.json").write_text(
                        json.dumps({"dropped_line_index": i, "dropped_text": l[:500],
                                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))
                    ledger_f.write_text(repaired)
                    break
                raise RuntimeError(
                    f"LEDGER CORRUPTION at {ledger_f}:{i + 1} (non-final malformed row) — "
                    "fail-closed; repair manually with an explicit side record.")
            prior[(d["prompt_id"], d["arm"], d["rep"])].append(d)

    # frozen inputs
    bundle = joblib.load(EVPD_THR_FILE)
    evpd_model, evpd_scaler, evpd_thr = bundle["model"], bundle["scaler"], bundle["threshold"]
    ladder = json.loads((B3 / "RESPAWN_LADDER.json").read_text())["ladder"]
    e2_pids = {json.loads(l)["prompt_id"] for l in open(B3 / "E2_TAIL_SUBGROUP.jsonl")}
    pf = Path(args.prompts_file) if args.prompts_file else (B3 / "batch3_selected_prompts_256.jsonl")
    sel_rows = [json.loads(l) for l in open(pf)]
    sel_rows.sort(key=lambda r: r["manifest_index"])
    if args.prompts_limit:
        sel_rows = sel_rows[:args.prompts_limit]
    mine = sel_rows[args.worker_index::args.num_workers]

    # SAME scoring config as the Batch-1 collection (records must be comparable):
    # gate_v2.yaml.draft is read as the eval policy exactly as collect_early_tweedie_validation.py
    # does by default — never renamed/activated (CLAUDE.md).
    gate_policy, _ = load_gate_eval_policy(REPO / "configs/eval/gate_v2.yaml.draft")
    cfg = load_config(REPO / "configs/baselines/r2_bon.yaml")
    reward_models = _build_reward_models(cfg.reward)
    _assert_reward_axes_match_policy(reward_models, gate_policy)
    master = _load_manifest(REPO / "orbit-research/EARLY_TWEEDIE_VALIDATION_512_PROMPTS.json")
    rows_by_id = _load_prompt_rows([m for m in master
                                    if m["prompt_id"] in {r["prompt_id"] for r in mine}])
    midx_of = {m["prompt_id"]: int(m["manifest_index"]) for m in master}
    model = AceStepModel()
    gate = GateLabeler("cuda")
    orig_step = FlowMatchEulerDiscreteScheduler.step
    BASE_EXTRAS = {"cfg_type": "apg", "guidance_interval": 0.5,
                   "use_erg_tag": False, "use_erg_lyric": False, "use_erg_diffusion": False}

    def apply_intervention(prompt, direction, level):
        lv = ladder[direction][f"level{level}"]
        p = prompt; extras = {}; cfg_scale = 5.0
        if "V" in lv or direction == "vocal_miss":
            if lv in ("V1", "V3"):
                extras = {"guidance_scale_text": 5.0, "guidance_scale_lyric": 7.5}
            if lv in ("V2", "V3") and not (p.structure_hint or "").strip():
                p = dataclasses.replace(p, structure_hint="[verse]\n[chorus]\n[verse]\n[chorus]")
        else:
            if lv in ("I1", "I3"):
                p = dataclasses.replace(p, text=p.text.rstrip(". ") +
                                        ", pure instrumental, no vocals, no singing, no voice")
            if lv in ("I2", "I3"):
                cfg_scale = 7.5
        return p, extras, cfg_scale, lv

    def generate(prompt, seed, probe_mode, requested_vocal, arm_state, extras_extra=None,
                 cfg_scale=5.0):
        """probe_mode: None | 'evpd' | 'common' | 'random'. Returns dict outcome."""
        st = {"probed": False, "aborted": False, "probe_s": 0.0, "evpd_p": None,
              "early_common": None}

        def step(sched, model_output, timestep, sample, **kw):
            # NOTE: upstream calls scheduler.step with KEYWORD args (model_output=, timestep=,
            # sample=) — parameter names must match exactly (dry-run TypeError lesson).
            mo, ts = model_output, timestep
            if sched.step_index is None:
                sched._init_step_index(ts)
            si = sched.step_index
            sigma = float(sched.sigmas[si])
            if probe_mode and not st["probed"] and sigma <= SIGMA_DECIDE:
                st["probed"] = True
                t0 = time.time()
                flag = False
                if probe_mode == "random":
                    flag = arm_state["aborts"] < arm_state.get("yoke_target", 0)
                else:
                    z0 = sample.to(torch.float32) - sigma * mo.to(torch.float32)
                    early = model.decode(z0)
                    ea = early.detach().cpu()
                    if probe_mode == "evpd":
                        feat = mel_summary(ea.numpy())
                        p = float(evpd_model.predict_proba(
                            evpd_scaler.transform(feat.reshape(1, -1)))[0, 1])
                        st["evpd_p"] = p
                        flag = (int(p >= evpd_thr) != requested_vocal)
                    else:  # common
                        sc = _score_common_metrics(reward_models=reward_models, waveform=ea,
                                                   sample_rate=48000, prompt=prompt,
                                                   gate_policy=gate_policy)
                        st["early_common"] = sc.get("common_robust_lcb")
                        flag = (st["early_common"] is None or st["early_common"] < ARM3_THR)
                st["probe_s"] = time.time() - t0
                if flag and arm_state["aborts"] < MAX_ABORTS and \
                        arm_state["budget"] >= PROBE_COST:
                    st["aborted"] = True
                    raise EarlyAbort()
            return orig_step(sched, mo, ts, sample, **kw)

        FlowMatchEulerDiscreteScheduler.step = step
        seed_everything(seed)
        t0 = time.time()
        try:
            res = model.sample(prompt, seed=seed, cfg_scale=cfg_scale, steps=30,
                               return_trajectory=False,
                               extras={**BASE_EXTRAS, **(extras_extra or {})})
        except EarlyAbort:
            res = None
        finally:
            FlowMatchEulerDiscreteScheduler.step = orig_step
        st["wall_s"] = time.time() - t0
        st["res"] = res
        return st

    ledger = ledger_f.open("a")
    for row in mine:
        pid = row["prompt_id"]; midx = midx_of[pid]
        prow = rows_by_id[(str(row["prompt_source"]), pid)]
        base_prompt = _prompt_from_row(prow)
        requested_vocal = int(row["vocal_stratum"] == "vocal")
        direction = "vocal_miss" if requested_vocal else "instr_leak"
        # PROTOCOL: R=2 everywhere; R=3 on the E2 tail subgroup for arms 4 and 6 (primary power)
        max_reps = 3 if pid in e2_pids else args.reps
        for rep in range(max_reps):
            arm4_aborts = 0
            arm_list = [args.only_arm] if args.only_arm else ARM_ORDER
            for arm in arm_list:
                if args.only_arm:
                    if rep >= args.reps:
                        continue
                elif rep >= (3 if (pid in e2_pids and arm in (4, 6)) else args.reps):
                    continue
                budget = BUDGETS[arm]
                arm_state = {"budget": budget, "aborts": 0,
                             "yoke_target": arm4_aborts if arm == 2 else 0}
                attempt = 0
                kept_wavs = []
                # ---- resume replay: restore budget/aborts/attempt + selection bookkeeping ----
                unit_prior = prior.get((pid, arm, rep), [])
                if any(d.get("type") == "unit_selection" for d in unit_prior):
                    if arm == 4:   # arm-2 yoking needs arm-4's abort count even when skipping
                        arm4_aborts = sum(1 for d in unit_prior if d.get("aborted"))
                    continue       # unit fully finalized in a previous session
                for d in sorted([d for d in unit_prior if "attempt" in d],
                                key=lambda x: x["attempt"]):
                    arm_state["budget"] -= d["cost"]
                    if d.get("aborted"):
                        arm_state["aborts"] += 1
                    if d.get("completed"):
                        w = Path(d["wav"])
                        kept_wavs.append((w, d.get("gate_pass", 0),
                                          d.get("final_common_robust_lcb"),
                                          d.get("final_lyric_intelligibility")))
                    attempt = max(attempt, d["attempt"] + 1)
                viol_seen = any(d.get("completed") and not d.get("gate_pass", 1)
                                for d in unit_prior)
                while True:
                    # arm 9 (probe-on-evidence): probe ONLY once a gated violation was observed
                    probing = arm in (2, 3, 4, 6) or (arm == 9 and viol_seen)
                    # Codex BLOCKING #1: every attempt must be able to afford a FULL completion
                    # (probe-only entries either waste 12 steps on a non-abort or overspend) —
                    # mirrors arm 1's "full completions until <30 remain".
                    if arm_state["budget"] < FULL_COST:
                        break
                    seed = SEED_B3 + midx * 1000 + rep * 100 + attempt
                    prompt, extras_x, cfgs, interv = base_prompt, {}, 5.0, None
                    # Codex BLOCKING #2 (protocol): restart1 = seed only; restart2 = level-1;
                    # restart3+ = level-2  ⇒ interventions begin at the SECOND restart.
                    if arm == 6 and arm_state["aborts"] >= 2:
                        prompt, extras_x, cfgs, interv = apply_intervention(
                            base_prompt, direction, 1 if arm_state["aborts"] == 2 else 2)
                    mode = {2: "random", 3: "common", 4: "evpd", 6: "evpd"}.get(arm)
                    if arm == 9:
                        mode = "evpd" if viol_seen else None
                    st = generate(prompt, seed, mode, requested_vocal, arm_state,
                                  extras_x, cfgs)
                    rec = {"prompt_id": pid, "stratum": row["stratum"], "arm": arm, "rep": rep,
                           "attempt": attempt, "seed": seed, "intervention": interv,
                           "probed": st["probed"], "aborted": st["aborted"],
                           "evpd_p": st["evpd_p"], "early_common": st["early_common"],
                           "probe_overhead_s": round(st["probe_s"], 3),
                           "wall_s": round(st["wall_s"], 2),
                           "budget_before": arm_state["budget"]}
                    if st["aborted"]:
                        arm_state["budget"] -= PROBE_COST
                        arm_state["aborts"] += 1
                        rec.update({"cost": PROBE_COST, "completed": False})
                    else:
                        arm_state["budget"] -= (PROBE_COST + CONT_COST) if st["probed"] \
                            else FULL_COST
                        res = st["res"]
                        wav_dir = SCRATCH / pid
                        wav_dir.mkdir(parents=True, exist_ok=True)
                        wav = wav_dir / f"a{arm}_r{rep}_t{attempt:02d}_seed{seed}.wav"
                        save_audio(wav, res.waveform, res.sample_rate)
                        t0 = time.time()
                        ratio, near_sil = gate.ratio(res.waveform, res.sample_rate)
                        present = int((ratio >= 0.1791) and not near_sil)
                        scores = _score_common_metrics(reward_models=reward_models,
                                                       waveform=res.waveform,
                                                       sample_rate=res.sample_rate,
                                                       prompt=base_prompt,
                                                       gate_policy=gate_policy)
                        rec.update({"cost": (PROBE_COST + CONT_COST) if st["probed"]
                                    else FULL_COST, "completed": True,
                                    "wav": str(wav),
                                    "gate_ratio": round(ratio, 5), "near_silent": near_sil,
                                    "present": present, "requested_vocal": requested_vocal,
                                    "gate_pass": int(present == requested_vocal),
                                    "score_s": round(time.time() - t0, 1),
                                    **{f"final_{k}": v for k, v in scores.items()}})
                        kept_wavs.append((wav, rec["gate_pass"],
                                          scores.get("common_robust_lcb"),
                                          scores.get("lyric_intelligibility")))
                        if not rec["gate_pass"]:
                            viol_seen = True
                    ledger.write(json.dumps(rec) + "\n"); ledger.flush()
                    attempt += 1
                if arm == 4:
                    arm4_aborts = arm_state["aborts"]
                # storage policy: keep gated-selected wav (+ all wavs for E2 prompts).
                # Codex BLOCKING #4: for arm-4 units on EN-vocal prompts ALSO keep arm 5's
                # lyric-defer selection (argmax common + 0.25*lyric over gate-passers), which can
                # differ from the best-common keep and is needed for human A/B pairs.
                # ---- storage finalize: choose keeps -> transcode to FLAC on Lustre; wipe scratch
                if kept_wavs:
                    keeps = set()
                    passers = [w for w in kept_wavs if w[1]]
                    pool = passers if passers else kept_wavs
                    selected = max(pool, key=lambda w: (w[2] if w[2] is not None else -1e9))[0]
                    keeps.add(selected)
                    if arm == 4 and requested_vocal and row.get("language") == "en":
                        keeps.add(max(pool, key=lambda w: ((w[2] if w[2] is not None else -1e9)
                                                           + 0.25 * (w[3] or 0.0)))[0])
                    if pid in e2_pids:          # E2 prompts: keep every gate-passer too
                        keeps.update(w[0] for w in passers)
                    flacs = {}
                    for w in kept_wavs:
                        persisted = w[0] not in keeps   # non-keeps need no persistence
                        if w[0] in keeps:
                            fdir = OUT / "keep" / pid
                            fdir.mkdir(parents=True, exist_ok=True)
                            try:
                                import soundfile as sf
                                data, sr_ = sf.read(str(w[0]))
                                fp = fdir / (w[0].stem + ".flac")
                                sf.write(str(fp), data, sr_, format="FLAC", subtype="PCM_24")
                                flacs[w[0].name] = str(fp.relative_to(REPO))
                                persisted = True
                            except Exception as e:
                                # Gate-A BLOCKING fix: NEVER delete a keep that failed transcode —
                                # fall back to copying the raw wav into the keep dir.
                                try:
                                    import shutil
                                    fp = fdir / w[0].name
                                    shutil.copy2(str(w[0]), str(fp))
                                    flacs[w[0].name] = str(fp.relative_to(REPO)) + " (wav fallback)"
                                    persisted = True
                                except Exception as e2:
                                    flacs[w[0].name] = (f"KEEP_RETAINED_ON_SCRATCH: "
                                                        f"{type(e).__name__}/{type(e2).__name__}")
                        if persisted:
                            try:
                                w[0].unlink()
                            except OSError:
                                pass
                    ledger.write(json.dumps({"type": "unit_selection", "prompt_id": pid,
                                             "arm": arm, "rep": rep,
                                             "selected": selected.name, "keeps": flacs}) + "\n")
                    ledger.flush()
        print(f"PROMPT_DONE {pid}", flush=True)
    ledger.close()
    print("WORKER_DONE", flush=True)


if __name__ == "__main__":
    main()
