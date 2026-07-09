#!/usr/bin/env python
"""ADSR downstream pipeline (CPU-only; never touches the Track-B GPUs).

Pipelines, per shard/prompt as the re-collection produces audio:
  - vocal-presence labeling  (Demucs htdemucs CPU -> vocal-energy ratio -> presence)
  - early Tweedie-clean mel extraction (EVPD inputs; sigma 0.9/0.8/0.7)
  - label QA
  - partial decision snapshots at 25/50/70% prompt coverage (EARLY WARNING only)
  - straggler detection + (optional) rescue manifest

Type-error = (final vocal present) XOR (prompt requested vocal). present XOR requested.
Subcommands: label | snapshot | straggler | watch

DOES NOT modify reward/sigma/prompt-split/gate configs. Demucs forced device=cpu.
"""
from __future__ import annotations
import argparse, glob, json, math, os, re, time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# Re-pointed to the COMPLETE merged dataset (4096/4096) after the resume + audio consolidation
# (scripts/merge_resume_records.py + scripts/consolidate_merged_audio.py, 2026-06-09). The merged
# tree mirrors the original layout (shard0X/audio/<prompt>/candidate_*_seed*.wav via symlinks).
RUN = REPO / "runs/adsr_recollect_20260604_full01_merged"
DATASET = REPO / "orbit-research/trajectory_candidate_dataset.jsonl"
P2 = REPO / "orbit-research/adsr_phase2_20260604"
RAW = P2 / "vocal_presence_raw.jsonl"
MELDIR = P2 / "mel"
SNAPDIR = P2 / "snapshots"
N_PROMPTS = 512
EARLY_SIGMAS = ("0.9", "0.8", "0.7")
FINAL_WAV_RE = re.compile(r"candidate_(\d+)_seed\d+\.wav$")

# ---- requested type per prompt (from the canonical dataset; stable per prompt_id) ----
def requested_types() -> dict:
    out = {}
    for l in open(DATASET):
        r = json.loads(l)
        out[r["prompt_id"]] = {"requested": r.get("vocal_stratum"), "language": r.get("language"),
                               "split": r.get("split"), "lyric_density": (r.get("lyric_density") or
                               r.get("strata", {}).get("lyric_density"))}
    return out

def final_wavs_for(prompt_dir: Path):
    """return {cand_idx: path} for final (non-early) wavs."""
    out = {}
    for p in prompt_dir.glob("candidate_*_seed*.wav"):
        if "_early" in p.name:
            continue
        m = FINAL_WAV_RE.search(p.name)
        if m:
            out[int(m.group(1))] = p
    return out

def early_wavs_for(prompt_dir: Path, cand_idx: int):
    out = {}
    for sk in EARLY_SIGMAS:
        g = list(prompt_dir.glob(f"candidate_{cand_idx:02d}_seed*_early{sk}.wav"))
        if g:
            out[sk] = g[0]
    return out

def complete_prompts():
    """prompts whose audio dir has all 8 final wavs (ready to label)."""
    ready = []
    for shard in sorted(RUN.glob("shard0*")):
        adir = shard / "audio"
        if not adir.is_dir():
            continue
        for pdir in adir.iterdir():
            if pdir.is_dir() and len(final_wavs_for(pdir)) == 8:
                ready.append((pdir.name, pdir))
    return ready  # list of (prompt_id, prompt_dir)

# ---------------- worker: Demucs vocal-energy ratio + early mel ----------------
_MODEL = None
def _get_model():
    global _MODEL
    if _MODEL is None:
        import torch
        torch.set_num_threads(int(os.environ.get("ADSR_THREADS", "4")))
        from demucs.pretrained import get_model
        _MODEL = get_model("htdemucs"); _MODEL.cpu().eval()
    return _MODEL

