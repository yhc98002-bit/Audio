# ADSR Reframe Brief — single source of truth for the 2026-06-04 canonical reframe

This brief + `ADSR_Research_Plan_FINAL_EN_2026-05-29.md` (the PI's frozen FINAL plan) are the
ONLY authoritative source for rewriting the canonical proposal stack from **ETV** (Early
Trajectory Verification — prune/select a fixed candidate pool) to **ADSR** (Axis-Deferred
Speculative Restart — compute *reallocation* via restart). Every reframed file must be
mutually consistent with this brief. Do NOT invent details not in the ADSR plan or this brief.

## The pivot (M-PRM → ETV → **ADSR**)
- **Title:** *When to Continue: Axis-Deferred Speculative Restart for Flow-Matching Music Generation* (short: **ADSR**).
- **Core question:** *When can we decide whether a music-generation trajectory is worth continuing, and which quality axes must be deferred until later in the flow trajectory?*
- **Method (one line):** use early Tweedie-clean estimates to **terminate low-promise trajectories early and restart new seeds**, while **deferring** decisions for late-observable axes (lyric intelligibility, fine semantics); treat **prompt-type match (vocal vs instrumental presence)** as a high-stakes early-reject axis with its own learned detector.
- ADSR is **NOT** primarily: RL post-training / M-FixedWin-PRM / section-level process reward / simple Early-Tweedie pruning. ETV-pruning becomes a *baseline* (raw ETP), not the headline; M-PRM/section credit becomes *boundary* evidence.

## Hypotheses (verbatim anchor — ADSR §2): H1 early persistence; H2 axis-dependent observability (aesthetic/production & vocal-presence early → semantic mid → lyric latest — the scientific core); **H2b presence-vs-content split (NEW)**; **H3 restart beats fixed-pool selection** (selection is low-stakes: median regret ≈ 0, ETP@50 over BoN-4 ≈ +0.0036); H4 axis-deferred restart preserves late axes; **H5 type errors high-stakes & early-catchable (NEW)**; H6 human evidence (obtained).

## Contributions (anchor — ADSR §3): C1 axis×σ observability map + human early→final validation; **C2 ADSR (main method — reallocation not selection)**; **C3 prompt-type match as early-decidable axis via learned EVPD (NEW)**; C4 compute–quality Pareto over BoN-k/Full-BoN/random/raw-ETP/learned-verifier; **C5 lyric as a first-class late-observable axis, evaluated only on lyric-bearing vocal prompts (no instrumental-sentinel pollution)**; C6 RL post-training boundary result.

## Method ADSR (anchor — ADSR §4)
- Decisions: **RESTART** (terminate trajectory, launch NEW independent seed — not a rollback/repair) / **DEFER** (continue to later σ before deciding) / **CONTINUE**.
- Decision logic priority: (1) if EVPD predicts final-type ≠ requested-type with high confidence → **restart** (gross type error); (2) elif early-quality clearly low & late-axis risk low → restart; (3) elif semantic/lyric content risk high/uncertain → **defer**; (4) else continue.
- **Two distinct learned components** (§4.2): (a) **Quality verifier (lightweight)** — scalar early features (axis scores, within-prompt rank, slope, risk, metadata); ridge/GBDT/LambdaMART; near-saturated (ridge NDCG ~0.995); capacity is NOT the bottleneck. (b) **Early Vocal-Presence Detector (EVPD) — learned AUDIO model** (small CNN / fine-tuned pretrained audio encoder) predicting FINAL vocal presence from the EARLY Tweedie-clean mel-spectrogram; warrants a real neural net because early-σ audio perception under heavy noise is a genuine learning problem and OOD for off-the-shelf detectors. prompt-type match = compare EVPD prediction to requested type.
- **Compute accounting (§4.5):** matched expected total NFE, no optimistic accounting (partial cost to σ_c + surviving full cost + restart new-seed cost + deferred-continuation cost). **Offline-first:** validate ADSR offline on the existing 4096-candidate pool ("restart" = draw the next independent pool candidate), then a small real-generation confirm.

## Data plan (anchor — ADSR §5)
- New fields: **final vocal-presence label** (via source separation Demucs/Spleeter vocal-energy ratio, or SVD model; Whisper `no_speech_prob` only as coarse pre-filter). **Relabel existing 4096 candidates** retroactively.
- **Lyric-bearing subset:** 200–300 lyric-bearing vocal prompts; English clean core; ≥3 lyric lines; report separately: clean-English-core / broader-lyric-bearing-vocal / multilingual-or-thin-lyric stress arm. **Never mix instrumental prompts into headline lyric metrics.** Split by prompt_id, never candidate_id.

## Experiments (anchor — ADSR §6): **E1** axis×σ observability matrix (fix lyric stratum first; vocal-presence & lyric as separate rows; expect vocal-presence-onset ≪ lyric-onset); **E2** human early→final validation (license for restart; incl. early vocal-presence listening); **E3** EVPD + prompt-type-error study (NEW; AUC, onset σ, type-error prevalence, type-match rate, disentangle lyric-zero into type-errors vs content-failures); **E4** raw pruning & same-compute baselines (raw ETP vs BoN-4 — known delta ≈ 0.0036, cannot be the headline); **E5** learned quality verifier; **E6** ADSR main method (restart/defer/continue; with/without EVPD branch; strict expected-compute); **E7** lyric-focused deferred eval (lyric-bearing vocal; lyric-decidability onset vs ASR-transcribability onset); **E8** human spot-check (32–64 blind A/B; human overrides reward); **E9** robustness + cross-backbone (Stable Audio Open, Phase-1-parallel, graceful fallback, does NOT gate submission).

## Baselines (§7): Full BoN-8, BoN-4, random prune/restart, raw ETP, learned-verifier selection, **type-match restart**, **ADSR**. Boundary (not main): M-FixedWin-PRM, M-Section-PRM, R8a/R8b.

## Success / failure (§8–9): min = ADSR beats same-compute BoN-k & random restart on robust/common; method = preserves common quality + improves semantic/lyric preservation + improves prompt-type-match via EVPD; strong = approaches Full-BoN-8 at lower compute; top = beats Full-BoN-8 at matched compute. Failure routing per §9 (e.g. ADSR ≤ BoN-4 → fall back to axis-observability + trajectory-analysis paper; vocal-presence not early → demote type-match to later σ, report onset honestly).

## EVIDENCE STATUS (critical — get this right; do NOT overclaim)
- **Foundation evidence already exists (repurposed):** H1/H2 early-quality persistence (Phase A headroom `delta_sigma_bon_vs_base=0.7549`; H2 STRONG_PASS on 128 prompts; Track B globalness 0.861); Track A raw-ETP pruning (Schedule A **0.9864** @ 0.500 compute, regenerated 2026-06-04 on the lyric-fix dataset, was 0.9858 on 2026-05-28; bottom-prune σ=0.7 false-negative 0.0195); lyric axis now scored EN-vocal-only (**0.682** ETP@50, n=282, 248/282=88% signal; instrumental 1.0 sentinel masked, non-EN excluded — `prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md`); C1 RL boundary (no clear first-wave common-metric gain).
- **NOT yet run (ADSR is forward-looking for these):** E3 **EVPD is NOT trained**; E6 **restart/ADSR NOT run** (only offline-simulatable on the 4096 pool); vocal-presence labels **not yet derived**; H2b presence/content split **unmeasured**; cross-backbone not started. The reframed proposal is therefore a **plan-stage proposal for the new ADSR method**, anchored on the existing ETV/Track-A/H2/human-listening evidence as foundation — state this honestly. Do NOT claim ADSR results that don't exist.
- ETV pruning (Track A) is now a **strong baseline (raw ETP)**, not the headline.

## Claims to AVOID (anchor — ADSR §14): music quality always globally determined; sections never matter; lyric evaluable over all prompts; ADSR has distribution-free guarantees; ADSR universally generalizes to all flow models; vocal presence always trivially detectable at any σ; RL post-training does not work.

## Versioning & doc-durability (MANDATORY)
- This is a **NEW major version: v4.0 (ADSR)**. Stamp each reframed file `v4.0 ADSR reframe, 2026-06-04`.
- ETV-era files are archived at `orbit-research/archive/etv_pre_adsr_20260604/` — reference, do not lose. Preserve each file's revision-history footer; APPEND a "v4.0 ADSR reframe (2026-06-04): ETV→ADSR pivot per ADSR_Research_Plan_FINAL_EN_2026-05-29.md" entry.
- Keep all still-valid implementation contracts (gate policy `configs/eval/gate_v2.yaml.draft`, reward definitions, prompt-level splits, calibration, compute accounting, the canonical reward set `orbit-research/trajectory_candidate_dataset.jsonl`). Reframe the METHOD, not the infra.
- The lyric-fix corrections (R2) stay: 0.682 EN-vocal n=282, 0.9864, cross-prompt-not-cross-content, per-specificity-stratum.

## Per-file role (what each canonical file must become)
- `refine-logs/FINAL_PROPOSAL.md` — flagship ADSR proposal: abstract/core-sentence, reframed problem (when-to-continue + axis observability + presence/content), 6 claims C1-C6, ADSR method (restart/defer/continue + EVPD + 2 components), 9 experiments E1-E9 (mark which are run vs planned), baselines, success/failure, anti-overclaim (§14 list), evidence-status honesty, STOP-A checklist.
- `refine-logs/FINAL_PROPOSAL_SHORT.md` — 1–2 page ADSR short (currently stale M-PRM — full rewrite): thesis, ADSR method, C1-C6, headline numbers (foundation only), what's-new (EVPD/restart/presence-content), anti-overclaim.
- `refine-logs/METHOD_SPEC.md` — ADSR implementation contract: restart/defer/continue logic, EVPD (audio model, label derivation, onset σ), quality verifier, decision thresholds, compute accounting §4.5, offline-first protocol, data fields incl. vocal-presence labels. Keep valid reward/gate/split infra; mark M-PRM/ETV-pruning sections as superseded boundary.
- `refine-logs/EXPERIMENT_PLAN_EXEC.md` — E1-E9 exec plan with go/no-go gates (Phases 1-7 per ADSR §11), splits, compute budget, offline-first ADSR simulation, EVPD training, cross-backbone parallel.
- `orbit-research/CONTROL_DESIGN.md` — ADSR baselines/controls (§7): type-match restart, random restart, raw restart, axis-deferred; EVPD vs off-the-shelf detector; two-factor ablation (axis-awareness × restart-reallocation); EVPD-branch on/off.
- `orbit-research/ASSUMPTION_LEDGER.md` — replace/append ADSR hypotheses **H1–H6** + claims **C1–C6** as the paper-bearing rows (keep ledger row IDs / boundary rows; add an "2026-06-04 ADSR Pivot Addendum").
- `CLAUDE.md` + `AGENTS.md` — current-state snapshot reframed to ADSR (stage, method stack = ADSR, foundation evidence, what's planned vs done, the v4.0 pointer + ADSR plan path).
