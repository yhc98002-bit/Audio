#!/usr/bin/env python
"""Strict QA gate for the ADSR downstream labeling/mel step on the COMPLETE 4096 merged dataset.

Verifies the PI's acceptance criteria and emits a machine + human report. Exits nonzero if any
HARD criterion fails (so it can gate Phase-2A EVPD). Read-only except writing the report files.

HARD criteria:
  1. all audio paths resolved (every record's final + early0.9/0.8/0.7 wav exists)
  2. no missing wav (merged symlink tree: 512 prompts x (8 final + 24 early))
  3. no duplicate prompt_id x candidate_index (records AND labels)
  4. final vocal-presence labels present (4096 ok labels; coverage 512x8)
  5. early-sigma mel present where required (3 mels/candidate; 12288; all files exist)
  6. lyric-bearing / vocal_scorable subset preserved (EN-vocal n matches canonical; 0 strata drift)
  7. instrumental 1.0 sentinel NOT pooled into a lyric headline (sentinel present on 100% of
     instrumental; lyric headline scoped to vocal_scorable; demonstrate pooled-vs-scoped gap)
Plus report metrics: coverage, failures, ambiguous, GPU-h, Phase-2A readiness.
"""
from __future__ import annotations
import json, glob, os, statistics, sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MERGED = REPO / "runs/adsr_recollect_20260604_full01_merged"
RAW = REPO / "orbit-research/adsr_phase2_20260604/vocal_presence_raw.jsonl"
MELDIR = REPO / "orbit-research/adsr_phase2_20260604/mel"
CANON = REPO / "orbit-research/trajectory_candidate_dataset.jsonl"
SNAP = REPO / "orbit-research/adsr_phase2_20260604/snapshots/snapshot_final.json"
OUT_JSON = REPO / "orbit-research/adsr_phase2_20260604/DOWNSTREAM_QA_REPORT.json"
OUT_MD = REPO / "orbit-research/adsr_phase2_20260604/DOWNSTREAM_QA_REPORT.md"
BON_N = 8
EARLY = ["0.9", "0.8", "0.7"]
AMBIG_MARGIN = 0.05  # |vocal_energy_ratio - threshold| < margin => ambiguous presence call


def resolve(p):
    if not p:
        return None
    p = Path(p)
    return p if p.is_absolute() else (REPO / p)


