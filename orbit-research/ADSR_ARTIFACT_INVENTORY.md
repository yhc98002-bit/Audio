# ADSR Artifact Inventory + Phase-0 Canonical-Consistency Gate (2026-06-04)

Researcher: claude:researcher. Goal: execute the first full ADSR experimental phase.
This is the **Phase-0 gate** — Phase 1 does not start until the 5 consistency checks PASS.

## Canonical artifacts (post proposal-revise + lyric fix)

| Artifact | Path | Status |
|---|---|---|
| Promoted candidate dataset (BoN-8) | `orbit-research/trajectory_candidate_dataset.jsonl` | **4096 = 512 prompts × 8**; promoted 2026-06-04 (380 unchanged + 132 lyric-regenerated) |
| Lyric-fixed candidate records | `runs/early_tweedie_validation_final_lyricfix_20260603/shard00/candidate_records.jsonl` | merged source of the dataset |
| Track A recompute (raw-ETP baseline) | `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.{md,json,_PLOT.csv,_RETENTION.csv}` | regenerated 2026-06-04: Schedule-A **0.9864** @ 0.500 |
| Pre-fix dataset (archive) | `orbit-research/archive/trajectory_candidate_dataset_pre_lyricfix_20260603.jsonl` | superseded |
| BoN-16 subset | `runs/early_tweedie_bon16_subset_128_20260528_full01/shard00..07/` | 128 prompts × 16 (8 shards present) |
| Human spot-check packet (existing) | `orbit-research/human_spotcheck_packet_20260528/`, `pi_listening_review_packet_20260529/` | exists, with per-pair audio (small subset) |
| ADSR plan / proposal | `ADSR_Research_Plan_FINAL_EN_2026-05-29.md`, `refine-logs/{FINAL_PROPOSAL,METHOD_SPEC,EXPERIMENT_PLAN,EXPERIMENT_PLAN_EXEC}.md` v4.0 | current |

## Dataset schema (what the 4096-candidate pool actually contains)

- Per candidate: `prompt_id`, `candidate_index`, `split`, `vocal_stratum`, `language`, strata,
  early-σ scalar rewards at **σ ∈ {0.9, 0.8, 0.7}** (all 8 axes), `final_*` scalar rewards
  (common_robust_lcb, semantic_fit, lyric_intelligibility, aesthetic_*, section_coherence,
  probes), slopes, within-prompt ranks, labels.
- **NOT present:** σ ∈ {0.5, 0.3} rewards; early or final **audio**; **mel-spectrograms**;
  **measured final vocal-presence** (only the prompt's *requested* type `vocal_stratum`).

## DATA GAPS → GPU re-collection needed (Track B)

The ADSR-specific axes cannot be computed from the cached pool:
1. **Axis observability at σ{0.5, 0.3}** — not captured (collect default sigmas = 0.9/0.8/0.7).
2. **Final vocal-presence labels** — need final audio + source separation (Demucs/SVD). The
   Track-A BoN-8 run saved NO audio (`--save-audio` off; 0 wav in the run; the 14,849 wavs found
   are old Phase-A r0/r1/r2/r4/r9 runs, not the candidate pool).
3. **EVPD inputs (early Tweedie-clean mel)** — not saved; only scalar rewards were cached.

→ A GPU re-collection ("data-collection v2") must regenerate the pool with extended sigmas +
saved early-σ audio + saved final audio. The collect script already supports `--target-sigmas`
and `--save-audio`; the only code add is **saving the early-σ decoded audio** (the script already
decodes it for scoring). Mel extraction + vocal-presence labeling are then CPU post-hoc on saved
audio. **Decision:** offline-first science (Phases 1-partial, 2B, 3-partial) runs NOW on the cached
pool (0-GPU); the GPU re-collection runs in parallel to unblock vocal-presence / EVPD / σ{0.5,0.3}.

## Phase-0 consistency checks (the gate)

| # | Check | Verdict | Evidence |
|---|---|---|---|
| 1 | Lyric headline uses lyric-bearing / EN-vocal / vocal-scorable only | **PASS** | analysis `vocal_scorable` stratum (vocal ∧ language=en), n=282; headline 0.682 |
| 2 | No instrumental sentinel in headline lyric | **PASS** | instrumental `final_lyric_intelligibility` ≡ 1.0 sentinel, masked from `vocal_scorable`; verified all-instrumental = {1.0} |
| 3 | Prompt-level split preserved | **PASS** | split by `prompt_id` (dev 256 / held_out 256); no candidate-level leakage |
| 4 | Old polluted 0.8432 marked superseded | **PASS** | caveated as contaminated prior across all v4.0 canonical docs; corrected to 0.682 EN-vocal n=282 |
| 5 | Current canonical lyric headline traceable | **PASS** | 0.682 ETP@50 EN-vocal n=282 → `orbit-research/prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md` + `etv_lyricfix_final_20260603/` |

**GATE VERDICT: PASS — Phase 1 (offline, cached σ) may proceed. The σ{0.5,0.3} + vocal-presence +
EVPD-input rows are gated on the Track-B GPU re-collection (launched in parallel).**

## Execution tracks (parallel; researcher-coordinated)

- **Track A (0-GPU, cached pool):** Phase 1 axis observability on σ{0.9,0.8,0.7,final}; Phase 2B
  late-axis-risk predictor; Phase 3 ADSR offline simulation (scalar early-reward restart/defer/continue,
  EVPD-branch deferred). Helpers + executors.
- **Track B (GPU, exclusive 8×A800):** re-collect the pool with σ{0.9,0.8,0.7,0.5,0.3,final} + saved
  early-σ + final audio → CPU mel extraction + vocal-presence labeling → unblocks σ{0.5,0.3}
  observability, EVPD (Phase 2A), the EVPD branch of ADSR, and audio for the human packet.
- **Codex audits** at the Phase-1 and Phase-3 milestones (not per-edit).

## Hard-boundary confirmation (this program will NOT)
RL training · pruning+RL · Phase D · human crowdsourcing · modify gate_v1.yaml · change reward
definitions · change prompt splits (except declared lyric-bearing subset construction) · rewrite the
canonical proposal · claim paper conclusions before PI review · large second-backbone campaign before
ADSR main results.
