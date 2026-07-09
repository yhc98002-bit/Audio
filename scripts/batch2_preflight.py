#!/usr/bin/env python
"""Batch 2 Stage 0 — pre-flight verification on the COMPLETE 4096 merged + labeled dataset.

Re-verifies the 8 hard pre-flight checks from the Batch-2 spec and emits
BATCH2_PREFLIGHT_CHECK.{md,json}. Exits nonzero (P0) if any hard check fails.
"""
from __future__ import annotations
import json, glob, sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MERGED = REPO / "runs/adsr_recollect_20260604_full01_merged"
RAW = REPO / "orbit-research/adsr_phase2_20260604/vocal_presence_raw.jsonl"
MELDIR = REPO / "orbit-research/adsr_phase2_20260604/mel"
CANON = REPO / "orbit-research/trajectory_candidate_dataset.jsonl"
P2 = REPO / "orbit-research/adsr_phase2_20260604"
EARLY = ["0.9", "0.8", "0.7"]
BON = 8


def main() -> int:
    recs = []
    for f in sorted(glob.glob(str(MERGED / "shard0*" / "candidate_records.jsonl"))):
        recs.extend(json.loads(l) for l in open(f) if l.strip())
    labels = [json.loads(l) for l in open(RAW)] if RAW.exists() else []
    ok = [r for r in labels if r.get("ok")]
    canon = {(json.loads(l)["prompt_id"], json.loads(l).get("candidate_index")) for l in open(CANON)}
    canon_meta = {}
    for l in open(CANON):
        d = json.loads(l)
        canon_meta[d["prompt_id"]] = (d.get("vocal_stratum"), d.get("language"), d.get("split"))

    rec_keys = [(r["prompt_id"], r["candidate_index"]) for r in recs]
    rec_set = set(rec_keys)
    prompts = {r["prompt_id"] for r in recs}
    ok_keys = {(r["prompt_id"], r["candidate_index"]) for r in ok}
    pmeta = {r["prompt_id"]: (r.get("vocal_stratum"), r.get("language"), r.get("split"), r.get("has_lyrics")) for r in recs}

    # mel presence per (pid,ci,sigma)
    mel_ref = set()
    mel_bad_key = 0
    for r in ok:
        mp = r.get("mel_paths", {})
        if set(mp.keys()) != set(EARLY):
            mel_bad_key += 1
        for sk, p in mp.items():
            mel_ref.add((r["prompt_id"], r["candidate_index"], sk, (REPO / p).exists()))
    mel_present = sum(1 for (_, _, _, ex) in mel_ref if ex)
    mel_files = len(list(MELDIR.glob("*.npy")))

    en_vocal = {p for p, (vs, lang, sp, hl) in pmeta.items() if vs == "vocal" and lang == "en"}
    non_en_vocal = {p for p, (vs, lang, sp, hl) in pmeta.items() if vs == "vocal" and lang != "en"}
    instr = {p for p, (vs, lang, sp, hl) in pmeta.items() if vs == "instrumental"}
    instr_li = [r.get("final_lyric_intelligibility") for r in recs if r.get("vocal_stratum") == "instrumental"]
    splits = Counter(v[2] for v in pmeta.values())
    # split per-prompt consistency: each prompt's 8 candidates share one split
    split_by_prompt = defaultdict(set)
    for r in recs:
        split_by_prompt[r["prompt_id"]].add(r.get("split"))
    split_consistent = all(len(s) == 1 for s in split_by_prompt.values())

    checks = {
        "1_4096_distinct_records": {"records": len(rec_keys), "distinct": len(rec_set),
                                    "pass": len(rec_keys) == len(rec_set) == BON * 512},
        "2_512_prompts": {"prompts": len(prompts), "pass": len(prompts) == 512},
        "3_final_vocal_labels_all_4096": {"ok_labels": len(ok), "cover_records": ok_keys == rec_set,
                                          "pass": len(ok) == BON * 512 and ok_keys == rec_set},
        "4_early_mels_present": {"mel_npy_files": mel_files, "distinct_pid_ci_sigma_present": mel_present,
                                 "expected": BON * 512 * 3, "labels_missing_sigma_key": mel_bad_key,
                                 "pass": mel_files == BON * 512 * 3 and mel_present == BON * 512 * 3 and mel_bad_key == 0},
        "5_vocal_scorable_en_vocal_282": {"en_vocal": len(en_vocal), "expected": 282,
                                          "keys_eq_canonical": rec_set == canon,
                                          "pass": len(en_vocal) == 282 and rec_set == canon},
        "6_instrumental_sentinel_maskable": {"instrumental_prompts": len(instr),
                                             "instr_candidates": len(instr_li),
                                             "all_sentinel_1.0": all(x == 1.0 for x in instr_li),
                                             "pass": len(instr_li) > 0 and all(x == 1.0 for x in instr_li)},
        "7_non_en_vocal_excluded_identifiable": {"non_en_vocal_prompts": len(non_en_vocal), "expected": 34,
                                                 "pass": len(non_en_vocal) == 34},
        "8_prompt_level_split_preserved": {"splits": dict(splits), "split_consistent_within_prompt": split_consistent,
                                           "pass": split_consistent and set(splits) == {"dev", "held_out"} and splits["dev"] == 256 and splits["held_out"] == 256},
    }
    all_pass = all(c["pass"] for c in checks.values())
    report = {"all_preflight_pass": all_pass, "checks": checks,
              "dataset": {"merged_run": MERGED.name, "raw_labels": str(RAW.relative_to(REPO)),
                          "meldir": str(MELDIR.relative_to(REPO)), "canonical": str(CANON.relative_to(REPO))}}
    (P2 / "BATCH2_PREFLIGHT_CHECK.json").write_text(json.dumps(report, indent=2))
    md = ["# Batch 2 — Stage 0 Pre-flight Verification", "",
          f"**ALL PRE-FLIGHT CHECKS PASS: {all_pass}**", "",
          f"Dataset: `{MERGED.name}` + `{RAW.relative_to(REPO)}` + `{MELDIR.relative_to(REPO)}`", "",
          "| # | Check | Pass | Detail |", "|---|---|---|---|"]
    for k, v in checks.items():
        md.append(f"| {k.split('_')[0]} | {k} | {'✅' if v['pass'] else '❌'} | "
                  f"{json.dumps({kk: vv for kk, vv in v.items() if kk != 'pass'})} |")
    (P2 / "BATCH2_PREFLIGHT_CHECK.md").write_text("\n".join(md))
    print(json.dumps(report, indent=2))
    print(f"\nALL_PREFLIGHT_PASS={all_pass}  -> {P2.name}/BATCH2_PREFLIGHT_CHECK.{{md,json}}")
    return 0 if all_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
