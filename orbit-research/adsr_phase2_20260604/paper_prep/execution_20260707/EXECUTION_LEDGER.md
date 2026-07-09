# ADSR Publication Execution Ledger

Started: 2026-07-07
Root: `orbit-research/adsr_phase2_20260604/paper_prep/execution_20260707/`

## Ground State

- an12 allocation: Slurm job `96931`, node `an12`, running but idle at start.
- an29 allocation: Slurm job `96930`, node `an29`, running but idle at start.
- Storage quota at start: about 142 GB used of 500 GB soft quota.
- Repo path note: `/HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion`
  and `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion`
  resolve to the same workspace.

## Boundaries

- Do not target an17.
- Do not mutate frozen configs, `runs/**`, `_pi_review_pkg/**`, human packets,
  calibration/parity/gate evidence, `trajectory_candidate_dataset.jsonl`, or archives.
- Do not distribute human-eval packets, contact raters, or unblind.
- Do not scale judge calls until a repaired 10-clip smoke passes.

## Events

- 2026-07-07: Execution root created. Initial implementation focuses on reusable
  ledger audits and publication metrics before any new generation launch.
- 2026-07-07: Added `ledger_audit.py` and `publication_metrics.py`.
  Baseline ATLAS audit passed on 16,384 rows with no duplicate
  `(prompt_id, condition, seed_idx)` keys. Publication metrics reproduced
  vocal median 0.0645, instrumental median 0.3613, V3 mean delta +0.6858
  with 17/17 prompts improved, and I_strong mean delta +0.0055.
- 2026-07-07: Judge smoke repair attempted. The original
  `smoke_10clip_20260706` failed 8/10; the two failed expected-negative clips
  were near detector threshold. A repaired extreme-detector manifest was built,
  but `qwen3.5-omni-plus` failed 6/10 and the specified fallback
  `qwen3.5-omni-flash` also failed 6/10. Large-scale judge A′/B′ calls are
  blocked pending PI/manual decision.
- 2026-07-07: Compute-node preflight reached both active allocations. an12
  and an29 both report torch 2.5.1+cu121, CUDA available, and 8 A800 GPUs.
  Broad D0 timed out because optional CLAP import attempted network access to
  Hugging Face from compute nodes. Narrow SAO check on an29 found
  `stable_audio_tools` missing; `mprm.inference.sao` imports but Stage 4 SAO
  generation is dependency-blocked until that package/weights are installed.
- 2026-07-07: ACE-Step D1 one-sample smoke passed on an12. Stage 3 worker and
  pre-registration added. Initial unbalanced smoke was clean but invalid as a
  launch gate because it covered only `held_out_0001`/`vocal_guidance`; worker
  smoke limiting was fixed to round-robin across conditions. Balanced smoke
  `smoke50_balanced` passed: 50 rows, 0 errors, all six conditions represented,
  0 near-silent clips, 0 missing FLACs, duplicate-key audit PASS.
- 2026-07-07: Full Stage 3 intervention-decomposition run launched on an12
  under tag `full64` (expected 6,144 rows). First-500 audit passed at 554
  current rows: duplicate/schema audit PASS, 0 errors, 0 near-silent clips,
  0 missing FLACs. First 500 rows are vocal-side only due task ordering; run
  remains active for instrumental block audit later.
- 2026-07-07: Stage 4 SAO dependency dry-run checked on login node. Installing
  `stable-audio-tools` into the shared `audio-prm` environment would upgrade
  torch/torchaudio to 2.7.1 and pull a new CUDA dependency stack. This is not
  safe while Stage 3 depends on torch 2.5.1 in the same environment. SAO remains
  blocked pending isolated env or pinned no-upgrade install.
- 2026-07-07: Stage 3 full run crossed into instrumental block. Audit at 3,434
  current rows passed duplicate/schema checks with all six conditions present,
  0 errors, 0 near-silent clips, and 0 missing FLACs. Quota remained safe
  at about 164 GB used.
- 2026-07-07: Stage 3 intervention-decomposition run `full64` completed on
  an12 with exactly 6,144 rows: 8 ledgers x 768 rows, 6,144 kept FLACs, and
  about 32 GB under `stage3_intervention_20260707/keep/full64`. Final ledger
  audit PASS: 0 parse errors, 0 missing required rows, 0 duplicate
  `(prompt_id, condition, seed_idx)` keys. Final output summary PASS:
  0 generation errors, 0 near-silent rows, 0 missing FLACs. Condition-level
  type-correct rates: `vocal_guidance` 0.781250, `vocal_both` 0.779412,
  `vocal_hints` 0.093750, `instr_both` 0.377083, `instr_sampler` 0.344792,
  and `instr_text` 0.326042.