def _label_one(args):
    prompt_id, prompt_dir, cand_idx, final_path = args
    import torch, soundfile as sf, numpy as np, librosa
    try:
        m = _get_model()
        model_sr = int(getattr(m, "samplerate", 44100))
        wav, sr = sf.read(str(final_path))
        stereo = wav.T if wav.ndim == 2 else np.stack([wav, wav])  # (ch, T)
        x = torch.tensor(stereo, dtype=torch.float32).unsqueeze(0)
        # Codex fix #1: htdemucs is trained at its model samplerate (44.1k); the audio is 48k.
        # Resample to the model rate before separation, else separation runs on pitch-shifted audio.
        if sr != model_sr:
            import torchaudio
            x = torchaudio.functional.resample(x, sr, model_sr)
        # Codex fix #2: absolute silence floor — a near-silent clip has no meaningful vocal ratio.
        input_rms = float(torch.sqrt((x ** 2).mean()))
        near_silent = input_rms < 1e-3
        from demucs.apply import apply_model
        with torch.no_grad():
            out = apply_model(m, x, device="cpu", split=True, overlap=0.1)[0]
        idx = {s: i for i, s in enumerate(m.sources)}
        en = {s: float((out[idx[s]] ** 2).mean()) for s in m.sources}
        tot = sum(en.values()) + 1e-12
        vr = en["vocals"] / tot
        # early mel (mono log-mel, n_mels=64, float16) for EVPD inputs
        mel_paths = {}
        for sk, ep in early_wavs_for(Path(prompt_dir), cand_idx).items():
            ew, esr = sf.read(str(ep))
            ew = ew.mean(axis=1) if ew.ndim == 2 else ew
            M = librosa.feature.melspectrogram(y=ew.astype("float32"), sr=esr, n_mels=64, hop_length=512)
            logM = librosa.power_to_db(M + 1e-9).astype("float16")
            mp = MELDIR / f"{prompt_id}__cand{cand_idx:02d}__early{sk}.npy"
            np.save(mp, logM)
            mel_paths[sk] = str(mp.relative_to(REPO))
        return {"prompt_id": prompt_id, "candidate_index": cand_idx,
                "vocal_energy_ratio": round(vr, 5), "input_rms": round(input_rms, 6),
                "near_silent": bool(near_silent), "model_sr": model_sr,
                "stem_energy": {k: round(v / tot, 4) for k, v in en.items()},
                "mel_paths": mel_paths, "ok": True}
    except Exception as e:
        return {"prompt_id": prompt_id, "candidate_index": cand_idx, "ok": False, "error": f"{type(e).__name__}: {e}"}

def cmd_label(args):
    MELDIR.mkdir(parents=True, exist_ok=True)
    done = set()
    if RAW.exists():
        for l in open(RAW):
            try:
                r = json.loads(l); done.add((r["prompt_id"], r["candidate_index"]))
            except Exception:
                pass
    tasks = []
    for pid, pdir in complete_prompts():
        for ci, fp in final_wavs_for(pdir).items():
            if (pid, ci) not in done:
                tasks.append((pid, str(pdir), ci, str(fp)))
    if args.limit:
        tasks = tasks[: args.limit]
    if not tasks:
        print(json.dumps({"event": "label", "new_tasks": 0, "already": len(done)})); return
    print(json.dumps({"event": "label_start", "new_tasks": len(tasks), "already": len(done),
                      "workers": args.workers}))
    os.environ["ADSR_THREADS"] = str(args.threads)
    n_ok = 0
    with open(RAW, "a") as f, ProcessPoolExecutor(max_workers=args.workers) as ex:
        for fut in as_completed([ex.submit(_label_one, t) for t in tasks]):
            r = fut.result()
            f.write(json.dumps(r) + "\n"); f.flush()
            n_ok += int(r.get("ok", False))
    print(json.dumps({"event": "label_done", "labeled_ok": n_ok, "total_now": len(done) + n_ok}))

# ---------------- snapshot: threshold + type-error + early-sigma AUC ----------------
def _gmm_valley(ratios):
    import numpy as np
    x = np.asarray([r for r in ratios if r is not None], dtype=float).reshape(-1, 1)
    if len(x) < 30:
        return 0.15, "default(<30)"
    try:
        from sklearn.mixture import GaussianMixture
        g = GaussianMixture(n_components=2, random_state=0).fit(x)
        mus = sorted(g.means_.ravel())
        grid = np.linspace(mus[0], mus[1], 200).reshape(-1, 1)
        return float(grid[np.argmin(np.exp(g.score_samples(grid)))][0]), f"gmm({mus[0]:.3f},{mus[1]:.3f})"
    except Exception:
        return float(np.median(x)), "median_fallback"

