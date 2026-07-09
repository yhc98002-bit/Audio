# Experiment Tracker — Headroom-Gated M-PRM (PI v2.0)

> *Per-run tracker.* Append one row per planned or completed run. Use TODO / RUNNING / DONE /
> FAILED / SKIPPED statuses. Authoritative compute accounting lives in `RUN_LEDGER.jsonl`; this
> table is the human-readable index. Phase 1 of `/experiment-bridge`, 2026-05-15.

> **Status refresh (2026-05-23):** the table below is a historical plan index and still
> contains many `TODO` rows from the original bridge. Current executed status is:
>
> | Run family | Current status |
> |---|---|
> | Phase A M1a / headroom gate | DONE; H1 passed after PI spot-check. |
> | D3a / Tweedie formula | DONE; `TWEEDIE_DERIVATION_NOTE.md` is resolved. |
> | Phase B.1 H2 reliability | DONE; 128-prompt verdict `STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES`. |
> | Phase B.3 H3 credit-unit comparison | PREPARED + smoke-tested; full launch pending PI approval. |
> | Phase B.2 segmentation/locality | NOT LAUNCHED per PI directive. |
> | Phase C M-PRM training | NOT LAUNCHED. |

| Run ID | Milestone | Wave | Rung (per COMPONENT_BUNDLE_LADDER) | Purpose | System / Variant | Split | Metrics | Priority | Status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| R000 | M0 | W1 | — | env smoke | D0: deps + tensor + I/O | — | install / import OK | MUST | TODO | run before any GPU; CPU-only |
| R001 | M0 | W1 | R0 | model load + 1 sample | D1: ACE-Step v1.5 + SAO 1.0, default CFG, fixed seed | — | non-silent waveform; seed determinism; SR match | MUST | TODO | uses `papers/diagnostic/d1_*.wav` |
| R002 | M0 | W1 | — | reward harness smoke | D2: CLAP, Audiobox, FAD, Whisper-WER, MERT, Demucs on D1 output + 3 references | — | in-range values per axis; finite | MUST | TODO | pin reward-model versions |
| R003 | M0 | W1.1 | R10 | Tweedie reconstruction sanity | D3: **Stage-1 K=3 checkpoints at τ ∈ {0.5, 0.3, 0.1}** (REVISED 2026-05-20 R2 #25 from prior K=4 default); escalate to K=4 (+τ=0.7) only on Stage-1 ambiguity OR Stage-0 sigma diagnostic justification. Decode `â_k` via `x̂_0 = x_σ − σ·v_out` for ACE-Step (σ=0 data, σ=1 noise per `TWEEDIE_DERIVATION_NOTE.md` §8); similarity vs `a_final`. NOTE: D3 REFUSES to run unless `TWEEDIE_DERIVATION_NOTE.md` STATUS=RESOLVED (per D3a / STOP-B-4) or `--allow-unresolved` is passed | 16 prompts | monotonic similarity; aesthetic Spearman trend | MUST | TODO | verifies A26 / Q-PRM-1 |
| R004 | M0 | W1 | R11 | segmentation / Demucs / Whisper smoke | D4: MERT on D1; Demucs htdemucs; Whisper-large-v3 | D1 outputs + 1 reference | F1 sanity; SI-SDR > 5 dB; non-empty transcript | MUST | TODO | A27, A28, A29 |
| R005 | M0 | W1 | R8 | mini Flow-GRPO | D5: 4 prompts × 8 RL steps, T_train=5, G=4, R_lcb reduced Π | 4 prompts | loss finite; KL ∈ [0, 5]; reward upward delta | MUST | TODO | tests A7/A8/A9 |
| R006 | M0 | W1 | R11 (Phase B) | D6 locality probe — **DEFERRED stub (STOP-B-2 fix #3)** | requires latent-span perturbation logic from Phase B/C scaffolding | n/a in current bridge | stub script exits zero with deferred message | NICE (stub) | TODO | Promoted to a gating diagnostic only by the next /experiment-bridge call once Phase B/C lands |
| R007 | M0 | W1 | R21 (Phase C) | D7 end-to-end mini M-PRM — **DEFERRED stub (STOP-B-2 fix #3)** | requires Phase B + Phase C scaffolding | n/a in current bridge | stub script exits zero with deferred message | NICE (stub) | TODO | Same promotion rule as D6 |
| R008 | M0 | W1 | — | **human-eval UI scaffold (STOP-B-1 fix)** | minimal pairwise UI: whole-song playback + section playback + prompt/lyrics display + worst-section annotation | n/a | UI loads; can play arbitrary 30–120 s audio; section-local annotation persists | MUST | TODO | move M6 dev to M0 since human eval is biggest bottleneck |
| R009 | M0 | W1.1 | — | UI 4-pair smoke test | 4 synthetic pairs through the UI; 5-rater pilot | n/a | rater can complete all 4 pairs without UI bug | MUST | TODO | UI is blocking for M6 if smoke fails |
| **R050 (STOP-B-4)** | **M0.5** | **W1.2** | — | **Informal mini-headroom probe (pause-and-report)** | 32 stratified prompts × {Base seed=42, BoN-8 with R_lcb under reduced Π={identity, crop}} | 32-prompt subset of dev | median Δ R_lcb(BoN-8 − Base) > 0 AND ≥ 50 % prompts have positive Δ; otherwise **PAUSE and report to PI** | NICE (informational, pause-and-report) | TODO | non-paper-bearing; M1a's 256-prompt audit is the authoritative gate. Cost ~3 GPU-h. |
| **R051 (STOP-B-4)** | **M0.5** | **W1.2** | — | **D3a Tweedie code-level derivation** | inspect ACE-Step source via `scripts/d3a_tweedie_derivation.py`; produce `orbit-research/TWEEDIE_DERIVATION_NOTE.md` with file/function refs for {flow target, time convention, latent scaling, clean-target formula} | n/a (code reading) | derivation note STATUS=RESOLVED; if AMBIGUOUS, test candidates and pick by reconstruction fidelity | MUST (hard gate on Phase B / M2) | TODO | M1a may proceed in parallel; Phase B / M2 is HARD-BLOCKED until R051 is RESOLVED. Cost ~5 GPU-h (mostly engineering wall-clock). |
| **R100** | **M1a** | **W2.1** | R0 | Phase A base sampling | dev + held-out | 256+256 | per-axis reward distribution | MUST | TODO | reference |
| R101 | M1a | W2.1 | R1 | CFG sweep | dev + held-out | 256+256 × 5 CFG | per-axis vs CFG | MUST | TODO | 1-knob ceiling |
| R102 | M1a | W2.1 | R2 | BoN-4/8/16 | dev + held-out | 256+256 × 3 N | BoN curve elasticity | MUST | TODO | inference ceiling |
| R103 | M1a | W2.1 | R3 | Robust BoN (R_lcb over Π) | dev + held-out | 256+256 | R_lcb vs raw BoN | MUST | TODO | reward hackability |
| R104 | M1a | W2.1 | R4 | BoN+CFG | dev + held-out | 256+256 | composite ceiling | MUST | TODO | combined inference |
| R109 | M1a | W2.1 | R9 | S7 sampler-control-only | dev + held-out | 256+256 with controller search | R_lcb @ held-out; matched inference cost | MUST | TODO | weight-update falsifier; in M1a per STOP-B-1 |
| R110 | M1a | W2.1 | — | reward-human calibration | Block A.aux | 32 ACE-Step + 32 SAO × 5 raters × 5 axes | Spearman(human, axis); Whisper-vs-human WER | MUST | TODO | A16/A17/A28 |
| **R150a** | **M1a gate** | **W2.1 end** | — | **Basic-headroom gate decision (STOP-B-1)** | n/a | held-out | gate per NULL_RESULT_CONTRACT §1 Block A.1 | MUST | TODO | **PASS → run M1b; FAIL → halt and pivot to saturation paper** |
| R105 | M1b | W2.2 | R5 | SFT-on-best | dev | 256 BoN-8 elites | 1-sample inference retention | MUST (cond. M1a pass) | TODO | offline amortization |
| R106 | M1b | W2.2 | R6 | Robust Elite SFT (S6) | dev | 256 R_lcb-LCB elites | R_lcb @ held-out | MUST (cond. M1a pass) | TODO | former S6 Stages 0–3 |
| R107 | M1b | W2.2 | R7 | Flow-DPO | dev | preference pairs from R3 / R2 | R_lcb @ held-out | MUST (cond. M1a pass) | TODO | offline preference |
| **R108a** | **M1b** | **W2.2** | **R8a** | **Outcome-GRPO-plain (canonical terminal control — STOP-B-1)** | dev; **no curriculum, no lyric guard** | 256 uniform sampling | R_lcb @ held-out; KL trace | MUST (cond. M1a pass) | TODO | "vanilla Flow-GRPO + R_lcb"; canonical terminal-reward baseline; matched-compute control for C3 |
| **R108b** | **M1b** | **W2.2** | **R8b** | **Outcome-GRPO-guarded (stronger terminal baseline — STOP-B-1)** | dev with optional curriculum from R102 | 256 with optional q_curriculum | R_lcb @ held-out; lyric WER; KL trace | MUST (cond. M1a pass) | TODO | terminal + Lagrangian lyric guard + optional curriculum; stronger control, NOT canonical |
| **R150b** | **M1b corpus complete** | **W2.2 end** | — | **M1b post-training corpus check** | n/a | dev | each rung produced stable trace; reward-drift bounded; probes do not fire post-RL | MUST | TODO | feeds Phase D matched-compute controls |
| **R200** | **M2** | **W3** | R10 | Tweedie reliability (adaptive per archived `refine-logs/archive/2026-05-revision/FINAL_REVISION_CRITIC.md` #6) | dev | **Stage 1: 64 prompts × 3 checkpoints (τ ∈ {0.5, 0.3, 0.1}) × 5 axes**; escalate to 128 + τ=0.7 on ambiguous | **Spearman ≥ 0.5 binary gate** (REVISED 2026-05-20 #11) | MUST | TODO | H2; D3a hard pre-Phase-B gate must be RESOLVED first |
| R201 | M2 | W3 | R11 | segmentation reliability | dev | 32 hand-labeled samples | **MERT boundary F1 3-level gate (STOP-B-2 fix #2): ≥ 0.7 strong pass → MERT primary; 0.5–0.7 weak pass → CBM refinement on the trained side, oracle segmentation only for human-eval; < 0.5 fail → demote section credit to ablation** | MUST | TODO | A27 (3-level) |
| R202 | M2 | W3 | R11 | locality probe | dev | 32 prompts × 4 sections | median LocalityRatio ≥ 1.5 / 2.0 | MUST | TODO | H4 (A30) |
| **R250** | **M2 gate** | **W3 end** | — | **Reliability gate + Locality probe decision** | n/a | dev | gate per NULL_RESULT_CONTRACT §2.1 + §3 | MUST | TODO | **stop M3+ if H2 fails; route to terminal-reward study** |
| **R300** | **M3** | **W4** | R12 | Stepwise-Tweedie process reward | dev + held-out | matched compute | per-section Spearman; broken-section ID | MUST | TODO | timestep credit unit (control) |
| R301 | M3 | W4 | R13 | FixedWin-Tweedie | dev + held-out | matched compute | per-section Spearman | MUST | TODO | fixed window credit unit |
| R302 | M3 | W4 | R14 | BeatWin-Tweedie | dev + held-out | matched compute | per-section Spearman | MUST | TODO | beat-aligned credit unit |
| R303 | M3 | W4 | R15 | LyricSpan-Tweedie | dev + held-out | matched compute | per-section Spearman; lyric-WER trace | MUST | TODO | lyric-aligned credit unit |
| R304 | M3 | W4 | R16 | Section-Tweedie (no extras) | dev + held-out | matched compute | per-section Spearman; broken-section ID | MUST | TODO | **proposed unit** |
| R305 | M3 | W4 | — | random-window control | dev + held-out | matched compute | per-section Spearman | MUST | TODO | sanity null |
| R306 | M3 | W4 | — | per-section human pref calibration | Block B.3 | 4 pairs × 256 prompts × 5 raters on top-Δ samples | per-axis preference rate | MUST | TODO | C2 evidence |
| **R350** | **M3 gate** | **W4 end** | — | **Credit-unit gate decision** | n/a | dev + held-out | gate per NULL_RESULT_CONTRACT §2.3 | MUST | TODO | **stop M4+ if H3 fails; route to credit-unit negative study** |
| **R400** | **M4** | **W5** | R17 | M-PRM + action-localized advantage | dev | LoRA-16, G=8, T_train=5, rl_steps≤3k | per-section human pref; broken-section rate; lyric WER | MUST | TODO | + H4 active |
| R401 | M4 | W5 | R18 | + Lagrangian lyric guard | dev | as above + ε=0 | Pareto (R_music, R_lyric) | MUST | TODO | + H5 |
| R402 | M4 | W5 | R19 | + Calibrated CVaR (α=0.30, **β=0** trained per R2 #11; β=0.5 offline sensitivity only — DISTINCT from beta_robust=0.5) | dev | as above | broken-section rate | MUST | TODO | + A3 (former H6) |
| R403 | M4 | W5 | R20 | + headroom-weighted curriculum | dev | as above | sample-efficiency curve | MUST | TODO | + sample efficiency |
| R404 | M4 | W5 | R21 | **M-PRM full** | dev | as above | full headline metrics | MUST | TODO | proposed |
| **R410a** | **M4** | **W5** | **R8a matched** | **Outcome-GRPO-plain matched (canonical)** | dev | rerun R108a at Phase C compute parity | per-section human pref; broken-section rate; lyric WER | MUST | TODO | **canonical matched-compute terminal control for C3 (STOP-B-1)** |
| **R410b** | **M4** | **W5** | **R8b matched** | **Outcome-GRPO-guarded matched (stronger)** | dev | rerun R108b at Phase C compute parity | per-section human pref; broken-section rate; lyric WER | MUST | TODO | stronger matched control; reported alongside R410a |
| R411 | M4 | W5 | R12 matched | Stepwise-Tweedie matched | dev | rerun R300 at matched compute | per-section pref | MUST | TODO | matched control |
| R412 | M4 | W5 | R6 matched | Robust Elite SFT (S6) matched | dev | rerun R106 at matched compute | per-section pref | MUST | TODO | matched control |
| R413 | M4 | W5 | R7 matched | Flow-DPO matched | dev | rerun R107 at matched compute | per-section pref | MUST | TODO | matched control |
| R414 | M4 | W5 | R9 matched | S7 sampler-control matched | dev | rerun R109 at matched compute | per-section pref | MUST | TODO | matched control |
| **R500** | **M5** | **W6** | R21 − R17 | M-PRM w/o action localization | dev | matched compute | per-section human pref; broken-section rate | MUST | TODO | H4 ablation |
| R501 | M5 | W6 | R21 − R18 | M-PRM w/o lyric guard | dev | matched compute | Pareto (R_music, R_lyric) | MUST | TODO | H5 ablation |
| R502 | M5 | W6 | R21 (mean) | M-PRM w/ mean instead of CVaR | dev | matched compute | broken-section rate | MUST | TODO | H6 ablation |
| R503 | M5 | W6 | R21 (R16 ← R13) | M-PRM w/ fixed-window unit | dev | matched compute | per-section human pref | MUST | TODO | training-time H3 |
| R504 | M5 | W6 | R21 (raw reward) | M-PRM w/ raw reward | dev | matched compute | reward calibration trace | MUST | TODO | robust-LCB ablation |
| R505 | M5 | W6 | R19 (no curriculum) | M-PRM w/o curriculum | dev | matched compute | sample efficiency | MUST | TODO | curriculum ablation |
| **R600** | **M6** | **W7** | top-3 | human eval (REVISED 2026-05-20 R2 #28 two-tier; supersedes prior STOP-B-2 fix #6 pair-accounting) | dev | **Tier 1 MUST: 128 unique pairs × 5 raters/pair × 5 axes/rating ≈ 3,200 axis-judgments. Tier 2 NICE (strong/borderline/rebuttal only): 240 pairs + section-local A/B → ≈ 8,400 axis-judgments.** Anti-fatigue session design per audit Fix #9 (Block D.hum). | per-axis preference rate; rater α (Krippendorff); per-genre balance | MUST | TODO | C3 headline; UI from M0 |
| **R700** | **M7** | **W8** | R21 | **M-PRM ACE-Step held-out (MUST per STOP-B-1)** | held-out | full eval | held-out − dev gap | MUST | TODO | ACE-Step is primary backbone |
| R701 | M7 | W8 | matched | top-3 baselines ACE-Step held-out | held-out | full eval | held-out − dev gap | MUST | TODO | matched controls |
| R702 | M7 | W8 | R21 / R6 / R8a on SAO | **SAO cross-model transfer (NICE-conditional per STOP-B-1)** | SAO prompts | full eval | SAO − ACE-Step transfer gap | NICE | TODO | runs only if budget remains AND Phase A SAO audit clean; SAO is first scope cut per FINAL_PROPOSAL §7 |
| R703 | M7 | W8 | R21 60–120 s | long-song extension | dev / held-out | full eval | length-stability | NICE | TODO | duration sensitivity |
| **R800** | **M8** | **W9** | — | failure analysis / qualitative | n/a | case studies | descriptive | NICE | TODO | Block D.fail |

**Status legend.** TODO (planned, not started) · RUNNING (live) · DONE (completed, results
recorded) · FAILED (run failed; see RUN_LEDGER for cause) · SKIPPED (skipped per scope cut /
gate failure / pivot).

**Gates** are bolded rows (`R150`, `R250`, `R350`). They are not runs; they are decision points
that consume the preceding wave's results.

**Compute accounting.** Sum of GPU-h is recorded in `RUN_LEDGER.jsonl`; this table is
human-readable index only. Plan-time per-method compute targets live in `CONTROL_DESIGN.md` §6.

**Document history.**
- v1.0 — 2026-05-15. Phase 1 of `/experiment-bridge`. Authored against `EXPERIMENT_PLAN_EXEC.md`.
- v1.1 — 2026-05-15 STOP-B-1 fix-pass. Added R008/R009 UI scaffold in M0; relabelled M1
  rows into M1a (R100/R101/R102/R103/R104/R109/R110) and M1b (R105/R106/R107/R108a/R108b);
  R108 split into R108a (Outcome-GRPO-plain, canonical) + R108b (Outcome-GRPO-guarded,
  stronger control); R150 split into R150a (basic-headroom gate before M1b) + R150b (M1b
  post-training corpus check); R410 split into R410a/R410b (matched-compute) for Phase C;
  R702 SAO transfer reclassified as NICE-conditional per FINAL_PROPOSAL §7 scope-cut order;
  R700 + R701 ACE-Step held-out marked explicitly MUST. Proposal / mainline / 5,400 GPU-h
  budget unchanged.
- v1.2 — 2026-05-15 STOP-B-2 consistency patch. R006/R007 reclassified as DEFERRED stubs
  (pre-Phase-B; not gating M1a per STOP-B-2 fix #3). R201 success criterion expanded to the
  3-level MERT F1 gate (STOP-B-2 fix #2). R600 human-eval row spells out unique-pairs ×
  raters × axes = individual-judgments accounting (STOP-B-2 fix #6). Documents history table
  + cross-references updated.
- v1.3 — 2026-05-15 STOP-B-4 pre-M1a additions. Added **R050 informal mini-headroom probe**
  (pause-and-report, NICE/informational, 32 stratified prompts × Base vs BoN-8, reduced Π)
  and **R051 D3a Tweedie code-level derivation** (MUST, hard gate on Phase B/M2, not M1a)
  in a new **M0.5 milestone (W1.2)** between M0 and M1a. R003 (D3 reconstruction sanity)
  note expanded to require RESOLVED derivation note before passing.
