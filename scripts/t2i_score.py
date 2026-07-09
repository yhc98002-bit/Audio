#!/usr/bin/env python
"""Phase-3 T2I — score generated images: OWLv2 constraint detection (final + step previews)
+ PickScore reward (final). Emits per-candidate records mirroring the music schema:
  violation (final), probe detector confidence per capture step, reward.
Presence prompt: violation = object NOT detected on final. Absence: violation = object detected.
Detector decision threshold is calibrated later on the dev split only (records store raw scores).

Env: t2i-adsr. Sharded; resumable. Output: t2i/records_w{K}.jsonl
"""
from __future__ import annotations
import argparse, json, time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
T2I = REPO / "orbit-research/adsr_phase2_20260604/t2i"
CAPTURE_STEPS = [6, 10, 14, 16, 20]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker-index", type=int, default=0)
    ap.add_argument("--num-workers", type=int, default=1)
    args = ap.parse_args()
    import torch
    from PIL import Image
    from transformers import Owlv2Processor, Owlv2ForObjectDetection, AutoProcessor, AutoModel
    dev = "cuda"
    oproc = Owlv2Processor.from_pretrained("google/owlv2-base-patch16-ensemble")
    omod = Owlv2ForObjectDetection.from_pretrained("google/owlv2-base-patch16-ensemble").to(dev).eval()
    pproc = AutoProcessor.from_pretrained("laion/CLIP-ViT-H-14-laion2B-s32B-b79K")
    pmod = AutoModel.from_pretrained("yuvalkirstain/PickScore_v1").to(dev).eval()

    def detect(img, obj):
        with torch.no_grad():
            inp = oproc(text=[[f"a photo of a {obj}"]], images=img, return_tensors="pt").to(dev)
            out = omod(**inp)
            res = oproc.post_process_object_detection(
                out, threshold=0.0, target_sizes=torch.tensor([img.size[::-1]]).to(dev))[0]
        return float(res["scores"].max()) if len(res["scores"]) else 0.0

    def pickscore(img, text):
        with torch.no_grad():
            ii = pproc(images=img, return_tensors="pt").to(dev)
            ti = pproc(text=text, padding=True, truncation=True, max_length=77,
                       return_tensors="pt").to(dev)
            ie = pmod.get_image_features(**ii); ie = ie / ie.norm(dim=-1, keepdim=True)
            te = pmod.get_text_features(**ti); te = te / te.norm(dim=-1, keepdim=True)
            return float((te @ ie.T)[0, 0] * pmod.logit_scale.exp())

    prompts = [json.loads(l) for l in open(T2I / "t2i_prompts.jsonl")]
    mine = prompts[args.worker_index::args.num_workers]
    out_f = T2I / f"records_w{args.worker_index}.jsonl"
    done = set()
    if out_f.exists():
        for l in open(out_f):
            try:
                d = json.loads(l); done.add((d["prompt_id"], d["cand"]))
            except Exception:
                pass
    fh = out_f.open("a"); n = 0; t0 = time.time()
    for row in mine:
        pid, obj = row["prompt_id"], row["constraint_object"]
        pdir = T2I / "images" / pid
        for k in range(8):
            if (pid, k) in done:
                continue
            fimg = pdir / f"cand{k}_final.jpg"
            if not fimg.exists():
                continue
            img = Image.open(fimg).convert("RGB")
            det_final = detect(img, obj)
            probes = {}
            for s in CAPTURE_STEPS:
                p = pdir / f"cand{k}_step{s:02d}.jpg"
                if p.exists():
                    probes[str(s)] = round(detect(Image.open(p).convert("RGB"), obj), 5)
            fh.write(json.dumps({"prompt_id": pid, "cand": k, "split": row["split"],
                                 "constraint_kind": row["constraint_kind"],
                                 "constraint_object": obj,
                                 "det_final": round(det_final, 5),
                                 "det_probe": probes,
                                 "pickscore": round(pickscore(img, row["text"]), 4)}) + "\n")
            fh.flush(); n += 1
            if n % 50 == 0:
                print(f"w{args.worker_index}: {n} scored ({n/max(time.time()-t0,1)*60:.0f}/min)",
                      flush=True)
    fh.close()
    print(f"T2I_SCORE_DONE w{args.worker_index} n={n}", flush=True)


if __name__ == "__main__":
    main()
