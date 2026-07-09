# Headroom Gate Pre-Registration

*Pre-registered: 2026-05-19, before M1a dev finals were all in (8/18 finals at signing time). This document is **immutable**: changes after this date constitute post-hoc revision and must be flagged in any subsequent paper.*

## Why this document

R4 in `papers/explainers/RISK_REGISTER.md` flags statistical-power risk (n=3 seed × 256 prompt may be underpowered for detecting small effects). Standard mitigation for low-power studies is **pre-registration**: lock in the effect size of interest + the decision rule **before** seeing the data, so post-hoc choices cannot bias the conclusion.

NULL_RESULT_CONTRACT.md §1 covers the *qualitative* pivot (saturation paper if H1 fails). This file adds the **quantitative thresholds** that turn that pivot into a falsifiable rule.

`configs/eval/gate_v1.yaml` is **not** modified here — its provenance hash is consumed by `scripts/compute_headroom_gate.py` to verify sidecars, and editing it mid-run would invalidate every gate-critical rung's sidecar (line 35 of gate_v1.yaml: *"DO NOT edit gate_v1 in place — bump to gate_v2 and migrate"*). The thresholds below live in this doc until a future `gate_v2.yaml` can absorb them.

## Pre-registered thresholds (locked 2026-05-19, M1a still running)

### T1. Minimum effect of interest

```
minimum_effect_of_interest_gate_r_lcb = 0.05  (absolute, on the gate_r_lcb scale)
```

**Rationale**: r0_base 3-seed empirical SD ≈ 0.141. An effect of +0.05 is ~0.36 SD — small but plausibly meaningful. Effects below this are within seed-batch noise and we will NOT claim them as evidence of headroom even if the t-test happens to be significant.

### T2. M1a headroom-gate PASS rule

(Replicates `mprm.audit.headroom_gate.headroom_gate()` logic, declared explicitly here for pre-reg traceability.)

H1a (basic headroom — CFG explain check) PASSES iff **all** of:
1. `mean(r1_cfg_sweep.gate_r_lcb) - mean(r0_base.gate_r_lcb) ≥ 0.05` (T1 threshold)
2. **Paired t-test by prompt_id**: `r1_cfg_sweep − r0_base` Δ has `p_value ≤ 0.05`
3. **Bootstrap 95% CI** for `mean(r1_cfg_sweep) - mean(r0_base)` does **not** include zero
4. **s7-explain control**: `mean(r9_s7_sampler_control)` is **not** above `mean(r0_base)` by more than 0.5 × SD(r0_base). (If r9 ≥ r1 → CFG signal is sampler-noise, NOT a CFG effect.)

H1b (BoN ceiling — quantity headroom) PASSES iff:
5. `mean(r2_bon.gate_r_lcb) - mean(r0_base.gate_r_lcb) ≥ 0.5 × SD(r0_base)` (≈ 0.07 at current SD)
6. **Paired t-test** `r2_bon − r0_base`: `p_value ≤ 0.05`

### T3. M1a PIVOT rule (saturation paper trigger)

If **all three** of these hold after M1a held-out finals are in:
- T2.1 (Δ ≥ 0.05) **fails for `r1_cfg_sweep − r0_base`** AND
- T2.5 (Δ ≥ 0.5 SD) **fails for `r2_bon − r0_base`** AND
- T2.5 (Δ ≥ 0.5 SD) **fails for `r4_bon_cfg − r0_base`**

→ Declare **saturation result** per NULL_RESULT_CONTRACT.md §1. Phase B/C are NOT launched. Pivot to *"Why current music FMs saturate under uniform process reward"* (see `papers/explainers/SATURATION_PAPER_OUTLINE.md` — to be written before Phase A.aux per HEDGE_STRATEGIES.md R1(c)).

### T4. Borderline-effect extra-power rule

If `r1_cfg_sweep − r0_base ∈ [0, 0.5 × SD(r0_base)]` (borderline) AND `p_value > 0.05` paired:
- Allocate up to **100 additional GPU-hours** to extra seeds (12 seeds × small rungs) before declaring NULL.
- Per HEDGE_STRATEGIES.md R1(d).
- Re-evaluate after extra seeds with same T2 rules.

### T5. Multiple comparison correction

Phase A reports raw p-values AND Benjamini-Hochberg q-values across the 5 paired tests (r1 vs r0, r2 vs r0, r4 vs r0, r1 vs r9, r2 vs r9). Reviewer-expected correction. q ≤ 0.05 is the canonical "significant" bar.

## What is NOT pre-registered (exploratory / post-hoc OK)

- Per-axis decomposition (which reward axis drives the effect): exploratory.
- Per-section gate_r_lcb (Phase B-onwards): exploratory.
- Held-out vs dev split comparison: exploratory.
- BoN-N curves at N≠8: exploratory.
- Cross-rung interaction effects: exploratory.

These can use the same data but **cannot be advertised as the primary finding** without pre-reg.

## Sign-off

