# SURPRISES AND LEADS (mandatory — antidote to over-narrowing)

> Prior project's biggest finding (seed-only restart ≈ BoN; mechanism = conditioning, not reseeding)
> was buried as a footnote. Do NOT repeat. Log surprises prominently and immediately.

## Open leads (seeded before any new data — to be tested on spare compute)
- L001 (hypothesis, unverified): instrumental-leak online null may be ACTION_UNAVAILABLE rather than
  ceiling-saturated — Batch-3 instrumental interventions were ≈0. Cheap probe: large-N BoN on E2
  instrumental-risk + anti-vocal intervention ladder; classify per RQ4. Could reframe the paper.
- L002 (hypothesis): does the seed-recoverable vs low-p split PREDICT which prompts BoN
  reward-selection still gets wrong? Links decomposition to a practical reward-selection failure.
- L003 (hypothesis): minimal-intervention — smallest condition edit that escapes a basin —
  motivates a learned-intervention follow-up.
(See EXPLORATION_BACKLOG.md for the ranked cheap-probe queue.)

## Confirmed surprises
(none yet — program just started)

## Confirmed observations
- S001 (2026-06-21, PI-observed + DATA-CONFIRMED): **pretrained ACE-Step has a vocal-generation
  prior** — it leaks vocals even on explicit "pure instrumental, no vocals" prompts. Evidence:
  7/40 trivial-instrumental sanity controls leaked vocals, and **7/7 are confirmed by BOTH Demucs
  (≥0.18) AND PANNs (≥0.065)** → not a detector artifact. PI note: instrumental prompts (esp.
  genres like hip-hop) trend toward generating human voice. **Why it matters:** this is the
  mechanism behind instrumental-leak; it sharpens RQ4 — the open question becomes whether
  anti-vocal CONDITIONING interventions (I1/I3/I_strong ladder) can suppress the prior
  (ACTION-AVAILABLE) or not (ACTION-UNAVAILABLE basin). The instrumental-dissociation workstream
  measures exactly this. Also pre-validates the detector-independence defensive probe.
  Hypothesis (unverified): instrumental-leak severity is GENRE-dependent (PI: hip-hop worse).
- S002 (2026-06-21, DATA, candidate headline — HYPOTHESIS, unverified): **the seed-recoverability
  (p_hat) of the failure mode dissociates by direction and may EXPLAIN the frozen Batch-3 direction
  split.** E2-tail BoN N=256 (canonical Demucs label, 8192 draws): vocal-miss prompts median
  p_hat=0.055 (min 0.012; 9/17 ≤0.10) = RARE_BUT_RECOVERABLE; instrumental-leak prompts median
  p_hat=0.36 (min 0.195; none ≤0.10) = SEED_RECOVERABLE. **n_zero_clean=0** → no STRONG_ESCAPABLE_BASIN
  (p≈0) at N=256 in either direction. Hypothesis: Batch-3 found conditioning helped VOCAL (rare →
  reseeding expensive → conditioning adds draws) and was NULL on INSTRUMENTAL (seed-recoverable →
  reseeding already cheap → conditioning adds nothing). If it holds, the regime decomposition
  PREDICTS where conditioning beats reseeding. NEEDS: detector-independence (human audit; PANNs
  proxy unusable, see D010) + paired-intervention data (V3/I_strong, running). Could be a headline.
- S002 UPGRADED (2026-06-23, MEASURED — paired intervention data): the p_hat dissociation + the
  intervention test now COHERE. **Vocal-miss (rare, p~0.05): V3 conditioning Δp=+0.688, 17/17
  improved** (rarest 0.012→0.66). **Instrumental-leak (seed-recoverable, p~0.36): I_strong anti-vocal
  Δp=+0.006, ~null** (9/15, several worse). This MEASURES the mechanism behind the frozen Batch-3
  direction split: conditioning beats reseeding exactly where the failure is rare; null where
  seed-recoverable. Candidate HEADLINE: "the failure's seed-recoverability predicts whether
  conditioning or reseeding is the right tool." Caveat: canonical Demucs label; detector-independence
  (human audit) still pending for the rare-vocal failures. Artifacts: PAIRED_INTERVENTION_RESULTS.json.

## S002 CORRECTION (2026-06-23, post-Codex-review — BLOCKED as headline)
Independent Codex review (CODEX_REVIEWS.md) BLOCKS S002 as a headline. Corrections:
- Over-reaching causal wording ("predicts/explains/beats") RETRACTED. Honest descriptive version:
  "In this Demucs-labeled exploratory slice, vocal-tail prompts had low-but-nonzero plain-seed clean
  rates and V3 greatly increased per-draw clean rate; instrumental prompts had higher plain-seed clean
  rates and I_strong was near-null." (No causal/headline claim.)
- "Conditioning beats reseeding" is UNDEFINED here: at-least-one-clean BoN is already SATURATED
  (vocal S_128=0.978, S_256=0.997; instrumental earlier) — a fair utility metric (clean-yield per
  FLOP / expected-draws-to-first-clean) is required.
- V3 (guidance+structure) and I_strong (text-rewrite+drop-lyrics) are NOT symmetric causal tests;
  "same semantic request" is not established → cannot attribute the asymmetry to seed-recoverability alone.
- Detector-independence unverified (Demucs-only; PANNs proxy over-fires; agree 0.515) → vocal/instrumental
  claims need human audit (queued) + a valid 2nd detector.
- VALID & reproducible: n_zero_clean=0 at N=256 (clean frozen ledger md5 a0509fad..., dedup); p_hat
  medians (vocal 0.055 / instr 0.36) on the Demucs label. These stay EXPLORATORY facts.
