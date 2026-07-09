#!/usr/bin/env python
"""Score an arbitrary list of audio files with the PANNs vocal-presence probe.

Same vocal-class max-score convention as scripts/phase0_panns_detector.py
(P0.6c), but takes a CSV manifest (column: clip_path, repo-relative or
absolute) instead of the 4,096-spine layout.

Usage: python panns_score_files.py IN.csv OUT.jsonl [--device cuda]
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path("/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion")
VOCAL_CLASSES = ["Singing", "Speech", "Male singing", "Female singing", "Child singing",
                 "Choir", "Rapping", "Human voice", "Vocal music", "A capella"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("out")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--path-col", default="clip_path")
    args = ap.parse_args()

    import librosa
    from panns_inference import AudioTagging
    from panns_inference.config import labels as panns_labels
    idx = [i for i, l in enumerate(panns_labels) if l in VOCAL_CLASSES]
    at = AudioTagging(checkpoint_path=None, device=args.device)

    rows = list(csv.DictReader(open(args.manifest)))
    done = set()
    out = Path(args.out)
    if out.exists():
        for l in open(out):
            try:
                done.add(json.loads(l)["clip_path"])
            except Exception:
                pass
    t0 = time.time()
    with out.open("a") as fh:
        for i, r in enumerate(rows):
            p = r[args.path_col]
            if p in done:
                continue
            full = Path(p) if p.startswith("/") else REPO / p
            try:
                y, _ = librosa.load(str(full), sr=32000, mono=True)
                clip, _ = at.inference(y[None, :])
                pr = clip[0]
                rec = {"clip_path": p,
                       "panns_vocal_score": round(float(np.max(pr[idx])), 5),
                       "top_vocal_class": panns_labels[idx[int(np.argmax(pr[idx]))]]}
            except Exception as e:
                rec = {"clip_path": p, "error": f"{type(e).__name__}: {e}"}
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            print(f"{i+1}/{len(rows)} {time.time()-t0:.0f}s", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