def _calibrate_threshold(recs):
    """Codex fix #2: strata-SUPERVISED threshold = midpoint of vocal-requested vs
    instrumental-requested ratio medians (excludes near-silent). Premise: type errors are the
    MINORITY (documented), so the two requested groups anchor the boundary; far more robust to
    coverage imbalance than a blind GMM. GMM valley + diagnostics reported as a cross-check, plus
    a confidence flag."""
    import numpy as np
    voc = [r["ratio"] for r in recs if r["requested"] == "vocal" and not r.get("near_silent")]
    ins = [r["ratio"] for r in recs if r["requested"] == "instrumental" and not r.get("near_silent")]
    diag = {"n_vocal_req": len(voc), "n_instr_req": len(ins)}
    allr = [r["ratio"] for r in recs if not r.get("near_silent")]
    if len(voc) >= 20 and len(ins) >= 20:
        mv, mi = float(np.median(voc)), float(np.median(ins))
        thr = (mv + mi) / 2.0; sep = mv - mi
        diag.update({"median_vocal_req": round(mv, 3), "median_instr_req": round(mi, 3), "separation": round(sep, 3)})
        how = "strata_median_midpoint"; conf = "high" if sep > 0.10 else "low(weak_separation)"
    else:
        thr, how0 = _gmm_valley(allr); how = "gmm_fallback_" + how0; conf = "low(insufficient_per_stratum)"
    try:
        gthr, _ = _gmm_valley(allr); diag["gmm_crosscheck_thr"] = round(gthr, 3)
    except Exception:
        pass
    return float(thr), how, conf, diag

