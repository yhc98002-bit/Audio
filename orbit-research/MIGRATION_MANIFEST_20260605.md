# Migration manifest — ADSR resume to a DIFFERENT machine (no shared filesystem)

Confirmed 2026-06-05: target GPU node does **not** mount the Paratera `/HOME` or `/XYFS02`
filesystems. So the two folders alone are insufficient — the conda env, ~14 G of model
weight caches, and the `.claude` session all live on `/HOME` outside them.

## Fact: your two folders are one physical tree + source
`/HOME/paratera_xy/pxy1289/HDD_POOL` → symlink → `/XYFS02/HDD_POOL/paratera_xy/pxy1289/`.
So project (`…/AudioDiffusion`) and `…/source` both live under `/XYFS02/HDD_POOL/paratera_xy/pxy1289/`.

## What to copy (group A = the tree you named; group B = home-FS deps you MISSED)

| # | Source (absolute) | Size | Needed for |
|---|---|---|---|
| A1 | `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion` **minus `runs/`** | ~5 G | code, configs, orbit-research (incl. 2.4 G EVPD mels), docs |
| A2 | `…/AudioDiffusion/runs/adsr_recollect_20260604_full01/shard0*/candidate_records.jsonl` + `run_summary.json` | 14 M | the checkpoint records (REQUIRED) |
| A3 | `…/AudioDiffusion/runs/adsr_recollect_20260604_full01/shard0*/audio` | 105 G | generated audio — **OPTIONAL** for resume (206 done prompts already labeled+mel'd); needed only for Phase-5 human spot-check / re-deriving from audio |
| A4 | `/XYFS02/HDD_POOL/paratera_xy/pxy1289/source` | 1.7 G | ace_step + reward-model code/weights (audiobox, MERT, clap tokenizers) |
| B1 | `/HOME/paratera_xy/pxy1289/.conda/envs/audio-prm` | 8.5 G | runtime (torch 2.5.1+cu121, demucs). **See env caveat below** |
| B2 | `/HOME/paratera_xy/pxy1289/.cache/modelscope` | 7.8 G | ACE-Step v1 3.5B generator weights |
| B3 | `/HOME/paratera_xy/pxy1289/.cache/whisper` | 2.9 G | Whisper large-v3 (lyric reward) |
| B4 | `/HOME/paratera_xy/pxy1289/.cache/clap` | 1.8 G | CLAP reward |
| B5 | `/HOME/paratera_xy/pxy1289/.cache/huggingface` | 1.6 G | tokenizers/models |
| B6 | `/HOME/paratera_xy/pxy1289/.cache/torch` | 104 M | **Demucs htdemucs** (vocal-presence labeling) |
| B7 | `/HOME/paratera_xy/pxy1289/.claude/projects/-XYFS02-HDD-POOL-paratera-xy-pxy1289-HaocunYe-Research-AudioDiffusion` + `~/.claude/plans/splendid-swimming-pebble.md` + `~/.claude/projects/…/memory/` | 60 M | `claude --resume` + runbook + memory |

**NOT needed for the resume:** `runs/{r0_base,r1_cfg_sweep,r2_bon,r3_robust_bon,r4_bon_cfg,r9_s7_sampler_control,phase_c1_…}` (~238 G of older campaigns). Copy only if the broader paper needs them.

- **Minimum viable (skip A3 audio): ~30 G.**  **Full (with current audio): ~135 G.**

## Path preservation (MANDATORY — many refs are absolute)
Recreate identical absolute paths on the new machine, OR the build breaks:
- Project at `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion`, source at
  `/XYFS02/HDD_POOL/paratera_xy/pxy1289/source` (editable installs `__editable__.mprm.pth` /
  `__editable__.ace_step.pth` encode these).
- Recreate the symlink `/HOME/paratera_xy/pxy1289/HDD_POOL -> /XYFS02/HDD_POOL/paratera_xy/pxy1289/`
  (configs reference `…/HDD_POOL/source/{audiobox_aesthetics,laion_clap_tokenizers,mert}`).
- Caches at `/HOME/paratera_xy/pxy1289/.cache/{modelscope,whisper,clap,huggingface,torch}`
  (config model paths are absolute: `~/.cache/whisper/large-v3.pt`, `~/.cache/clap/630k-audioset-best.pt`,
  `~/.cache/torch/hub/checkpoints/955717e8-8726e21a.th`).
- For `claude --resume` to match: same project path + the `-XYFS02-HDD-POOL-…` transcript dir under `~/.claude/projects/`.
- If the new machine has a different username/home, all `/HOME/paratera_xy/pxy1289/...` paths differ →
  you must either symlink them into place or fix the abs paths in the env `.pth` + configs.

## Env caveat (do not assume the copied env just works)
- A copied conda env often breaks across machines (shebang/.pth abs paths, .so linkage). Try the
  copy first; if `python -c "import torch,mprm,acestep"` fails, **rebuild** the env per CLAUDE.md
  "Environment" (then re-`pip install -e` for `source/ACE-Step` and the project).
- **GPU arch:** env is `torch 2.5.1+cu121` (max sm_90). This supports **4090 (sm_89)** but
  **NOT the RTX PRO 6000 Blackwell (sm_120)** — Blackwell needs torch ≥2.7 / CUDA ≥12.8, i.e. a
  new env. → practical choice is the 8×4090; using Blackwell means rebuilding the stack.

## Suggested transfer (adjust host; rsync preserves symlinks with -a)
```
DST=user@gpunode:/XYFS02/HDD_POOL/paratera_xy/pxy1289     # mirror the same abs path
rsync -aP --exclude 'runs/' /XYFS02/.../AudioDiffusion  $DST/HaocunYe/Research/
rsync -aP /XYFS02/.../source  $DST/
# records only (skip 105G audio unless you need A3):
rsync -aP --include '*/' --include 'candidate_records.jsonl' --include 'run_summary.json' \
      --exclude '*' /XYFS02/.../AudioDiffusion/runs/adsr_recollect_20260604_full01  $DST/HaocunYe/Research/AudioDiffusion/runs/
# home-FS deps:
HDST=user@gpunode:/HOME/paratera_xy/pxy1289
rsync -aP ~/.conda/envs/audio-prm  $HDST/.conda/envs/
rsync -aP ~/.cache/{modelscope,whisper,clap,huggingface,torch}  $HDST/.cache/
rsync -aP ~/.claude  $HDST/
# on the new node: recreate the symlink
ln -s /XYFS02/HDD_POOL/paratera_xy/pxy1289 /HOME/paratera_xy/pxy1289/HDD_POOL
```

## Post-migration smoke (before any GPU work)
1. `…/audio-prm/bin/python -c "import torch,mprm,acestep,demucs; print('ok')"`
2. `ls ~/.cache/modelscope/hub/models/ACE-Step/ACE-Step-v1-3.5B` resolves.
3. Re-audit records == 1,676 (per the runbook §2), then proceed with resume Steps A–D.