- 2026-07-07: Population retry-map N2 prepared for an12 because an29 remains
  reserved for Stage 4 and SAO is dependency-blocked. Pre-registration frozen
  at `paper_prep/POPULATION_RETRY_PREREG_20260707.md`. Manifest selected
  128/256 held-out prompts stratified by 8-candidate baseline violation count:
  `{0:51, 1:24, 2:17, 3:8, 4:11, 5:8, 6:5, 7:2, 8:2}`. Smoke `smoke50`
  completed on an12 with 50 rows and all violation bins represented. Smoke
  ledger audit PASS, output summary PASS, 0 errors, 0 near-silent rows,
  0 missing FLACs.
- 2026-07-07: Population retry-map full run launched detached on an12 under
  tag `full128`, with 8 workers and expected total `128 prompts * 128 seeds =
  16384` rows.
- 2026-07-07: Population retry-map first-500 audit passed at 550 current
  rows. Ledger audit PASS: 0 parse errors, 0 missing required rows,
  0 duplicate `(prompt_id, seed_idx)` keys. Output summary PASS: 0 errors,
  0 near-silent rows, 0 missing FLACs. Quota after first-500 was about
  178.6 GB used of 500 GB soft quota.
- 2026-07-07: Population retry-map 4k progress audit passed at 4,190 current
  rows. Ledger audit PASS and output summary PASS, with 0 errors,
  0 near-silent rows, and 0 missing FLACs. Quota at the surrounding monitor
  poll was about 194.4 GB used.
- 2026-07-07: Population retry-map crossed the bin-0 boundary. At audit time,
  ledgers had 6,528 rows from baseline-violation bin 0 and had begun bin 1.
  Cross-bin ledger audit PASS and output summary PASS, with 0 errors,
  0 near-silent rows, and 0 missing FLACs. Quota at the surrounding monitor
  poll was about 205.2 GB used.
- 2026-07-07: Population retry-map crossed into baseline-violation bin 2.
  Boundary audit around 9.8k rows PASS: 0 parse errors, 0 missing required
  rows, 0 duplicate `(prompt_id, seed_idx)` keys, 0 errors, 0 near-silent rows,
  and 0 missing FLACs. A small overlap between late bin-1 rows and early bin-2
  rows is expected because workers shard by task index.
- 2026-07-07: Population retry-map crossed into baseline-violation bin 3.
  Boundary audit at 11,986 rows PASS. Bins 0, 1, and 2 were complete
  (`6528`, `3072`, and `2176` rows respectively), bin 3 had begun, and
  integrity checks remained clean: 0 duplicate keys, 0 errors, 0 near-silent
  rows, and 0 missing FLACs.
- 2026-07-07: Population retry-map late-bin audit around 14.3k rows PASS.
  Bins 0-3 were complete and bins 4-5 were overlapping as expected from
  sharded workers. Integrity checks remained clean: 0 duplicate keys,
  0 errors, 0 near-silent rows, and 0 missing FLACs. Quota at the surrounding
  monitor poll was about 239.3 GB used.
- 2026-07-07: Population retry-map `full128` completed and final audits
  passed. Final ledger audit: 8 files, 16,384 rows, 2,048 rows per worker,
  0 parse errors, 0 missing required rows, 0 duplicate `(prompt_id, seed_idx)`
  keys. Final output summary: 16,384 OK rows, 0 errors, 0 near-silent rows,
  0 missing FLACs, 16,384 kept FLACs. Final quota was about 251.9 GB used of
  500 GB soft quota; `population_retry_20260707` uses about 73 GB.
- 2026-07-07: Population retry-map read-out PASS. Regime counts over 128
  selected held-out prompts: `easy_ge_1_in_2` 67 (0.523438),
  `seed_recoverable_1_in_4_to_1_in_2` 33 (0.257812),
  `low_1_in_16_to_1_in_4` 23 (0.179688), and `rare_le_1_in_16`
  5 (0.039062). Stratum mean clean rates: instrumental 0.761137
  over 47 prompts; vocal 0.401331 over 81 prompts.
- 2026-07-07: Checked next backlog tail-deepening area after an12 became
  idle. Existing `ext512*` artifacts under the authoritative retry-study tree
  are logs only and ambiguous relative to current frozen evidence; no new
  backlog run was launched into that tree without a scoped artifact plan.

## Current Gate Status

- Stage 3 intervention decomposition: complete and audited.
- Population retry map: complete and audited.
- Judge A'/B' scale calls: blocked because both repaired judge smokes failed
  6/10.
- Stage 4 SAO: blocked because `stable_audio_tools` is absent and a direct
  install into shared `audio-prm` would upgrade torch/torchaudio and CUDA stack.
- an17: not targeted.
