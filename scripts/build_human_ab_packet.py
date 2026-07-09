#!/usr/bin/env python
"""Build the blinded human A/B spot-check packet from Batch-3 keeps (PREPARE ONLY — PI distributes).

Contrasts (selected outputs, same prompt+rep): arm6-vs-arm1, arm6-vs-arm4, arm6-vs-arm7,
arm6-vs-arm2. Up to ~60 pairs/contrast sampled across strata (tail E2 / C lyric-bearing /
D general). Blinded: A/B order randomized per pair via deterministic hash; key file kept separate.
Outputs: phase3/human_ab/{HUMAN_ADSR_SPOTCHECK_PACKET.md, human_adsr_pairs.jsonl,
         audio_manifest.csv, response_sheet.csv, UNBLINDING_KEY.jsonl (PI-only)}
"""
from __future__ import annotations
import glob, hashlib, json, random
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
B3 = REPO / "orbit-research/adsr_phase2_20260604/batch3"
OUT = REPO / "orbit-research/adsr_phase2_20260604/phase3/human_ab"
CONTRASTS = [(6, 1), (6, 4), (6, 7), (6, 2)]
PER_CONTRAST = 60
rng = random.Random(20260613)


def main():
    sels = {}
    for f in glob.glob(str(B3 / "online_run/ledger_w*.jsonl")):
        for l in open(f):
            d = json.loads(l)
            if d.get("type") == "unit_selection":
                sels[(d["prompt_id"], d["arm"], d["rep"])] = d
    strata = {json.loads(l)["prompt_id"]: json.loads(l)
              for l in open(B3 / "batch3_selected_prompts_256.jsonl")}
    e2 = {json.loads(l)["prompt_id"] for l in open(B3 / "E2_TAIL_SUBGROUP.jsonl")}

    def sel_flac(pid, arm, rep):
        d = sels.get((pid, arm, rep))
        if not d:
            return None
        ks = d.get("keeps", {})
        p = ks.get(d.get("selected", ""), None)
        if p is None and ks:
            p = next(iter(ks.values()))
        if p and "KEEP" not in str(p) and (REPO / str(p).split(" ")[0]).exists():
            return str(p).split(" ")[0]
        return None

    OUT.mkdir(parents=True, exist_ok=True)
    pairs, key = [], []
    for a, b in CONTRASTS:
        cands = []
        for pid in strata:
            for rep in (0, 1):
                fa, fb = sel_flac(pid, a, rep), sel_flac(pid, b, rep)
                if fa and fb and fa != fb:
                    grp = ("tail" if pid in e2 else
                           ("lyric" if strata[pid]["stratum"].startswith("C") else "general"))
                    cands.append((pid, rep, fa, fb, grp))
        # stratified sample: prefer tail + lyric, fill with general
        by_g = defaultdict(list)
        for c in cands:
            by_g[c[4]].append(c)
        for g in by_g:
            rng.shuffle(by_g[g])
        take = (by_g["tail"][:24] + by_g["lyric"][:20] + by_g["general"][:16])[:PER_CONTRAST]
        for pid, rep, fa, fb, grp in take:
            pair_id = hashlib.md5(f"{a}v{b}_{pid}_{rep}".encode()).hexdigest()[:10]
            flip = int(hashlib.md5(pair_id.encode()).hexdigest(), 16) % 2
            A, B = (fb, fa) if flip else (fa, fb)
            pairs.append({"pair_id": pair_id, "group": grp, "A": A, "B": B,
                          "prompt_text_for_rater": True})
            key.append({"pair_id": pair_id, "contrast": f"arm{a}_vs_arm{b}",
                        "prompt_id": pid, "rep": rep,
                        "A_is": f"arm{b}" if flip else f"arm{a}",
                        "B_is": f"arm{a}" if flip else f"arm{b}"})
    with (OUT / "human_adsr_pairs.jsonl").open("w") as fh:
        for p in pairs:
            fh.write(json.dumps(p) + "\n")
    with (OUT / "UNBLINDING_KEY.jsonl").open("w") as fh:
        for k in key:
            fh.write(json.dumps(k) + "\n")
    with (OUT / "audio_manifest.csv").open("w") as fh:
        fh.write("pair_id,slot,path\n")
        for p in pairs:
            fh.write(f"{p['pair_id']},A,{p['A']}\n{p['pair_id']},B,{p['B']}\n")
    with (OUT / "response_sheet.csv").open("w") as fh:
        fh.write("pair_id,rater_initials,overall_preference(A/B/tie),musicality(A/B/tie),"
                 "prompt_fit(A/B/tie),vocal_type_correct(A/B/tie),"
                 "lyric_intelligibility(A/B/tie/NA),vocal_artifacts(A/B/tie),comment\n")
        for p in pairs:
            fh.write(f"{p['pair_id']},,,,,,,\n")
    (OUT / "HUMAN_ADSR_SPOTCHECK_PACKET.md").write_text(
        f"# Blinded A/B spot-check packet ({len(pairs)} pairs)\n\n"
        "**PI distributes to the 3 raters; do NOT run as crowdsourcing.** Each pair: two clips\n"
        "(A/B, FLAC paths in audio_manifest.csv, relative to repo root) generated for the SAME\n"
        "prompt. Listen to both (headphones), then answer the rubric per pair on the response\n"
        "sheet: overall preference, musicality, prompt fit, vocal-type correctness (does the\n"
        "presence/absence of vocals match the prompt?), lyric intelligibility (NA for\n"
        "instrumental), vocal artifacts. A/B order is randomized per pair; raters must not\n"
        "discuss. 3 raters per pair; report agreement.\n\n"
        f"Groups: tail-rescue cases, lyric-bearing, general sanity. Contrasts (blinded): "
        f"{len(CONTRASTS)} policy comparisons x ~{PER_CONTRAST} pairs.\n\n"
        "UNBLINDING_KEY.jsonl maps pairs to arms — PI ONLY; keep away from raters.\n")
    from collections import Counter
    print(json.dumps({"pairs": len(pairs),
                      "by_contrast": dict(Counter(k["contrast"] for k in key)),
                      "by_group": dict(Counter(p["group"] for p in pairs))}, indent=2))


if __name__ == "__main__":
    main()
