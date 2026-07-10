#!/usr/bin/env python
"""Batch 2 Stage 3 — EVPD training + evaluation (Worker B).

Predict FINAL Demucs vocal-presence from EARLY-σ log-mels (σ0.9/0.8/0.7). Prompt-level splits
(held_out=test; dev→train/val). Models: scalar-proxy baseline, logistic/LightGBM on mel-summary,
small log-mel CNN (GPU), multi-σ fusion. Multi-seed. Full metrics + type-error detection +
survivor-set type-error. No final-audio/reward/label/candidate_id leakage; threshold on val only.

Usage: batch2_stage3_evpd.py [--build-cache] [--seeds 0 1 2] [--epochs 30] [--device cuda]
Outputs: EVPD_RESULTS.{md,json}, EVPD_SPLIT_REPORT.md, EVPD_MODEL_CARD.md  (+ cache npz)
"""
from __future__ import annotations
import argparse, glob, hashlib, json, os, sys
from collections import defaultdict
from pathlib import Path
import numpy as np

from mprm.common.thresholds import VOCAL_PRESENCE_THRESHOLD

REPO = Path(__file__).resolve().parent.parent
MERGED = REPO / "runs/adsr_recollect_20260604_full01_merged"
RAW = REPO / "orbit-research/adsr_phase2_20260604/vocal_presence_raw.jsonl"
MELDIR = REPO / "orbit-research/adsr_phase2_20260604/mel"
P2 = REPO / "orbit-research/adsr_phase2_20260604"
CACHE = P2 / "batch2" / "evpd_feature_cache.npz"
SIGMAS = ["0.9", "0.8", "0.7"]
THR_LABEL = VOCAL_PRESENCE_THRESHOLD
TPOOL = 128                  # adaptive time-pool width for CNN
SCALAR_KEYS = ["aesthetic_pq", "section_coherence", "probe_silence_fraction", "common_robust_lcb"]


def prompt_split(pid, dev_is):
    """held_out -> test; dev -> train(~80%)/val(~20%) by deterministic prompt hash."""
    if not dev_is:
        return "test"
    h = int(hashlib.md5(pid.encode()).hexdigest(), 16) % 100
    return "val" if h < 20 else "train"


def build_cache():
    recs = {}
    for f in sorted(glob.glob(str(MERGED / "shard0*" / "candidate_records.jsonl"))):
        for l in open(f):
            if l.strip():
                r = json.loads(l); recs[(r["prompt_id"], r["candidate_index"])] = r
    lab = {}
    for l in open(RAW):
        r = json.loads(l)
        if r.get("ok"):
            lab[(r["prompt_id"], r["candidate_index"])] = r
    keys = sorted(recs.keys())
    N = len(keys)
    summ = np.zeros((N, len(SIGMAS), 64 * 5), np.float32)   # per-band mean/std/max/p25/p75
    cnn = np.zeros((N, len(SIGMAS), 64, TPOOL), np.float32)  # adaptive-pooled mel
    scal = np.zeros((N, len(SIGMAS), len(SCALAR_KEYS)), np.float32)
    y = np.zeros(N, np.int64); req = np.zeros(N, np.int64); common = np.zeros(N, np.float32)
    split = np.empty(N, object); pid_arr = np.empty(N, object); ci_arr = np.zeros(N, np.int64)
    lang = np.empty(N, object)
    for i, k in enumerate(keys):
        r, L = recs[k], lab[k]
        pid_arr[i] = k[0]; ci_arr[i] = k[1]
        y[i] = int((L["vocal_energy_ratio"] >= THR_LABEL) and not L.get("near_silent"))
        req[i] = int(r.get("vocal_stratum") == "vocal")
        common[i] = r.get("final_common_robust_lcb") if r.get("final_common_robust_lcb") is not None else -1e9
        lang[i] = r.get("language")
        split[i] = prompt_split(k[0], r.get("split") == "dev")
        for si, sk in enumerate(SIGMAS):
            mp = L.get("mel_paths", {}).get(sk)
            m = np.load(REPO / mp).astype(np.float32)        # 64 x T
            summ[i, si] = np.concatenate([m.mean(1), m.std(1), m.max(1),
                                          np.percentile(m, 25, 1), np.percentile(m, 75, 1)])
            # adaptive avg-pool time -> TPOOL
            T = m.shape[1]; idx = (np.linspace(0, T, TPOOL + 1)).astype(int)
            cnn[i, si] = np.stack([m[:, idx[j]:max(idx[j] + 1, idx[j + 1])].mean(1) for j in range(TPOOL)], 1)
            for ki, kk in enumerate(SCALAR_KEYS):
                v = r.get(f"early_{sk}_{kk}")
                scal[i, si, ki] = v if isinstance(v, (int, float)) else 0.0
        if i % 500 == 0:
            print(f"  cache {i}/{N}", flush=True)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(CACHE, summ=summ, cnn=cnn, scal=scal, y=y, req=req, common=common,
                        split=split.astype(str), pid=pid_arr.astype(str), ci=ci_arr, lang=lang.astype(str))
    print(f"wrote {CACHE} N={N}")


