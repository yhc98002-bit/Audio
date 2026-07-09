#!/usr/bin/env python
"""Persist the FIXED Batch-2 σ0.8 EVPD model for ONLINE inference (Batch 3).

Trains the σ0.8 mel-summary logistic detector on the Batch-1 TRAIN split (deterministic), tunes the
operating threshold on VAL (the FIXED Batch-2 threshold — NOT retuned on Batch-3 outputs), and saves
model + scaler + threshold + the exact mel/feature spec via joblib. This is the σ0.8 per-σ model the
Batch-2 σ-frontier used (held-out AUC ~0.916). Online code MUST replicate the mel spec exactly.
"""
from __future__ import annotations
import json, hashlib
from pathlib import Path
import numpy as np
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / "orbit-research/adsr_phase2_20260604/batch2/evpd_feature_cache.npz"
OUT = REPO / "orbit-research/adsr_phase2_20260604/batch2/evpd_sigma08_online.joblib"
SIGMA_IDX = 1  # SIGMAS=["0.9","0.8","0.7"] -> σ0.8 is index 1
MEL_SPEC = {"n_mels": 64, "hop_length": 512, "power_to_db": True, "eps": 1e-9,
            "summary": ["mean", "std", "max", "p25", "p75"], "decode_z0": "sample - sigma*model_output"}


def best_thr_balacc(y, p):
    best, bt = -1, 0.5
    for t in np.unique(np.round(p, 3)):
        pred = (p >= t).astype(int)
        tp = ((pred == 1) & (y == 1)).sum(); tn = ((pred == 0) & (y == 0)).sum()
        rec = tp / max((y == 1).sum(), 1); spec = tn / max((y == 0).sum(), 1)
        ba = (rec + spec) / 2
        if ba > best:
            best, bt = ba, float(t)
    return bt


def main():
    d = np.load(CACHE, allow_pickle=True)
    summ, y, split = d["summ"], d["y"], d["split"].astype(str)
    X = summ[:, SIGMA_IDX, :]                  # σ0.8 per-band summary (320-d)
    tr, va = split == "train", split == "val"
    sc = StandardScaler().fit(X[tr])
    clf = LogisticRegression(max_iter=1000, class_weight="balanced").fit(sc.transform(X[tr]), y[tr])
    pv = clf.predict_proba(sc.transform(X[va]))[:, 1]
    thr = best_thr_balacc(y[va], pv)
    val_auc = float(roc_auc_score(y[va], pv)) if len(set(y[va].tolist())) == 2 else None
    # held-out (test) AUC for the record (NOT used for any tuning)
    te = split == "test"
    pt = clf.predict_proba(sc.transform(X[te]))[:, 1]
    test_auc = float(roc_auc_score(y[te], pt)) if len(set(y[te].tolist())) == 2 else None
    bundle = {"model": clf, "scaler": sc, "threshold": thr, "sigma": "0.8", "sigma_idx": SIGMA_IDX,
              "feature": "per-band [mean,std,max,p25,p75] of 64-bin log-mel(dB) at σ0.8 (320-d)",
              "mel_spec": MEL_SPEC, "val_auc": val_auc, "test_auc": test_auc,
              "trained_on": "Batch-1 dev train split (deterministic)", "frozen": True,
              "note": "FIXED Batch-2 EVPD; threshold val-tuned, NOT retuned on Batch-3. predict_present(p>=threshold)."}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, OUT)
    print(json.dumps({"saved": str(OUT.relative_to(REPO)), "threshold": round(thr, 4),
                      "val_auc": round(val_auc, 4) if val_auc else None,
                      "test_auc": round(test_auc, 4) if test_auc else None,
                      "n_train": int(tr.sum()), "n_val": int(va.sum()), "feat_dim": X.shape[1]}, indent=2))


if __name__ == "__main__":
    main()
