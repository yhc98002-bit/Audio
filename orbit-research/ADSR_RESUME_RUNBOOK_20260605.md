# RUNBOOK: Resume ADSR re-collection from checkpoint (after accidental GPU release)

> **Saved 2026-06-05.** The user will migrate the project data to a GPU node and wake the
> session with `claude --resume`. This file is the canonical, standalone resume runbook —
> follow it top to bottom on resume. **Verdict: RESUME, do not restart** (~41% is done,
> intact, deterministically reproducible).

---

## 0. STATE SNAPSHOT (audited read-only at 2026-06-05 04:21Z, before GPU loss confirmed)

- Run dir: `runs/adsr_recollect_20260604_full01/` (8 shards). **1,676 / 4,096 records on disk,
  0 corrupt JSON lines, 0 duplicate `(prompt_id,candidate_index)`, 0 prompts with >8.**
- Completion: **206 complete (8/8)**, **6 partial** (20 records short), **300 not started**.
  → **2,420 candidate-gens remain (59.1%).** Rescue set = **306 prompts**.
- Partial prompts (recompute live on resume — do not trust this stale list):
  `dev_0092(5/8) dev_0220(1/8) held_out_0021(6/8) held_out_0088(3/8) held_out_0155(7/8)` + 1 more.
- Labeling: `orbit-research/adsr_phase2_20260604/vocal_presence_raw.jsonl` had 1,632 labels,
  4,896 mel files, `snapshots/snapshot_cov25.json` written. Watch loop is DEAD (pid file stale).
- cov25 result (early-warning, not a claim): cand type-error prev 0.213, prompt-affected 0.643,
  vocal 0.235 / instr 0.180, survivor top1 0.202, scalar-proxy held-out AUC 0.765 / AUPRC 0.805.

## 1. MIGRATION CHECKLIST (move these to the GPU node at IDENTICAL relative paths under repo root)

Repo root: `…/HaocunYe/Research/AudioDiffusion/`. Migrate (read-then-write, verify sizes):
- `runs/adsr_recollect_20260604_full01/**` — the 1,676 records + per-candidate audio/mel (LARGE).
- `orbit-research/adsr_phase2_20260604/**` — labels, mels, snapshots, watch.log/pid.
- `orbit-research/EARLY_TWEEDIE_VALIDATION_512_PROMPTS.json` — the master manifest.
- `scripts/` (esp. `collect_early_tweedie_validation.py`, `launch_adsr_recollect.sh`,
  `adsr_downstream.py`, `run_adsr_watch.sh`, `adsr_pipeline_monitor.sh`).
- `configs/` (prompts, `baselines/r2_bon.yaml`, `eval/gate_v2.yaml.draft`).
- This runbook itself (it lives in `~/.claude/plans/` — copy it into the repo, e.g.
  `orbit-research/ADSR_RESUME_RUNBOOK_20260605.md`, so it travels with the data).
- The conda env `audio-prm` must exist on the new node (torch 2.5.1+cu121, demucs, torchaudio).
  If the env is not migrated, rebuild per CLAUDE.md "Environment".

## 2. ON-RESUME FIRST ACTIONS (verify before spending any GPU — do NOT trust §0 blindly)

1. `nvidia-smi -L` → record GPU **count and model**. **GPU decision is still OPEN** (see §5);
   ask the PI which strategy, since model ≠ A800 raises a homogeneity question.
2. Re-audit on-disk state with the same script used in §0: recount records, recompute the
   per-prompt `<8` set (the rescue set), reconfirm 0 dup / 0 corrupt. Use the LIVE numbers.
3. Confirm the env python imports torch: `…/.conda/envs/audio-prm/bin/python -c "import torch"`.
4. Finish CPU labeling now (0 GPU): relaunch `scripts/run_adsr_watch.sh` to label the ~44
   stragglers — EVPD inputs for the 206 done prompts become ready while GPU is arranged.

## 3. WHY RESUME IS SAFE (key technical facts, already verified)

- `collect_early_tweedie_validation.py:308-310`: `manifest_index` is read from the manifest
  row (global, stable) and `seed = seed_base + manifest_index*1000 + cand_idx`. Regenerating a
  prompt from its original manifest row reproduces identical seeds → mergeable, deterministic.
- No native resume: `mkdir(exist_ok=False)` (:218), records open `"w"`/truncate (:306),
  candidate loop always `range(bon_n)` from 0 (:309). → resume writes to NEW dirs + a merge step.