# ---------------- metrics ----------------
def metrics(y, p, thr=None):
    from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
    y = np.asarray(y); p = np.asarray(p)
    out = {"n": int(len(y)), "pos_rate": round(float(y.mean()), 4)}
    if len(set(y.tolist())) == 2:
        out["auc"] = round(float(roc_auc_score(y, p)), 4)
        out["auprc"] = round(float(average_precision_score(y, p)), 4)
        out["brier"] = round(float(brier_score_loss(y, np.clip(p, 0, 1))), 4)
        # recall@precision>=0.8 and precision@recall>=0.8 via PR curve
        from sklearn.metrics import precision_recall_curve
        pr, rc, th = precision_recall_curve(y, p)
        rec_at_p80 = max([rc[i] for i in range(len(pr)) if pr[i] >= 0.8], default=0.0)
        prec_at_r80 = max([pr[i] for i in range(len(rc)) if rc[i] >= 0.8], default=0.0)
        out["recall_at_prec80"] = round(float(rec_at_p80), 4)
        out["prec_at_recall80"] = round(float(prec_at_r80), 4)
    if thr is not None:
        pred = (p >= thr).astype(int)
        tp = int(((pred == 1) & (y == 1)).sum()); fp = int(((pred == 1) & (y == 0)).sum())
        tn = int(((pred == 0) & (y == 0)).sum()); fn = int(((pred == 0) & (y == 1)).sum())
        prec = tp / (tp + fp) if tp + fp else 0.0; rec = tp / (tp + fn) if tp + fn else 0.0
        spec = tn / (tn + fp) if tn + fp else 0.0
        out.update({"thr": round(float(thr), 4), "precision": round(prec, 4), "recall": round(rec, 4),
                    "balanced_acc": round((rec + spec) / 2, 4), "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn}})
    return out


def best_thr_on_val(y, p):
    # threshold maximizing balanced accuracy on val
    ths = np.unique(np.round(p, 3))
    best, bt = -1, 0.5
    for t in ths:
        pred = (p >= t).astype(int)
        tp = ((pred == 1) & (y == 1)).sum(); tn = ((pred == 0) & (y == 0)).sum()
        rec = tp / max((y == 1).sum(), 1); spec = tn / max((y == 0).sum(), 1)
        ba = (rec + spec) / 2
        if ba > best:
            best, bt = ba, t
    return float(bt)


# ---------------- CNN ----------------
def train_cnn(Xtr, ytr, Xva, yva, Xte, device, epochs, seed):
    import torch, torch.nn as nn
    torch.manual_seed(seed); np.random.seed(seed)
    C = Xtr.shape[1]  # channels = n sigma used
    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.f = nn.Sequential(
                nn.Conv2d(C, 16, 3, padding=1), nn.BatchNorm2d(16), nn.ReLU(), nn.MaxPool2d(2),
                nn.Conv2d(16, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(), nn.AdaptiveAvgPool2d(1))
            self.h = nn.Sequential(nn.Flatten(), nn.Dropout(0.3), nn.Linear(32, 1))
        def forward(self, x): return self.h(self.f(x)).squeeze(1)
    dev = torch.device(device if torch.cuda.is_available() else "cpu")
    net = Net().to(dev)
    Xtr_t = torch.tensor(Xtr, dtype=torch.float32); ytr_t = torch.tensor(ytr, dtype=torch.float32)
    opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=1e-4)
    pos_w = torch.tensor([(ytr == 0).sum() / max((ytr == 1).sum(), 1)], dtype=torch.float32, device=dev)
    lossf = nn.BCEWithLogitsLoss(pos_weight=pos_w)
    best_va, best_state = -1, None
    bs = 256
    for ep in range(epochs):
        net.train(); perm = torch.randperm(len(Xtr_t))
        for j in range(0, len(perm), bs):
            idx = perm[j:j + bs]
            xb = Xtr_t[idx].to(dev); yb = ytr_t[idx].to(dev)
            opt.zero_grad(); out = net(xb); loss = lossf(out, yb); loss.backward(); opt.step()
        net.eval()
        with torch.no_grad():
            pv = torch.sigmoid(net(torch.tensor(Xva, dtype=torch.float32).to(dev))).cpu().numpy()
        from sklearn.metrics import roc_auc_score
        va = roc_auc_score(yva, pv) if len(set(yva.tolist())) == 2 else 0
        if va > best_va:
            best_va = va; best_state = {k: v.cpu().clone() for k, v in net.state_dict().items()}
    net.load_state_dict(best_state); net.eval()
    with torch.no_grad():
        pv = torch.sigmoid(net(torch.tensor(Xva, dtype=torch.float32).to(dev))).cpu().numpy()
        pt = torch.sigmoid(net(torch.tensor(Xte, dtype=torch.float32).to(dev))).cpu().numpy()
    return pv, pt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-cache", action="store_true")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--device", default="cuda:0")
    args = ap.parse_args()
    if args.build_cache or not CACHE.exists():
        print("building feature cache..."); build_cache()
    d = np.load(CACHE, allow_pickle=True)
    summ, cnn, scal, y, req, common, split, pid, ci, lang = (d["summ"], d["cnn"], d["scal"], d["y"],
        d["req"], d["common"], d["split"].astype(str), d["pid"].astype(str), d["ci"], d["lang"].astype(str))
    tr, va, te = split == "train", split == "val", split == "test"
    # split report
    def split_counts(m):
        return {"candidates": int(m.sum()), "prompts": int(len(set(pid[m])))}
    splitrep = {"train": split_counts(tr), "val": split_counts(va), "test": split_counts(te),
                "prompt_overlap_train_test": int(len(set(pid[tr]) & set(pid[te]))),
                "prompt_overlap_train_val": int(len(set(pid[tr]) & set(pid[va]))),
                "prompt_overlap_val_test": int(len(set(pid[va]) & set(pid[te]))),
                "label_pos_rate_overall": round(float(y.mean()), 4)}
    (P2 / "EVPD_SPLIT_REPORT.md").write_text(
        "# EVPD Split Report\n\n" + json.dumps(splitrep, indent=2) +
        "\n\n- test = held_out (untouched). dev -> train/val by prompt hash. 0 overlap required.\n"
        "- All 8 candidates of a prompt share a split (split assigned per prompt_id).")
    # Codex BLOCKING safeguards: hard-fail unless the plan is honored.
    assert splitrep["prompt_overlap_train_test"] == 0 and splitrep["prompt_overlap_val_test"] == 0 \
        and splitrep["prompt_overlap_train_val"] == 0, "SPLIT LEAK (prompt crosses splits)"
    per_prompt_splits = defaultdict(set)
    for j in range(len(pid)):
        per_prompt_splits[pid[j]].add(split[j])
    assert all(len(s) == 1 for s in per_prompt_splits.values()), "SPLIT LEAK (a prompt's 8 candidates span >1 split)"
    # feature-safety: the model features (summ/cnn/scal) are built ONLY from early mels + these early
    # scalar keys; assert no lyric/whisper/final/candidate_id/prompt_id/split field can be a feature.
    assert not any(any(b in k for b in ("lyric", "whisper", "final", "ratio")) for k in SCALAR_KEYS), \
        "FEATURE LEAK (a scalar key references a forbidden field)"

    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    import lightgbm as lgb
    results = {"label_threshold": THR_LABEL, "split": splitrep, "prevalence_test": round(float(y[te].mean()), 4),
               "models": {}}

    def fit_eval(name, Xtr, Xva, Xte, kind, multiseed=False):
        rec = {}
        if kind == "logit":
            sc = StandardScaler().fit(Xtr)
            m = LogisticRegression(max_iter=1000, class_weight="balanced").fit(sc.transform(Xtr), y[tr])
            pv = m.predict_proba(sc.transform(Xva))[:, 1]; pt = m.predict_proba(sc.transform(Xte))[:, 1]
            thr = best_thr_on_val(y[va], pv)
            rec = {"val": metrics(y[va], pv, thr), "test": metrics(y[te], pt, thr), "p_test": pt}
        elif kind == "gbdt":
            m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31,
                                   class_weight="balanced", verbose=-1, random_state=0)
            m.fit(Xtr, y[tr], eval_set=[(Xva, y[va])])
            pv = m.predict_proba(Xva)[:, 1]; pt = m.predict_proba(Xte)[:, 1]
            thr = best_thr_on_val(y[va], pv)
            rec = {"val": metrics(y[va], pv, thr), "test": metrics(y[te], pt, thr), "p_test": pt}
        elif kind == "cnn":
            pvs, pts = [], []
            for s in args.seeds:
                pv, pt = train_cnn(Xtr, y[tr], Xva, y[va], Xte, args.device, args.epochs, s)
                pvs.append(pv); pts.append(pt)
            pv = np.mean(pvs, 0); pt = np.mean(pts, 0)
            thr = best_thr_on_val(y[va], pv)
            mt = metrics(y[te], pt, thr)
            mt["seed_test_auc"] = [round(float(metrics(y[te], p)["auc"]), 4) for p in pts]
            rec = {"val": metrics(y[va], pv, thr), "test": mt, "p_test": pt}
        results["models"][name] = {"val": rec["val"], "test": rec["test"]}
        return rec["p_test"]

    PT = {}   # name -> test predictions (capture ALL models so we can deploy the best-on-VAL)
    for si, sk in enumerate(SIGMAS):
        PT[f"scalar_logit_s{sk}"] = fit_eval(f"scalar_logit_s{sk}", scal[tr, si], scal[va, si], scal[te, si], "logit")
        PT[f"melsumm_logit_s{sk}"] = fit_eval(f"melsumm_logit_s{sk}", summ[tr, si], summ[va, si], summ[te, si], "logit")
        PT[f"melsumm_gbdt_s{sk}"] = fit_eval(f"melsumm_gbdt_s{sk}", summ[tr, si], summ[va, si], summ[te, si], "gbdt")
        PT[f"cnn_s{sk}"] = fit_eval(f"cnn_s{sk}", cnn[tr, si:si+1], cnn[va, si:si+1], cnn[te, si:si+1], "cnn")
    Sall = summ.reshape(len(y), -1)
    PT["melsumm_gbdt_fused"] = fit_eval("melsumm_gbdt_fused", Sall[tr], Sall[va], Sall[te], "gbdt")
    PT["cnn_fused_s987"] = fit_eval("cnn_fused_s987", cnn[tr], cnn[va], cnn[te], "cnn")
    # DEPLOYED EVPD = best model by VALIDATION AUC (legit selection; never test). For the ADSR sim
    # at the σ0.7 onset decision, restrict deployment to σ0.7-or-fused models (earliest-usable strong).
    DEPLOY_POOL = [m for m in PT if ("s0.7" in m or "fused" in m) and not m.startswith("scalar")]
    deployed = max(DEPLOY_POOL, key=lambda m: results["models"][m]["val"].get("auc", 0))
    p_deploy = PT[deployed]
    thr_deploy = results["models"][deployed]["val"].get("thr", 0.5)
    results["deployed_evpd_model"] = {"name": deployed, "selected_by": "val AUC among σ0.7/fused non-scalar",
                                      "val_auc": results["models"][deployed]["val"].get("auc"),
                                      "test": results["models"][deployed]["test"]}

    # ---- type-error & survivor-set DETECTION (the ADSR-relevant evaluation) ----
    # predicted_present from the best model's test prob @ val threshold; predicted type-error = (pred != requested)
    def detection(name, pt, thr):
        pred = (pt >= thr).astype(int)
        te_true = (y[te] != req[te]).astype(int)            # true type-error on test
        te_pred = (pred != req[te]).astype(int)             # EVPD-flagged type-error
        tp = int(((te_pred == 1) & (te_true == 1)).sum()); fp = int(((te_pred == 1) & (te_true == 0)).sum())
        fn = int(((te_pred == 0) & (te_true == 1)).sum())
        prec = tp / (tp + fp) if tp + fp else 0.0; rec = tp / (tp + fn) if tp + fn else 0.0
        # survivor-set: among common-score top-1 per test prompt, type-error true vs flagged
        idx_te = np.where(te)[0]
        byp = defaultdict(list)
        for j in idx_te:
            byp[pid[j]].append(j)
        surv_true = surv_flagged_correct = surv_n = 0
        for p, js in byp.items():
            if len(js) < 8:
                continue
            top = max(js, key=lambda j: common[j])
            surv_n += 1
            tt = int(y[top] != req[top]); tf = int((1 if pt[np.where(idx_te == top)[0][0]] >= thr else 0) != req[top])
            surv_true += tt; surv_flagged_correct += int(tt == 1 and tf == 1)
        ntest = len(te_true)
        return {"type_error_detect_precision": round(prec, 4), "type_error_detect_recall": round(rec, 4),
                "type_error_true_n": int(te_true.sum()), "type_error_flagged_n": int(te_pred.sum()),
                # restart accounting at this operating point (a "restart" = EVPD flags predicted mismatch)
                "restart_rate": round(float(te_pred.mean()), 4),
                "false_restart_rate": round(float(((te_pred == 1) & (te_true == 0)).mean()), 4),
                "false_restart_frac_of_restarts": round(fp / (tp + fp), 4) if (tp + fp) else None,
                "survivor_top1_prompts": surv_n, "survivor_top1_true_type_errors": surv_true,
                "survivor_top1_caught": surv_flagged_correct,
                "survivor_top1_catch_rate": round(surv_flagged_correct / surv_true, 4) if surv_true else None}
    det = {deployed: detection(deployed, p_deploy, thr_deploy)}
    results["type_error_and_survivor_detection"] = det
    results["detection_model"] = f"{deployed} (best-on-VAL deployed EVPD; threshold val-tuned)"

    # prompt-level bootstrap CI for the primary (fused CNN) held-out AUC/AUPRC (Codex #6)
    from sklearn.metrics import roc_auc_score, average_precision_score
    idx_te = np.where(te)[0]
    byp = defaultdict(list)
    for jj, j in enumerate(idx_te):
        byp[pid[j]].append(jj)
    test_prompts = list(byp.keys())
    rng = np.random.RandomState(0)
    aucs, aps = [], []
    yte = y[te]; pte = p_deploy
    for _ in range(500):
        samp = rng.choice(len(test_prompts), len(test_prompts), replace=True)
        rows_b = [r for s in samp for r in byp[test_prompts[s]]]
        yb, pb = yte[rows_b], pte[rows_b]
        if len(set(yb.tolist())) == 2:
            aucs.append(roc_auc_score(yb, pb)); aps.append(average_precision_score(yb, pb))
    results["deployed_evpd_test_bootstrap_ci"] = {
        "auc_mean": round(float(np.mean(aucs)), 4), "auc_ci95": [round(float(np.percentile(aucs, 2.5)), 4), round(float(np.percentile(aucs, 97.5)), 4)],
        "auprc_mean": round(float(np.mean(aps)), 4), "auprc_ci95": [round(float(np.percentile(aps, 2.5)), 4), round(float(np.percentile(aps, 97.5)), 4)],
        "method": "prompt-level resampling, 500 reps"}

    # Save per-candidate EVPD predictions on the held-out TEST prompts (out-of-fold: model trained
    # on dev only) for the Stage-4 ADSR offline simulation — no leakage into the sim prompts.
    with (P2 / "batch2" / "evpd_test_predictions.jsonl").open("w") as fh:
        for jj, j in enumerate(np.where(te)[0]):
            fh.write(json.dumps({"prompt_id": pid[j], "candidate_index": int(ci[j]),
                                 "evpd_model": deployed,
                                 "evpd_p": float(p_deploy[jj]), "evpd_thr": float(thr_deploy),
                                 "evpd_pred_present": int(p_deploy[jj] >= thr_deploy),
                                 "true_present": int(y[j]), "requested_vocal": int(req[j]),
                                 "common": float(common[j])}) + "\n")
    # per-σ deployed predictions (best-on-val σ-specific model) for the σ-decision frontier sim
    for sk in SIGMAS:
        cands = [m for m in PT if m.endswith(f"s{sk}") and not m.startswith("scalar")]
        best_s = max(cands, key=lambda m: results["models"][m]["val"].get("auc", 0))
        thr_s = results["models"][best_s]["val"].get("thr", 0.5)
        with (P2 / "batch2" / f"evpd_test_pred_s{sk}.jsonl").open("w") as fh:
            for jj, j in enumerate(np.where(te)[0]):
                fh.write(json.dumps({"prompt_id": pid[j], "candidate_index": int(ci[j]), "sigma": sk,
                                     "evpd_model": best_s, "evpd_p": float(PT[best_s][jj]), "evpd_thr": float(thr_s),
                                     "evpd_pred_present": int(PT[best_s][jj] >= thr_s),
                                     "requested_vocal": int(req[j])}) + "\n")
    (P2 / "batch2" / "EVPD_RESULTS.json").write_text(json.dumps(results, indent=2, default=float))
    (P2 / "EVPD_RESULTS.json").write_text(json.dumps(results, indent=2, default=float))
    # markdown summary table
    md = ["# EVPD Results (Batch 2 Stage 3)", "",
          f"Test = held_out ({splitrep['test']['prompts']} prompts / {splitrep['test']['candidates']} cands); "
          f"presence prevalence(test)={results['prevalence_test']}. Threshold tuned on val only.", "",
          "## Held-out presence-prediction metrics", "",
          "| model | AUC | AUPRC | rec@P.8 | prec@R.8 | bal-acc |", "|---|---|---|---|---|---|"]
    for nm, mm in results["models"].items():
        t = mm["test"]
        md.append(f"| {nm} | {t.get('auc')} | {t.get('auprc')} | {t.get('recall_at_prec80')} | "
                  f"{t.get('prec_at_recall80')} | {t.get('balanced_acc')} |")
    md += ["", "## Type-error & survivor-set detection (ADSR-relevant)", "",
           "```json", json.dumps(det, indent=2), "```"]
    (P2 / "EVPD_RESULTS.md").write_text("\n".join(md))
    print(json.dumps({"split": splitrep, "models": {k: v["test"].get("auc") for k, v in results["models"].items()},
                      "detection": det}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
