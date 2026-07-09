# Research Decision Log — Phase B.1 Tweedie Reliability (formal run)

> **Superseded status (2026-05-23):** This decision log captured the original
> 64-prompt AMBIGUOUS routing. PI revised the near-threshold rule and the
> 128-prompt merged verdict is now `STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES`.
> Use `orbit-research/PHASE_B1_H2_CONCLUSION_2026-05-23.md` for the current H2
> decision. The text below is retained as audit history.

- **Diagnostic / run ID**: `run_2026-05-23T16-30Z_phase_b1_4d004a4c` (per `orbit-research/DIAGNOSTIC_RUN_REPORT.md`)
- **Result pattern**: positive-but-classified-as-AMBIGUOUS (underlying data strongly supports H2; AMBIGUOUS triggered by threshold-band rule on 2 near-threshold pairs out of 17 surviving primary pairs)
- **Affected hypotheses**: **H2** (Tweedie reliability — `FINAL_PROPOSAL.md` §6) — strongly supported by the underlying data; tier classification rule treats the result as inconclusive pending threshold-rounding resolution.
- **Failure type**: `inconclusive` (under literal rule) — NOT mechanism issue; NOT implementation/config issue; NOT central-paper-breaking; NOT benchmark/headroom issue.
- **Decision**: **PI decision required** (do NOT auto-route). See three documented options below.
- **Local patch target**: none — the configs + driver + frozen SHAs are all internally consistent; the AMBIGUOUS verdict is from the scientific rule, not from a code-level mismatch.
- **Proposal status update**: **unchanged** — `FINAL_PROPOSAL.md` H2 stays in its current pending state (paper-level claim) until PI resolves the AMBIGUOUS verdict.
- **Proposal revision needed**: **no** (none of the three options below changes the paper-claim structure).
- **Next skill hint**: PI decision (see options) → if A, re-run `/experiment-bridge` with 128-prompt expansion config; if B, manual amendment to `H2_VERDICT.json` + reinvoke `/diagnostic-to-review` from Phase 3; if C, `/proposal-revise` SUPPORTED_PASS-equivalent wording.
- **Human decision required**: **yes**.

## Rationale

The formal Phase B.1 run completed cleanly (0.32 GPU-h, run integrity audit verdict PASS). The scientific outcome under the PI-locked tiered rule is `tier=AMBIGUOUS` per `_classify_tier` priority order (driver step 2: `near_threshold_primary` non-empty → AMBIGUOUS).

The underlying data, however, is much stronger than the AMBIGUOUS tier suggests:

