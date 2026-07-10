#!/usr/bin/env python
"""P0.8 — Respawn knob screen on DEV tail prompts (held_out untouched).

Picks ~10 vocal-miss + ~10 instrumental-leak dev tail prompts (highest Batch-1 violation counts),
generates 4 conditions x 4 fresh seeds each (CRN: same seeds across conditions), Demucs-gates all
outputs, and freezes the 2-level escalation ladder per error direction for the Batch-3 conditioned-
respawn arm (arm 6).

Conditions (per direction):
  vocal-miss   : B=reseed | V1=lyric-boost (guidance_scale_text=5.0, guidance_scale_lyric=7.5)
                 | V2=structure-hint inject | V3=V1+V2
  instr-leak   : B=reseed | I1=anti-vocal tag append | I2=cfg_scale 7.5 | I3=I1+I2

All knobs are adapter-passthrough today (UPSTREAM_PASSTHROUGH_KEYS) — no code changes.
Outputs: orbit-research/adsr_phase2_20260604/phase0/respawn_screen/{wavs,labels.jsonl}
         + PHASE0_RESPAWN_LADDER.{json,md}
"""
from __future__ import annotations
import dataclasses, glob, json, os, sys, time
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from mprm.common.thresholds import VOCAL_PRESENCE_THRESHOLD
P0 = REPO / "orbit-research/adsr_phase2_20260604/phase0/respawn_screen"
MERGED = REPO / "runs/adsr_recollect_20260604_full01_merged"
RAW = REPO / "orbit-research/adsr_phase2_20260604/vocal_presence_raw.jsonl"
THR = VOCAL_PRESENCE_THRESHOLD
SEED_BASE = 2026061000   # fresh base — deliberately disjoint from canonical 2026052700
N_PER_DIR = 10
SEEDS_PER_COND = 4
SAMPLE_KW = dict(cfg_scale=5.0, steps=30)
BASE_EXTRAS = {"cfg_type": "apg", "guidance_interval": 0.5,
               "use_erg_tag": False, "use_erg_lyric": False, "use_erg_diffusion": False}


def pick_tail_prompts():
    recs = {}
    for f in sorted(glob.glob(str(MERGED / "shard0*" / "candidate_records.jsonl"))):
        for l in open(f):
            r = json.loads(l); recs[(r["prompt_id"], r["candidate_index"])] = r
    lab = {}
    for l in open(RAW):
        r = json.loads(l)
        if r.get("ok"):
            lab[(r["prompt_id"], r["candidate_index"])] = r
    viol = defaultdict(int); meta = {}
    for k, r in recs.items():
        if r.get("split") != "dev":
            continue
        L = lab[k]
        present = (L["vocal_energy_ratio"] >= THR) and not L.get("near_silent")
        req = r.get("vocal_stratum") == "vocal"
        if present != req:
            viol[k[0]] += 1
        meta[k[0]] = r
    vocal_tail = sorted([p for p in viol if meta[p]["vocal_stratum"] == "vocal"],
                        key=lambda p: -viol[p])[:N_PER_DIR]
    instr_tail = sorted([p for p in viol if meta[p]["vocal_stratum"] == "instrumental"],
                        key=lambda p: -viol[p])[:N_PER_DIR]
    return vocal_tail, instr_tail, meta, viol


def conditions_for(direction):
    if direction == "vocal_miss":
        return [("B", {}, {}), ("V1", {}, {"guidance_scale_text": 5.0, "guidance_scale_lyric": 7.5}),
                ("V2", {"structure": True}, {}),
                ("V3", {"structure": True}, {"guidance_scale_text": 5.0, "guidance_scale_lyric": 7.5})]
    return [("B", {}, {}), ("I1", {"anti_vocal": True}, {}),
            ("I2", {}, {"_cfg_scale": 7.5}),
            ("I3", {"anti_vocal": True}, {"_cfg_scale": 7.5})]


def apply_prompt_mod(prompt, mod):
    if mod.get("structure") and not (prompt.structure_hint or "").strip():
        prompt = dataclasses.replace(prompt, structure_hint="[verse]\n[chorus]\n[verse]\n[chorus]")
    if mod.get("anti_vocal"):
        prompt = dataclasses.replace(
            prompt, text=(prompt.text.rstrip(". ") +
                          ", pure instrumental, no vocals, no singing, no voice"))
    return prompt


def main():
    from mprm.common.seeding import seed_everything
    from mprm.data.audio_io import save_audio
    from mprm.inference.ace_step import AceStepModel
    from scripts.collect_early_tweedie_validation import (_load_manifest, _load_prompt_rows,
                                                          _prompt_from_row)
    vocal_tail, instr_tail, meta, viol = pick_tail_prompts()
    print(json.dumps({"vocal_miss_tail": [(p, viol[p]) for p in vocal_tail],
                      "instr_leak_tail": [(p, viol[p]) for p in instr_tail]}), flush=True)
    # full prompt rows via the canonical master manifest
    master = _load_manifest(REPO / "orbit-research/EARLY_TWEEDIE_VALIDATION_512_PROMPTS.json")
    rows_by_id = _load_prompt_rows([r for r in master
                                    if r["prompt_id"] in set(vocal_tail + instr_tail)])
    (P0 / "wavs").mkdir(parents=True, exist_ok=True)
    model = AceStepModel()
    manifest_idx = {r["prompt_id"]: int(r["manifest_index"]) for r in master}
    plan = [("vocal_miss", p) for p in vocal_tail] + [("instr_leak", p) for p in instr_tail]
    ledger = (P0 / "gen_ledger.jsonl").open("a")
    done = set()
    if (P0 / "gen_ledger.jsonl").exists():
        for l in open(P0 / "gen_ledger.jsonl"):
            try:
                d = json.loads(l); done.add((d["prompt_id"], d["cond"], d["seed"]))
            except Exception:
                pass
    n = 0
    for direction, pid in plan:
        src = str(meta[pid]["prompt_source"])
        prow = rows_by_id[(src, pid)]
        base_prompt = _prompt_from_row(prow)
        for cond, pmod, xmod in conditions_for(direction):
            prompt = apply_prompt_mod(base_prompt, pmod)
            extras = {**BASE_EXTRAS, **{k: v for k, v in xmod.items() if not k.startswith("_")}}
            cfg = xmod.get("_cfg_scale", SAMPLE_KW["cfg_scale"])
            for si in range(SEEDS_PER_COND):
                seed = SEED_BASE + manifest_idx[pid] * 1000 + si
                if (pid, cond, seed) in done:
                    continue
                seed_everything(seed)
                t0 = time.time()
                res = model.sample(prompt, seed=seed, cfg_scale=cfg,
                                   steps=SAMPLE_KW["steps"], return_trajectory=False,
                                   extras=extras)
                d = P0 / "wavs" / f"{pid}__{cond}"
                d.mkdir(parents=True, exist_ok=True)
                wav = d / f"candidate_{si:02d}_seed{seed}.wav"
                save_audio(wav, res.waveform, res.sample_rate)
                ledger.write(json.dumps({"prompt_id": pid, "direction": direction, "cond": cond,
                                         "seed": seed, "wav": str(wav.relative_to(REPO)),
                                         "elapsed_s": round(time.time() - t0, 2)}) + "\n")
                ledger.flush(); n += 1
                if n % 20 == 0:
                    print(f"gen {n} done", flush=True)
    ledger.close()
    print(f"GENERATION_COMPLETE n={n} (+{len(done)} pre-existing)", flush=True)


if __name__ == "__main__":
    main()