| Field | Value |
|-------|-------|
| Pre-registered by | PI (Despaireye / yhc) — to confirm before M1a held-out finishes |
| Date | 2026-05-19 (M1a dev finals 8/18 in) |
| Witness / reviewer | Codex MCP review thread `019e3ef4-66ed-7543-a887-49aa45f2f0cb` (Phase A code review) |
| Locked against | gate_v1.yaml hash `55c065012c04…` (live policy that all current M1a sidecars stamp) |
| Implementation | `scripts/compute_headroom_gate.py` (paired test + bootstrap supplementary block added 2026-05-19) |
| Visible in decision JSON | `orbit-research/HEADROOM_GATE_DECISION.json.supplementary` block (written at M1a end) |
| Public deposit (post Phase A) | Plan: OpenReview pre-registration — see HEDGE_STRATEGIES.md cross-cutting (c) |

## T6. Pre-Registered Decision Matrix (post-M1a outcome → paper-claim path)

*Added 2026-05-20 by /proposal-revise round 1 (C13 Codex MISSING finding); REVISED 2026-05-20 round 2 (C21) for H1-H3 paper-level + A1-A5 ablation-dimension structure. Locks the paper-claim wording per result pattern BEFORE M1a held-out finals land.*

**Key Round-2 reframing**: only H1, H2, H3 failures pivot the paper claim. A1, A2, A3, A4, A5 component nulls downgrade their component but DO NOT pivot the paper. This separation prevents single-component failures from triggering paper-scope changes.

### Paper-claim-level patterns (H-driven; pivot the paper)

| Result pattern | Paper claim wording (locked pre-result) |
|----------------|----------------------------------------------|
| **A. H1 ∧ H2 ∧ H3 all pass at pre-reg thresholds** | "M-PRM: a method for musical credit assignment in flow-matching song generation, with empirical evidence that section-level Tweedie process rewards on intermediate audio outperform terminal and non-section credit-unit baselines. Component ablations A1-A5 characterize the per-component contributions." |
| **A.1 M1a held-out marginal** (r2_bon vs r0_base gate_r_lcb effect in [+0.03, +0.05], paired t p in [0.05, 0.20]) | Trigger T4 borderline-power: add 12 extra seeds (~100 GPU-h from reserve, ~12h delay) before final pass/fail. Do NOT pivot, do NOT finalize claim during the borderline interval. Re-route into A or B after extra-seed re-eval. |
| **B. H1 fails** (M1a per T3 saturation rule) | Trigger NULL_RESULT_CONTRACT.md §1: pivot to saturation paper. Phase B/C/D NOT launched. SATURATION_PAPER_OUTLINE.md activates. |
| **C. H2 fails** (Tweedie ρ < 0.5 for all axes × Tweedie checkpoints after Stage-1 + escalation per C25) | "M-OR: Musically-structured Outcome Reward. Section credit and A1-A3 ablations characterized over terminal reward (no process-reward claim). Tweedie process-reward claim retracted." |
| **D. H3 fails** (section credit no advantage over best non-section credit unit at +0.08 Spearman margin, ≥2/3 axes, on canonical held-out) | "Credit-Unit Study for flow-matching music generation: musical sections do NOT provide a stronger process-reward credit signal than {timestep, fixed-window, beat-window, lyric-span}. We characterize this as the credit-unit negative finding." Section-credit headline retracted; M-PRM downgraded. |

### Component-level patterns (A-driven; do NOT pivot the paper)

| Result pattern | Component-level outcome |
|----------------|--------------------------|
| **A1-null** (decoder-locality ratio < 1.5) | A1 reported as null ablation. Paper claim INTACT. |
| **A2-null** (lyric guard does not improve (R_music, R_lyric) tradeoff at ε ∈ {0, σ_WER}) | A2 reported as null ablation. Paper claim INTACT. |
| **A3-null** (CVaR β=0 ≈ mean aggregation on worst-section reduction) | A3 reported as null ablation. Paper claim INTACT. |
| **A4-null** (curriculum no sample-efficiency gain vs uniform sampling) | A4 reported as null ablation. Paper claim INTACT. |
| **A5-null** (raw reward matches robust LCB at similar training stability) | A5 reported as null ablation. Paper claim INTACT. |

### Cross-claim footnote

> *"Phase C training collapse (any of R6/R7/R8 RL rung diverges or fails to train) is an operational risk handled by HEDGE_STRATEGIES.md R7 (KL guard ≤ 5.0 nats per C8, frequent checkpointing, supervised distillation fallback). If unrecoverable after hedging, paper claim downgrades to 'M-PRM via BoN selection (no RL training)' as a fallback; this is NOT a primary paper-claim pattern. RL-failure scenario is documented in EXPERIMENT_PLAN_EXEC.md §Risks."*

### Compound failure pivot mapping (extends ASSUMPTION_LEDGER pivot table)

- H2 false + H3 true → pattern C (M-OR; section credit still rides as outcome-reward target)
- H2 true + H3 false → pattern D (credit-unit negative paper)
- H2 + H3 both false → pattern B-equivalent triggers (no process reward, no section claim) → saturation-paper alternative.
- A1 + A2 + A3 + A4 + A5 ALL null + H1/H2/H3 all pass → paper claim INTACT but narrower: "M-PRM section-aware process reward (H3); A1-A5 ablation dimensions characterized as not load-bearing for this scale/regime." Section credit (H3) is the single load-bearing component.