- Original gen config to MATCH EXACTLY (from `shard00/run_summary.json`):
  `--bon-n 8 --target-sigmas 0.9 0.8 0.7 0.5 0.3 --save-audio --progress-every 16`,
  `reward_config=configs/baselines/r2_bon.yaml`, `gate_policy=configs/eval/gate_v2.yaml.draft`,
  **seed-base NOT passed → default 2026052700 (do NOT pass --seed-base on resume).**
- Manifest schema: dict, rows under key `"prompts"` (512); each row has `manifest_index,
  prompt_id, prompt_source, split, strata, vocal_stratum, has_lyrics`.

## 4. EXECUTION STEPS (after GPU strategy chosen)

**Step A — Build rescue manifest (0 GPU).** New `scripts/build_resume_manifest.py`:
recount per-prompt candidates from `runs/adsr_recollect_20260604_full01/shard0*/candidate_records.jsonl`;
select prompt_ids with `<8`; copy the master manifest dict, replace `"prompts"` with the
filtered rows **in manifest_index order** (rows untouched, incl. `manifest_index`), fix
`n_prompts`/`split_counts`/`vocal_counts`. Write
`orbit-research/adsr_recollect_resume_manifest_20260605.json`. Assert selected==prompts-with-<8.

**Step B — Launch resume generation (GPU).** New `scripts/launch_adsr_recollect_resume.sh`
(model on `launch_adsr_recollect.sh`, **no `rm -rf`**): `RUN2=runs/adsr_recollect_20260604_full01_resume`,
`MAN2=<rescue manifest>`. **Auto-detect NGPU from `nvidia-smi -L`**, `chunk=ceil(306/NGPU)`,
per GPU `--prompt-offset g*chunk --n-prompts chunk` (last clamps). Identical flags as §3; **do
not pass --seed-base.** Run a 1-prompt smoke (`--n-prompts 1 --bon-n 2`) first to catch OOM
(esp. 24 GB cards) before the full fan-out.

**Step C — Merge → 4,096 (0 GPU). CODEX-REVIEW Steps A+C scripts before running (standing rule
[[feedback-always-codex-review]]).** New `scripts/merge_resume_records.py`: read original 1,676 +
resume records; dedupe by `(prompt_id,candidate_index)` with **original-wins precedence** (partial
prompts keep their original done candidates; only genuinely-missing indices come from resume — this
sidesteps cross-GPU determinism entirely). **Assert total==4096, 8/prompt ×512, id-set==manifest,
0 dup.** Write `runs/adsr_recollect_20260604_full01_merged/shard0*/candidate_records.jsonl`.
Records carry their own audio/mel paths, so labeling works regardless of which run made each.

**Step D — Re-point downstream (0 GPU).** Update `RUN` in `scripts/adsr_downstream.py:~26` to the
merged dir; relaunch `scripts/run_adsr_watch.sh` + `scripts/adsr_pipeline_monitor.sh cov50`.
Then continue the existing pipeline: finish labeling → Phase-2A (type-error study + EVPD; **cast
float16 mels to float32 before any reduction**) → full ADSR offline sim with EVPD branch → Codex
Audit 3 → decision gate → Phase-4 online pilot if it beats the common-score-restart baseline.

## 5. OPEN DECISION — GPU strategy (ask PI on resume; was deferred 2026-06-05)

Switching off A800 is allowed but not free. Determinism for the merge is fine (original-wins).
The real risks: (a) **homogeneity** — done(A800) vs remaining(new GPU) tracks manifest-index
position, so a systematic GPU-type quality shift could mildly confound; mitigate with a
**cross-GPU control** (regenerate ~15 already-done A800 prompts on the new GPU, compare
reward/type-error/early-σ within noise). (b) **memory** — 4090 = 24 GB may OOM on BoN-8 +
trajectory capture + on-GPU reward models (original used 80 GB); smoke-test first. PRO 6000
Blackwell = 96 GB (no memory issue) but single card ≈ 8× slower than 8-way.
Candidate options offered: 8×4090+control (fast, needs OOM smoke) / wait-for-A800 (zero risk) /
8×4090+Blackwell (9 workers) / Blackwell-only (slow, fine only for the 20 partial top-ups).

## 6. HARD BOUNDARIES (unchanged)
Resume writes only to NEW run dirs; **never modify `runs/**` existing data**, `configs/eval/gate_v1.yaml`,
`_pi_review_pkg/**`, calibration/parity/gate files, or `trajectory_candidate_dataset.jsonl`.
`gate_v2.yaml.draft` stays a draft (used as `--gate-policy`, never renamed/activated). No RL,
pruning+RL, Phase D, human eval, EVPD training-as-result, or canonical proposal rewrite without PI sign-off.