def main() -> int:
    recs = []
    for f in sorted(glob.glob(str(MERGED / "shard0*" / "candidate_records.jsonl"))):
        for l in open(f):
            l = l.strip()
            if l:
                recs.append(json.loads(l))
    labels = [json.loads(l) for l in open(RAW)] if RAW.exists() else []
    ok = [r for r in labels if r.get("ok")]
    snap = json.loads(SNAP.read_text()) if SNAP.exists() else {}
    checks = {}

    # 1 + 2: audio paths resolved / no missing wav
    miss_paths = 0
    for r in recs:
        for k in ("audio_path", "early_0.9_audio_path", "early_0.8_audio_path", "early_0.7_audio_path"):
            sp = resolve(r.get(k))
            if sp is None or not sp.exists():
                miss_paths += 1
    midx = {r["prompt_id"]: int(r["manifest_index"]) for r in recs}
    fs_bad = 0
    for pid in set(midx):
        d = MERGED / f"shard{midx[pid]//64:02d}" / "audio" / pid
        fin = [p for p in d.glob("candidate_*_seed*.wav") if "_early" not in p.name] if d.is_dir() else []
        ear = list(d.glob("candidate_*_seed*_early*.wav")) if d.is_dir() else []
        broken = [p for p in fin + ear if not p.resolve().exists()]
        if len(fin) != BON_N or len(ear) != BON_N * 3 or broken:
            fs_bad += 1
    checks["1_audio_paths_resolved"] = {"records_with_missing_wav": miss_paths, "pass": miss_paths == 0}
    checks["2_no_missing_wav_symlinks"] = {"prompts_bad_8final_24early": fs_bad, "pass": fs_bad == 0}

    # 3: no duplicates AND label set EXACTLY equals record set (Codex hardening: forbid extra/failed
    #    labels and any drift between records and labels)
    rec_keys = [(r["prompt_id"], r["candidate_index"]) for r in recs]
    lab_keys = [(r.get("prompt_id"), r.get("candidate_index")) for r in labels]
    rec_set, lab_set = set(rec_keys), set(lab_keys)
    checks["3_no_duplicate_pid_cand"] = {
        "records": len(rec_keys), "records_distinct": len(rec_set),
        "labels_total": len(labels), "labels_distinct": len(lab_set),
        "label_set_equals_record_set": rec_set == lab_set,
        "pass": (len(rec_keys) == len(rec_set) == BON_N * 512
                 and len(labels) == len(lab_set) == BON_N * 512 and rec_set == lab_set)}

    # 4: final vocal-presence labels present — every prompt has EXACTLY candidates {0..7}, all ok w/ ratio
    ok_keys = {(r["prompt_id"], r["candidate_index"]) for r in ok}
    per_prompt_ci = defaultdict(set)
    for r in ok:
        per_prompt_ci[r["prompt_id"]].add(r["candidate_index"])
    prompts_full = sum(1 for p in per_prompt_ci if per_prompt_ci[p] == set(range(BON_N)))
    has_ratio = sum(1 for r in ok if isinstance(r.get("vocal_energy_ratio"), (int, float)))
    checks["4_vocal_presence_labels"] = {
        "ok_labels": len(ok), "expected": BON_N * 512, "with_vocal_ratio": has_ratio,
        "prompts_with_exact_0to7": prompts_full, "missing_labels": len(rec_set - ok_keys),
        "pass": (len(ok) == BON_N * 512 and ok_keys == rec_set and has_ratio == len(ok)
                 and prompts_full == 512)}

    # 5: early-sigma mel present — exactly 4096x3 DISTINCT referenced paths, each = expected name & exists
    expected_mel = set()
    ref_mel, bad_keys, miss_files, bad_name = set(), 0, 0, 0
    for r in ok:
        pid, ci = r["prompt_id"], r["candidate_index"]
        mp = r.get("mel_paths", {})
        if set(mp.keys()) != set(EARLY):
            bad_keys += 1
        for sk in EARLY:
            expected_mel.add(f"{pid}__cand{ci:02d}__early{sk}.npy")
        for sk, p in mp.items():
            rp = resolve(p)
            ref_mel.add(str(p))
            if rp is None or not rp.exists():
                miss_files += 1
            if Path(p).name != f"{pid}__cand{ci:02d}__early{sk}.npy":
                bad_name += 1
    mel_n = len(list(MELDIR.glob("*.npy")))
    referenced_names = {Path(p).name for p in ref_mel}
    checks["5_early_sigma_mel"] = {
        "mel_npy_files": mel_n, "expected": BON_N * 512 * 3,
        "distinct_referenced_paths": len(ref_mel), "labels_missing_sigma_key": bad_keys,
        "mel_files_referenced_missing": miss_files, "basename_mismatch": bad_name,
        "referenced_names_eq_expected": referenced_names == expected_mel,
        "pass": (mel_n == BON_N * 512 * 3 and len(ref_mel) == BON_N * 512 * 3 and bad_keys == 0
                 and miss_files == 0 and bad_name == 0 and referenced_names == expected_mel)}

    # 6: vocal_scorable preserved — EXACT (pid,ci) set == canonical, per-candidate strata match, prompt-set match
    canon = {}
    for l in open(CANON):
        d = json.loads(l)
        canon[(d["prompt_id"], d.get("candidate_index"))] = (d.get("vocal_stratum"), d.get("language"))
    canon_keys = set(canon)
    canon_prompts = {k[0] for k in canon_keys}
    rec_strata = {(r["prompt_id"], r["candidate_index"]): (r.get("vocal_stratum"), r.get("language")) for r in recs}
    per_cand_drift = sum(1 for k, v in rec_strata.items() if k in canon and canon[k] != v)
    pmeta = {}
    for r in recs:
        pmeta[r["prompt_id"]] = (r.get("vocal_stratum"), r.get("language"), r.get("has_lyrics"))
    en_vocal = [p for p, (vs, lang, hl) in pmeta.items() if vs == "vocal" and lang == "en"]
    non_en_vocal = [p for p, (vs, lang, hl) in pmeta.items() if vs == "vocal" and lang != "en"]
    hl_consistent = all((hl is True) == (vs == "vocal") for (vs, lang, hl) in pmeta.values())
    checks["6_vocal_scorable_preserved"] = {
        "prompts": len(pmeta), "vocal": sum(1 for v in pmeta.values() if v[0] == "vocal"),
        "instrumental": sum(1 for v in pmeta.values() if v[0] == "instrumental"),
        "en_vocal_scorable": len(en_vocal), "expected_en_vocal": 282,
        "non_en_vocal_floored_excluded": len(non_en_vocal),
        "rec_keys_eq_canonical_keys": rec_set == canon_keys,
        "prompt_set_eq_canonical": set(pmeta) == canon_prompts,
        "per_candidate_strata_drift": per_cand_drift, "has_lyrics_consistent": hl_consistent,
        "pass": (len(en_vocal) == 282 and rec_set == canon_keys and set(pmeta) == canon_prompts
                 and per_cand_drift == 0 and hl_consistent)}

    # 7: instrumental 1.0 sentinel present on ALL instrumental AND lyric headline strictly scoped to
    #    vocal_scorable (EN-vocal): exact scoped set == EN-vocal candidates, NO instrumental/non-EN leak
    enset = set(en_vocal)
    instr_prompts = {p for p, (vs, lang, hl) in pmeta.items() if vs == "instrumental"}
    instr_li = [r.get("final_lyric_intelligibility") for r in recs if r.get("vocal_stratum") == "instrumental"]
    instr_sentinel = sum(1 for x in instr_li if x == 1.0)
    scoped_keys = {(r["prompt_id"], r["candidate_index"]) for r in recs if r["prompt_id"] in enset}
    scoped = [r.get("final_lyric_intelligibility") for r in recs
              if r["prompt_id"] in enset and isinstance(r.get("final_lyric_intelligibility"), (int, float))]
    pooled = [r.get("final_lyric_intelligibility") for r in recs
              if isinstance(r.get("final_lyric_intelligibility"), (int, float))]
    leak_instr = any(k[0] in instr_prompts for k in scoped_keys)
    leak_nonen = any(k[0] in set(non_en_vocal) for k in scoped_keys)
    checks["7_lyric_sentinel_masked"] = {
        "instrumental_candidates": len(instr_li), "sentinel_eq_1.0": instr_sentinel,
        "sentinel_frac": round(instr_sentinel / len(instr_li), 4) if instr_li else None,
        "scoped_n": len(scoped), "expected_scoped_n": 282 * BON_N,
        "scoped_has_instrumental_leak": leak_instr, "scoped_has_nonEN_leak": leak_nonen,
        "lyric_headline_scoped_vocal_scorable_mean": round(statistics.mean(scoped), 4) if scoped else None,
        "naive_pooled_mean_CONTAMINATED_do_not_use": round(statistics.mean(pooled), 4) if pooled else None,
        "note": "headline scoped to vocal_scorable (EN-vocal); pooled value is inflated by the 1.0 instrumental sentinel. Canonical Track-A ETP@50% lyric headline = 0.682 (EN-vocal n=282).",
        "pass": (bool(instr_li) and instr_sentinel == len(instr_li)
                 and len(scoped) == 282 * BON_N and not leak_instr and not leak_nonen)}

    # ---- report metrics ----
    failures = len(labels) - len(ok)
    thr = snap.get("threshold")
    ambiguous = None
    if thr is not None:
        ambiguous = sum(1 for r in ok if abs(r.get("vocal_energy_ratio", -9) - thr) < AMBIG_MARGIN)
    near_silent = sum(1 for r in ok if r.get("near_silent"))
    all_pass = all(c["pass"] for c in checks.values())
    metrics = {
        "label_coverage_prompts": f"{len(set(p for p, c in Counter(r['prompt_id'] for r in ok).items() if c == BON_N))}/512",
        "label_coverage_frac": round(len(ok) / (BON_N * 512), 4),
        "candidates_labeled": len(ok),
        "failure_count": failures,
        "ambiguous_count": ambiguous, "ambiguous_def": f"|vocal_energy_ratio - threshold({thr})| < {AMBIG_MARGIN}",
        "near_silent_count": near_silent,
        "gpu_hours_used": 0.0, "compute_note": "labeling is CPU-only (Demucs htdemucs forced device=cpu); ~0 GPU-h",
        "type_error_prevalence_candidate": snap.get("candidate_type_error_prevalence"),
        "type_error_per_stratum": snap.get("per_requested_stratum"),
        "early_sigma_scalar_AUC_heldout": snap.get("early_sigma_vocal_presence_AUC_heldout"),
        "phase2a_ready": bool(all_pass),
        "phase2a_gate": "EVPD training is PI-gated (CLAUDE.md hard boundary) — DO NOT launch without explicit approval.",
    }

    report = {"all_hard_checks_pass": all_pass, "hard_checks": checks, "report_metrics": metrics}
    OUT_JSON.write_text(json.dumps(report, indent=2))
    # markdown
    md = ["# ADSR Downstream Labeling/Mel — Strict QA Report", "",
          f"**ALL HARD CHECKS PASS: {all_pass}**", "", "## Hard criteria"]
    for k, v in checks.items():
        md.append(f"- {'✅' if v['pass'] else '❌'} **{k}** — {json.dumps({kk: vv for kk, vv in v.items() if kk != 'pass'})}")
    md += ["", "## Report metrics"]
    for k, v in metrics.items():
        md.append(f"- **{k}**: {v}")
    OUT_MD.write_text("\n".join(md))
    print(json.dumps(report, indent=2))
    print(f"\nwrote {OUT_JSON.name} + {OUT_MD.name}  | ALL_PASS={all_pass}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