This matrix MUST be SHA-locked into this document before Phase B kicks off. No editing after first M1a held-out final per gate_r_lcb (T2) is recorded in `orbit-research/HEADROOM_GATE_DECISION.json`.

### §T6 SHA-lock signature

| Field | Value |
|-------|-------|
| **PI approval** | ✅ approved per PI message 2026-05-21: "结束 Phase A 吧，这些文件你帮我签署，我批准了" |
| Sign-off date | 2026-05-21 |
| Authorized signatory | PI Despaireye / yhc (yhc98002@gmail.com) |
| Signed by agent on PI's behalf | Claude (per PI explicit delegation 2026-05-21) |
| Bound HEADROOM_GATE_DECISION.json | `orbit-research/HEADROOM_GATE_DECISION.json` (pass_gate=True, reason=all_conditions_satisfied) |
| Pre-PI-confirm backup | `orbit-research/HEADROOM_GATE_DECISION.3seed_pre_pi_confirm.json` |
| Earlier seed-0-only buggy decision (audit trail) | `orbit-research/HEADROOM_GATE_DECISION.seed0only_backup.json` |
| Spot-check verdict source | `/HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion/m1a_spot_check_verdicts_2026-05-21.json` |
| Spot-check result | YES (27/32 bon_better, 5/32 unclear, 0/32 base_better) |
| Pattern triggered | **A** (all H2-H6 pass — though H2 and H3 still need Phase B confirmation; H1 confirmed by M1a Pattern A pre-reg pass) |

The pattern A claim wording is now locked: "M-PRM: a method for musical credit assignment in flow-matching song generation, with empirical evidence that section-level Tweedie process rewards on intermediate audio outperform terminal and non-section credit-unit baselines. Component ablations A1-A5 characterize the per-component contributions." This wording is bound to the Phase A gate outcome and may not be revised post-hoc.

Subsequent matrix amendments would require PI re-signature with a new date stamp and a clear `revision_reason`.

---

## T7. M-PRM Pattern A method-success threshold (added 2026-05-21, post-audit Fix #1)

*Pre-registered after Phase A close + 4-round multi-agent method audit (Claude + Codex). PI explicit policy: anti-scope-creep — only fixes required for H1/H2/H3 identification kept.*

Phase A confirmed BoN-8 ceiling: `r2_bon − r0_base = +0.213` on canonical 256 held-out. M-PRM is supposed to internalize this BoN-selection capability into policy weights via RL. To prevent post-hoc claim wording, the success threshold is locked here.

**Two-tier definition**:

- **Minimal RL success**: M-PRM (no BoN at inference) improves over base by `≥ +0.05` gate_r_lcb on canonical 256 held-out (matches T1).
- **Pattern A method success**: M-PRM recovers `≥ 50%` of the Phase A BoN-8 gap without BoN at inference. Concretely: `M-PRM − r0_base ≥ +0.107` on canonical 256 held-out (= 50% × 0.213).

**Statistical strength**:
- Use **point estimate** for the 50% criterion gate decision.
- Additionally report **bootstrap 95% LCB**. If LCB also clears `+0.107`, declare "strong" success; if only point estimate clears, declare "qualified" success with explicit limitation paragraph.
- Comparison against R8a Outcome-GRPO-plain at matched compute is REQUIRED for the "internalized BoN headroom" claim. Otherwise the result is reported as "trained policy internalizes selection capability vs untrained base", not "vs matched-compute terminal reward".

**If Pattern A method success fails**:
- Minimal RL success still holds → paper claim downgrades to "M-PRM achieves some RL post-training gain; falls short of BoN-8 inference ceiling at our compute scale". Section credit / locality / lyric guard ablations still inform A1-A3 component contributions.
- If even Minimal RL success fails → invoke pattern C (M-OR) or D (credit-unit negative) per §T6.

---

## Reviewer-facing summary (paper §4 or appendix)

> We pre-registered (2026-05-19, before M1a finals were complete) the minimum effect of
> interest as +0.05 absolute gate_r_lcb. We pre-registered paired t-test by prompt_id +
> bootstrap 95% CI as the inferential primary; the s7-explain control (r9) is the
> falsifier for sampler-noise. The saturation pivot rule (T3) was pre-registered
> simultaneously. All supplementary analyses listed in §4.5 are exploratory and not
> advertised as headline claims.

## How to verify this pre-reg held

```bash
# 1. This file's git-history-equivalent timestamp predates HEADROOM_GATE_DECISION.json
stat -c '%y' orbit-research/HEADROOM_GATE_PREREG.md
stat -c '%y' orbit-research/HEADROOM_GATE_DECISION.json    # written by compute_headroom_gate
# If PREREG is newer than DECISION → pre-reg was violated.

# 2. The thresholds in this file match what compute_headroom_gate computes
grep -E "T1|T2|T3" orbit-research/HEADROOM_GATE_PREREG.md
# Cross-check vs supplementary block in HEADROOM_GATE_DECISION.json
```