def cmd_snapshot(args):
    req = requested_types()
    raw = [json.loads(l) for l in open(RAW)] if RAW.exists() else []
    raw = [r for r in raw if r.get("ok")]
    by = {(r["prompt_id"], r["candidate_index"]): r for r in raw}
    # Codex: coverage = prompts with ALL 8 ok labels (complete), not any
    cnt = defaultdict(int)
    for r in raw:
        cnt[r["prompt_id"]] += 1
    complete = sorted(p for p, c in cnt.items() if c == 8)
    cov = len(complete) / N_PROMPTS
    # build recs with requested type, ratio, near_silent
    recs, unknown_req = [], 0
    for (pid, ci), r in by.items():
        reqv = req.get(pid, {}).get("requested")
        if reqv not in ("vocal", "instrumental"):
            unknown_req += 1; continue  # Codex: don't silently count unknown as non-error
        recs.append({"prompt_id": pid, "ci": ci, "requested": reqv,
                     "ratio": r["vocal_energy_ratio"], "near_silent": bool(r.get("near_silent")),
                     "language": req.get(pid, {}).get("language")})
    thr, thr_how, thr_conf, thr_diag = _calibrate_threshold(recs)
    for x in recs:
        x["present"] = (x["ratio"] >= thr) and (not x["near_silent"])  # near-silent => no vocal
        x["type_error"] = (x["present"] and x["requested"] == "instrumental") or \
                          ((not x["present"]) and x["requested"] == "vocal")
    n = len(recs)
    cand_te = sum(x["type_error"] for x in recs) / n if n else 0
    by_p = defaultdict(list)
    for x in recs:
        by_p[x["prompt_id"]].append(x)
    affected = sum(1 for p, xs in by_p.items() if any(x["type_error"] for x in xs))
    prompt_rate = affected / len(by_p) if by_p else 0
    strat = {}
    for s in ("vocal", "instrumental"):
        xs = [x for x in recs if x["requested"] == s]
        strat[s] = {"n_cand": len(xs), "type_error_rate": round(sum(x["type_error"] for x in xs) / len(xs), 4) if xs else None}
    # Codex: type-error among common-score SURVIVORS — report top-1 / top-2 / top-4 (BoN survivor sets)
    ds = {}
    for l in open(DATASET):
        d = json.loads(l); ds[(d["prompt_id"], d["candidate_index"])] = d.get("final_common_robust_lcb")
    survivors = {}
    for k in (1, 2, 4):
        te = nn = 0
        for pid, xs in by_p.items():
            if len(xs) < 8:  # only fully-labeled prompts so survivor sets are well-defined
                continue
            ordered = sorted(xs, key=lambda x: ds.get((pid, x["ci"]), -1e9), reverse=True)[:k]
            nn += len(ordered); te += sum(int(x["type_error"]) for x in ordered)
        survivors[f"top{k}"] = round(te / nn, 4) if nn else None
    # Codex fix #1: early-sigma vocal-presence AUC on a PROMPT-LEVEL HELD-OUT split (dev=train, held_out=eval)
    auc = auprc = None; auc_n = 0; auc_note = ""
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import roc_auc_score, average_precision_score
        import numpy as np
        feats = {}
        for l in open(DATASET):
            d = json.loads(l)
            feats[(d["prompt_id"], d["candidate_index"])] = [d.get(f"early_{s}_{a}") for s in EARLY_SIGMAS
                for a in ("aesthetic_pq", "section_coherence", "probe_silence_fraction", "common_robust_lcb")]
        spl = {p: req.get(p, {}).get("split") for p in by_p}
        Xtr = Ytr = Xte = Yte = None
        tr = [(x, feats.get((x["prompt_id"], x["ci"]))) for x in recs if spl.get(x["prompt_id"]) == "dev"]
        te = [(x, feats.get((x["prompt_id"], x["ci"]))) for x in recs if spl.get(x["prompt_id"]) == "held_out"]
        tr = [(x, f) for x, f in tr if f and all(v is not None for v in f)]
        te = [(x, f) for x, f in te if f and all(v is not None for v in f)]
        if len({x["present"] for x, _ in tr}) == 2 and len({x["present"] for x, _ in te}) == 2 and len(tr) >= 40 and len(te) >= 40:
            m = LogisticRegression(max_iter=500).fit(np.array([f for _, f in tr]), np.array([int(x["present"]) for x, _ in tr]))
            p = m.predict_proba(np.array([f for _, f in te]))[:, 1]
            yte = np.array([int(x["present"]) for x, _ in te])
            auc = round(float(roc_auc_score(yte, p)), 4); auprc = round(float(average_precision_score(yte, p)), 4); auc_n = len(yte)
            auc_note = "prompt-level held-out (train=dev prompts, eval=held_out prompts); scalar early features only (NOT the EVPD mel-CNN, which is Phase 2A)"
        else:
            auc_note = "insufficient/degenerate held-out classes yet"
    except Exception as e:
        auc = f"err:{type(e).__name__}"
    near_silent_n = sum(1 for x in recs if x["near_silent"])
    snap = {"coverage_complete_prompts": len(complete), "coverage_frac": round(cov, 4),
            "n_candidates_labeled": n, "near_silent_candidates": near_silent_n, "unknown_requested_skipped": unknown_req,
            "threshold": round(thr, 4), "threshold_method": thr_how, "threshold_confidence": thr_conf, "threshold_diag": thr_diag,
            "candidate_type_error_prevalence": round(cand_te, 4),
            "prompt_level_affected_rate": round(prompt_rate, 4),
            "per_requested_stratum": strat,
            "type_error_rate_among_common_score_survivors": survivors,
            "early_sigma_vocal_presence_AUC_heldout": auc, "AUPRC_heldout": auprc, "auc_n_heldout": auc_n, "auc_note": auc_note,
            "WARNING": "EARLY-WARNING ONLY — NOT a paper claim. Threshold is provisional/strata-supervised (assumes type-errors are the minority; recalibrated as coverage grows). AUC is a held-out scalar-feature proxy; the real EVPD mel-CNN onset-σ study is Phase 2A."}
    tag = args.tag or f"cov{int(cov*100):02d}"
    (SNAPDIR / f"snapshot_{tag}.json").write_text(json.dumps(snap, indent=2))
    print(json.dumps(snap, indent=2))
    return snap

# ---------------- straggler detection (Codex: real rate + projection) ----------------
def _utc_epoch(s):
    import datetime
    try:
        return datetime.datetime.strptime(s.replace("Z", ""), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc).timestamp()
    except Exception:
        return None

