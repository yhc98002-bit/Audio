# gate_v2 + Phase B.1 formal-run policy FREEZE — 2026-05-23

## Status

**FROZEN for Phase B.1 formal launch.** This file records the PI-approved policy
state at the moment of formal Phase B.1 launch (autonomous AFK execution
2026-05-23). Any subsequent edits to these files invalidate the launched run's
provenance hash.

## Files frozen

| Path | SHA-256 | Role |
|---|---|---|
| `configs/eval/gate_v2.yaml.draft` | `34db933b67d06f3acc3780e70b2f492a20d685ef710777fc81eaffba1d2806e9` | Gate evaluator policy. Still `.draft` — Phase B.1 binds via path, not via promotion to `.yaml`. |
| `configs/runs/phase_b1_reliability.yaml` | `365d67c9f605fb99704c2461930bca6d5c48e59f9584a2bf1577d4f503d1d28a` | Phase B.1 run config (64 prompts, 6 σ curve, tiered H2, escalation). |
| `scripts/phase_b1_reliability.py` | `4d004a4cb19cb4132f2ff1c21df3f87796dbf1f1ba83a88708cf99360590ded4` | Phase B.1 driver. Re-frozen 2026-05-23 after Codex audit CRITICAL fix: approval-string check `!= "PI_APPROVED"` → `not startswith("PI_APPROVED")` to accept dated approval tags like `PI_APPROVED_2026-05-23`. Prior SHA `690bd5af...` superseded. Unit tests 4/4 PASS post-fix. |

## PI approval chain

1. **K=3 design (superseded)**: PI-approved morning 2026-05-22; retired same day in favor of curve design.
2. **σ-curve design**: PI-approved afternoon 2026-05-22 as PENDING_PI_REVIEW for the curve and pass rule.
3. **Tiered rule + smoke + CFG-boundary**: PI directive 2026-05-23 replaced single-rule with STRONG/SUPPORTED/AMBIGUOUS/FAIL tiers; required end-to-end smoke before launch; required figures to mark CFG-active → cond-only boundary between σ=0.6 and σ=0.5.
4. **Smoke PASS**: `runs/phase_b1_reliability_smoke/` (1 prompt `dev_0209` × 6 σ; 347.9 s = 0.097 GPU-h; all 4 figure JSONs with `_cfg_branch_metadata`). H2 tier=FAIL expected for n=1.
5. **Codex 4-item check**: thread `019e5078` → 1 PARTIAL + 3 PASS; flagged early-only-≥2-primary edge case + late-pair near-threshold triggering AMBIGUOUS.
6. **Bug fix**: `_classify_tier` priority order reworked; near-threshold band restricted to primary pairs only; early-only case explicitly AMBIGUOUS. Unit tests 10/10 PASS.
7. **Codex re-verification**: thread `019e507c` → PASS, overall ACCEPT.
8. **Approval locks flipped**: `pi_approved_binding: true`, `pi_approved_launch: true`, `reliability_curve.pi_approval_status: PI_APPROVED_2026-05-23`.

## Pre-launch verification (this freeze)

- gate_v1.yaml UNTOUCHED (mtime `2026-05-16 22:35:35`)
- 4 invariants confirmed: `beta_robust=0.5`, CVaR `α=0.30`, CVaR `β=0`, `ρ_gate=0.5`
- Local reward-model SHAs match `GATE_V1_SHA_BACKFILL_2026-05-21.md`
- σ_actual values match `SIGMA_CALIBRATION_REPORT_v2_2026-05-22.json` per_sigma_per_prompt
- 64 formal prompts disjoint from 16 σ-cal prompts; smoke prompt `dev_0209` also disjoint
- Captured-v parity = 0.0 rel_err (`CAPTURED_V_PARITY_2026-05-22_GI05.json`)
- D3a formula RESOLVED (`TWEEDIE_DERIVATION_NOTE.md` §8 + §9)

## Constraints in force during AFK launch window

- ONLY Phase B.1 may be launched. Phase C / M-PRM training is OUT OF SCOPE.
- gate_v1.yaml must remain byte-identical.
- gate_v2.yaml.draft stays `.draft` until Phase B.1 audit completes.
- Any HARD blocker (audit CRITICAL_MISMATCH, driver crash, hard_cap_gpu_h exceeded, Codex REJECT in red-team) must HALT.