- 17 surviving primary pairs (target: ≥ 2)
- Coverage across both early σ ∈ {0.9, 0.8} and middle σ ∈ {0.7, 0.6}
- 6 of 7 reward axes have at least one primary survival
- Monotonic σ → ρ curves on almost every axis
- Sample-dependent emergence empirically supported (PI's pre-launch hypothesis) — top-Q4 vs bot-Q1 separation grows monotonically from σ=0.9 (+0.65) to σ=0.5 (+2.17) on aesthetic_pq

The AMBIGUOUS tier is triggered by **2 isolated near-threshold pairs** in the [0.50, 0.55] band:
- `aesthetic_pc @ σ=0.7 ρ=0.5109`
- `section_coherence @ σ=0.8 ρ=0.5140`

These 2 pairs are NOT load-bearing for the STRONG/SUPPORTED classification (excluding them, the result still has 15 primary pairs + early + middle coverage = STRONG_PASS-equivalent).

The PI-locked rule's intent was: "if STRONG/SUPPORTED classification would HINGE on a threshold-rounding-sensitive ρ value, escalate". A strict literal reading triggers AMBIGUOUS here. A spirit-of-the-rule reading (does classification hinge on those pairs?) would give STRONG_PASS.

## Three options for PI decision

### Option A — Expand to 128 prompts (literal rule's escalation route)

- **What**: Re-run Phase B.1 with the same 6-σ curve on an additional 64 dev prompts (disjoint from formal 64 + σ-cal 16; seed=20260524 per current config), giving a total of 128 prompts. Re-apply the tiered classification.
- **Cost**: ~0.5 GPU-h additional (linear extrapolation of 0.32 GPU-h on 64 prompts).
- **What it resolves**: If aesthetic_pc @ σ=0.7 and section_coherence @ σ=0.8 are genuinely near-threshold due to small-N noise on 64 prompts, expansion shifts them either firmly above or firmly below ρ=0.5, breaking the AMBIGUOUS verdict.
- **Risk**: The two near-threshold pairs may stay near-threshold under more data, leaving the AMBIGUOUS verdict persistent. The escalation route does NOT auto-add σ=0.1 and does NOT change σ points; only sample size grows.
- **Required artifact**: a `PHASE_B1_RELIABILITY_PROMPTS_EXPANSION.json` (currently TODO in `phase_b1_reliability.yaml escalation.ambiguous.extra_prompts_source`).
- **Recommended if**: PI wants the literal rule honored without override.

### Option B — PI override to STRONG_PASS

- **What**: PI explicitly amends `runs/phase_b1_reliability/H2_VERDICT.json` to set `tier=STRONG_PASS_PI_OVERRIDE` (or equivalent) with a written rationale citing: 17 surviving primary pairs, robust early + middle coverage, sample-dependent emergence pattern, and the observation that classification does NOT hinge on the 2 near-threshold pairs.
- **Cost**: zero GPU; minutes of PI time.
- **What it resolves**: The Phase B.1 verdict becomes STRONG_PASS (paper-bearing), enabling Phase 3 `/result-to-claim` + Phase 4 `/auto-review-loop` to proceed for the H2 claim chain.
- **Risk**: Paper reviewers may push back on the override unless the rationale is documented prominently (e.g., in METHOD_SPEC or the paper's reliability section). Codex red-team in Phase 4 will likely surface this.
- **Recommended if**: PI is confident the underlying evidence is robust and the literal rule was overly strict.

### Option C — Accept AMBIGUOUS, proceed with σ-restricted set (SUPPORTED_PASS-like)

- **What**: PI declares the run "SUPPORTED-equivalent": acknowledges that the literal rule says AMBIGUOUS but uses ONLY the empirically-supported σ checkpoints (e.g., σ ∈ {0.7, 0.6} where most axes have ρ ≫ 0.5) for downstream M-PRM training. Skip 128-prompt expansion.
- **Cost**: zero GPU; this is a scoping decision.
- **What it resolves**: M-PRM training in Phase C can use σ ∈ {0.7, 0.6} (well-supported empirically) without claiming the very-early σ=0.9 emergence (paper paragraph wording).
- **Risk**: Paper claim is narrower than what the data supports; sample-dependent emergence finding (σ=0.9 top-Q4 vs bot-Q1 separation) gets demoted to an "exploratory" observation in the paper.
- **Recommended if**: PI prefers conservative claim scope without burning additional GPU.

## Boundaries surviving this stage

- gate_v1.yaml UNTOUCHED ✓
- gate_v2.yaml.draft stays `.draft` (no activation) ✓
- Phase C / M-PRM training NOT launched ✓
- Phase B.2 (R11 segmentation + locality probe) NOT in scope ✓
- σ=0.1 NOT brought into primary ✓
- No silent override of the tier classification — driver-emitted verdict is preserved verbatim in `H2_VERDICT.json` ✓

## What this skill (`/diagnostic-to-review`) does next, per the spec

Per the `/diagnostic-to-review` workflow:
- **Phase 2 (this document + RESULT_INTERPRETATION.md) — COMPLETE**.
- **Phase 3 (`/result-to-claim`) — SKIPPED** because tier=AMBIGUOUS is NOT a paper-bearing claim verdict yet. Per the skill table: "For AMBIGUOUS / FAIL, route per RESEARCH_DECISION_LOG without invoking `/result-to-claim`."
- **Phase 4 (`/auto-review-loop`) — SKIPPED** because Phase 3 did not run.
- **Phase 5 (PIPELINE_SUMMARY.md)** — write summary with `status: awaiting_human_continue` and `next_action` describing the three-option PI decision.

PI cannot be silently chosen for; the routing genuinely requires human judgment between A/B/C.
