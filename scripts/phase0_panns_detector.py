#!/usr/bin/env python
"""P0.6c — PANNs (Cnn14/AudioSet) as an ALTERNATIVE vocal-presence detector over the 4,096 finals.

Breaks the Demucs-circularity objection: an independent architecture/training corpus gives
(a) alternate ground truth (agreement with Demucs label) and (b) an alternate policy filter.
Vocal score = max over AudioSet classes {Singing, Speech, Male/Female singing, Choir, Rapping,
Human voice}. Resumable; GPU.

Output: orbit-research/adsr_phase2_20260604/phase0/panns_labels.jsonl + P0_6_PANNS_AGREEMENT.json
"""
from __future__ import annotations
import glob, json, sys, time
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
MERGED = REPO / "runs/adsr_recollect_20260604_full01_merged"
RAW = REPO / "orbit-research/adsr_phase2_20260604/vocal_presence_raw.jsonl"
P0 = REPO / "orbit-research/adsr_phase2_20260604/phase0"
OUT = P0 / "panns_labels.jsonl"
THR = 0.1791
VOCAL_CLASSES = ["Singing", "Speech", "Male singing", "Female singing", "Child singing",
                 "Choir", "Rapping", "Human voice", "Vocal music", "A capella"]


def main():
    import librosa, torch
    from panns_inference import AudioTagging
    from panns_inference.config import labels as panns_labels
    idx = [i for i, l in enumerate(panns_labels) if l in VOCAL_CLASSES]
    print(f"vocal-class indices: {[(panns_labels[i]) for i in idx]}", flush=True)
    at = AudioTagging(checkpoint_path=None, device="cuda")
    recs = {}
    for f in sorted(glob.glob(str(MERGED / "shard0*" / "candidate_records.jsonl"))):
        for l in open(f):
            r = json.loads(l); recs[(r["prompt_id"], r["candidate_index"])] = r
    done = set()
    if OUT.exists():
        for l in open(OUT):
            try:
                d = json.loads(l); done.add((d["prompt_id"], d["candidate_index"]))
            except Exception:
                pass
    todo = [(k, r) for k, r in sorted(recs.items()) if k not in done]
    print(f"{len(todo)} to score ({len(done)} done)", flush=True)
    n = 0; t0 = time.time()
    with OUT.open("a") as fh:
        for (pid, ci), r in todo:
            try:
                y, _ = librosa.load(str(REPO / r["audio_path"]), sr=32000, mono=True)
                clip, _ = at.inference(y[None, :])
                p = clip[0]
                fh.write(json.dumps({"prompt_id": pid, "candidate_index": ci,
                                     "panns_vocal_score": round(float(np.max(p[idx])), 5),
                                     "top_vocal_class": panns_labels[idx[int(np.argmax(p[idx]))]]}) + "\n")
            except Exception as e:
                fh.write(json.dumps({"prompt_id": pid, "candidate_index": ci,
                                     "error": f"{type(e).__name__}: {e}"}) + "\n")
            fh.flush(); n += 1
            if n % 200 == 0:
                print(f"{n}/{len(todo)} ({n/max(time.time()-t0,1):.1f}/s)", flush=True)
    # ---- agreement analysis ----
    lab = {}
    for l in open(RAW):
        d = json.loads(l)
        if d.get("ok"):
            lab[(d["prompt_id"], d["candidate_index"])] = d
    rows = []
    for l in open(OUT):
        d = json.loads(l)
        if "panns_vocal_score" in d:
            k = (d["prompt_id"], d["candidate_index"])
            L = lab[k]; r = recs[k]
            rows.append({"panns": d["panns_vocal_score"],
                         "demucs_present": int((L["vocal_energy_ratio"] >= THR) and not L.get("near_silent")),
                         "req": int(r.get("vocal_stratum") == "vocal")})
    from sklearn.metrics import roc_auc_score
    y = np.array([r["demucs_present"] for r in rows]); s = np.array([r["panns"] for r in rows])
    req = np.array([r["req"] for r in rows])
    # pick PANNs threshold by balanced accuracy vs the REQUEST-type separation (label-free-ish):
    ths = np.percentile(s, np.linspace(5, 95, 60))
    best, bt = -1, 0.5
    for t in ths:
        pred = (s >= t).astype(int)
        tp = ((pred == 1) & (y == 1)).sum(); tn = ((pred == 0) & (y == 0)).sum()
        ba = (tp / max((y == 1).sum(), 1) + tn / max((y == 0).sum(), 1)) / 2
        if ba > best:
            best, bt = ba, float(t)
    pred = (s >= bt).astype(int)
    agree = float((pred == y).mean())
    rep = {"n": len(rows), "auc_panns_vs_demucs_label": round(float(roc_auc_score(y, s)), 4),
           "panns_thr_balacc": round(bt, 4), "agreement_at_thr": round(agree, 4),
           "cohens_kappa": round(float(((pred == y).mean() - ((pred.mean() * y.mean()) + ((1 - pred.mean()) * (1 - y.mean())))) /
                                       (1 - ((pred.mean() * y.mean()) + ((1 - pred.mean()) * (1 - y.mean()))))), 4),
           "type_error_rate_under_panns_label": round(float((pred != req).mean()), 4),
           "type_error_rate_under_demucs_label": round(float((y != req).mean()), 4)}
    (P0 / "P0_6_PANNS_AGREEMENT.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()
