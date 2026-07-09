#!/usr/bin/env python
"""Phase-3 T2I transfer — build the ~500-prompt presence/absence constraint set.

Music→T2I analogy: ABSENCE prompts ("..., no people") = instrumental/vocal-leakage analog
(negation violations are the known failure mode); PRESENCE prompts ("... with a red umbrella")
= vocal/vocal-miss analog. Constraint objects restricted to classes OWLv2 detects reliably.
Deterministic construction (seeded), 250 presence + 250 absence, scene-diverse.
Output: orbit-research/adsr_phase2_20260604/t2i/t2i_prompts.jsonl
"""
from __future__ import annotations
import json, random
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "orbit-research/adsr_phase2_20260604/t2i"
rng = random.Random(20260612)

SCENES = [
    "a busy city street at dusk", "a quiet mountain lake at sunrise", "a cozy living room",
    "a sandy beach with gentle waves", "a snow-covered village square", "a sunlit forest clearing",
    "a rustic farmhouse kitchen", "a modern office lobby", "a colorful flower garden",
    "a rainy downtown intersection", "an old European alleyway", "a desert highway at noon",
    "a crowded farmers market", "a misty harbor at dawn", "a suburban backyard in summer",
    "a grand library reading hall", "a neon-lit night market", "a country road in autumn",
    "a rooftop terrace at sunset", "a train station platform", "a botanical greenhouse",
    "a lakeside camping site", "a medieval castle courtyard", "a minimalist art gallery",
    "an industrial warehouse interior",
]
OBJECTS = ["dog", "cat", "person", "car", "bicycle", "umbrella", "balloon", "bird",
           "horse", "boat", "bench", "traffic light", "backpack", "kite", "pizza",
           "potted plant", "clock", "teddy bear", "motorcycle", "bus"]
STYLES = ["photorealistic, high detail", "cinematic lighting, 35mm photo",
          "soft natural light, documentary photo", "golden hour photography, sharp focus"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    i = 0
    while len(rows) < 500:
        scene = rng.choice(SCENES); obj = rng.choice(OBJECTS); style = rng.choice(STYLES)
        kind = "presence" if len(rows) % 2 == 0 else "absence"
        if kind == "presence":
            text = f"{scene}, with a {obj} clearly visible, {style}"
        else:
            text = f"{scene}, with absolutely no {obj} anywhere, {style}"
        key = (scene, obj, kind)
        if any(r["_key"] == list(key) for r in rows):
            continue
        rows.append({"prompt_id": f"t2i_{len(rows):04d}", "text": text, "constraint_kind": kind,
                     "constraint_object": obj, "scene": scene, "style": style,
                     "_key": list(key)})
        i += 1
    # deterministic prompt-level split, INDEPENDENT of constraint_kind (kind alternates with j%2,
    # so split must NOT — earlier j%2 split confounded kind⊗split; fixed to pair-level alternation:
    # each (presence, absence) pair lands in the same split, pairs alternate dev/held_out).
    for j, r in enumerate(rows):
        r["split"] = "dev" if (j // 2) % 2 == 0 else "held_out"
        del r["_key"]
    with (OUT / "t2i_prompts.jsonl").open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    from collections import Counter
    print(json.dumps({"n": len(rows),
                      "kinds": dict(Counter(r["constraint_kind"] for r in rows)),
                      "splits": dict(Counter(r["split"] for r in rows)),
                      "objects": len(set(r["constraint_object"] for r in rows))}, indent=2))


if __name__ == "__main__":
    main()