def cmd_straggler(args):
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    per = {}
    for shard in sorted(RUN.glob("shard0*")):
        if not shard.is_dir():
            continue
        rec = shard / "candidate_records.jsonl"
        n = sum(1 for _ in open(rec)) if rec.exists() else 0
        ss = shard / "run_summary.json"
        t0 = None
        if ss.exists():
            try:
                t0 = _utc_epoch(json.load(open(ss)).get("generated_at_utc"))
            except Exception:
                pass
        # subtract a ~5min model-load so the rate reflects steady-state generation
        elapsed = max((now - t0) - 300, 1.0) if t0 else None
        rate = (n / elapsed) if (elapsed and n > 0) else None  # records/sec
        target = int(getattr(args, "target_per_shard", 512))
        eta_h = ((target - n) / rate / 3600.0) if (rate and rate > 0) else None
        per[shard.name] = {"records": n, "rate_per_min": round(rate * 60, 3) if rate else None,
                           "remaining": target - n, "eta_h": round(eta_h, 2) if eta_h is not None else None}
    rates = [v["rate_per_min"] for v in per.values() if v["rate_per_min"]]
    med_rate = sorted(rates)[len(rates) // 2] if rates else None
    etas = [v["eta_h"] for v in per.values() if v["eta_h"] is not None]
    med_eta = sorted(etas)[len(etas) // 2] if etas else None
    stragglers = {}
    for s, v in per.items():
        if med_rate and v["rate_per_min"] is not None and v["rate_per_min"] < 0.6 * med_rate \
           and med_eta is not None and v["eta_h"] is not None and (v["eta_h"] - med_eta) > 4.0:
            stragglers[s] = {**v, "drag_h_over_median": round(v["eta_h"] - med_eta, 2)}
    out = {"per_shard": per, "median_rate_per_min": med_rate, "median_eta_h": med_eta,
           "stragglers_60pct_rate_and_4h_drag": stragglers,
           "policy": "If a shard is <60% of median rate AND projected to finish >4h after the median, "
                     "build a rescue manifest of its NOT-complete prompts and run on a freed GPU; "
                     "merge dedupes by (prompt_id, candidate_index)."}
    print(json.dumps(out, indent=2)); return out

# ---------------- watch loop ----------------
def cmd_watch(args):
    fired = set()
    targets = [0.25, 0.50, 0.70]
    while True:
        cmd_label(argparse.Namespace(workers=args.workers, threads=args.threads, limit=None))
        raw = [json.loads(l) for l in open(RAW)] if RAW.exists() else []
        # Codex re-review: trigger the partial-decision snapshots on COMPLETE (8-ok) prompt
        # coverage, matching cmd_snapshot's coverage definition (not any-label coverage).
        cnt = defaultdict(int)
        for r in raw:
            if r.get("ok"):
                cnt[r["prompt_id"]] += 1
        cov = sum(1 for c in cnt.values() if c == 8) / N_PROMPTS
        for t in targets:
            if cov >= t and t not in fired:
                fired.add(t)
                cmd_snapshot(argparse.Namespace(tag=f"cov{int(t*100):02d}"))
        cmd_straggler(argparse.Namespace())
        shard_dirs = [s for s in RUN.glob("shard0*") if s.is_dir()]
        total_recs = sum(sum(1 for _ in open(s / "candidate_records.jsonl"))
                         for s in shard_dirs if (s / "candidate_records.jsonl").exists())
        if total_recs >= 4096 and cov >= 0.99:
            cmd_snapshot(argparse.Namespace(tag="final"))
            print(json.dumps({"event": "watch_done", "coverage": cov})); break
        if not any(True for _ in REPO.glob(".keep_never")):
            pass
        # stop watching if generation finished and labeling caught up
        procs = os.popen("ps aux | grep collect_early_tweedie | grep -v grep | wc -l").read().strip()
        if procs == "0" and cov >= 0.99:
            print(json.dumps({"event": "watch_done_genfinished", "coverage": cov})); break
        time.sleep(args.interval)

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("label"); pl.add_argument("--workers", type=int, default=14); pl.add_argument("--threads", type=int, default=4); pl.add_argument("--limit", type=int, default=None)
    ps = sub.add_parser("snapshot"); ps.add_argument("--tag", default=None)
    sub.add_parser("straggler")
    pw = sub.add_parser("watch"); pw.add_argument("--workers", type=int, default=14); pw.add_argument("--threads", type=int, default=4); pw.add_argument("--interval", type=int, default=300)
    a = ap.parse_args()
    {"label": cmd_label, "snapshot": cmd_snapshot, "straggler": cmd_straggler, "watch": cmd_watch}[a.cmd](a)

if __name__ == "__main__":
    main()
