# Plan-Code Audit — Headroom-Gated M-PRM

> *Independent semantic implementation audit per `shared-references/semantic-code-audit.md`.*
>
> **Auditor.** Codex GPT-5.5 via `mcp__codex__codex`. Sandbox: `danger-full-access`.
> **Audit history.**
> - v1.0 → v1.3 (2026-05-15): Phase A scaffold (R0–R9). Codex thread `019e2bc1-912f-7791-8061-2c868cc37e51`. Final verdict PARTIAL_MISMATCH (scoped). Body lost 2026-05-20 in agent doc-cleanup incident.
> - **v1.4 (2026-05-23)**: Phase B.1 reliability extension (R10). Codex thread `019e5086-8406-77d3-bd45-d1a40949c840`. This document.

---

## 1. Final verdict (iteration v1.4, 2026-05-23, post-fix)

**VERDICT: PARTIAL_MISMATCH (scoped) — consumable by `/diagnostic-to-review` for Phase B.1**

### Executive summary

Phase B.1 R10 is in **semantic alignment** with the PI-frozen six-σ reliability plan:

- **Frozen SHAs match** the GATE_V2_FREEZE_2026-05-23 record for gate_v2.yaml.draft + phase_b1_reliability.yaml + driver (the latter re-frozen post-fix, below).
- **Prompt isolation verified**: 64 formal ∩ 16 σ-cal = ∅; both ⊂ dev.jsonl (256).
- **σ_actual / step / cfg_active** bindings match `SIGMA_CALIBRATION_REPORT_v2_2026-05-22.json` per_sigma_per_prompt exactly (full precision).
- **Captured effective velocity** is used for Tweedie reconstruction (`x̂_0 = z_k − σ_k · v_effective(k)`), NOT recomputed via predict_velocity; matches the 0.0-rel_err captured-v parity evidence.
- **Tiered H2 rule** (`_classify_tier`) implemented in correct priority order (FAIL → near-threshold-AMBIGUOUS → 1-pair-AMBIGUOUS → STRONG_PASS → SUPPORTED_PASS → early-only-AMBIGUOUS → defensive FAIL); late-reference pairs do NOT rescue.
- **Figure outputs** (4 JSONs) all emit `_cfg_branch_metadata` marking the CFG-active → cond-only transition between σ=0.6 and σ=0.5; quartile_emergence carries `must_not_influence_gate: True`.
- **Reward-model SHA bindings** verified to match actual local files: CLAP `8053c977…`, Audiobox `a4931a7a…`, MERT-v1-95M manifest `ef116b0b…`, Whisper `e5b1a55b…`, Demucs `8726e21a…`.
- **gate_v1.yaml UNTOUCHED** (mtime 2026-05-16 22:35:35).
- **Phase C / M-PRM training NOT imported**; APG / ERG explicitly out of scope.

The initial Codex pass returned `CRITICAL_MISMATCH` due to one **approval-string check bug** in the driver (`gate_status != "PI_APPROVED"` rejected the frozen value `"PI_APPROVED_2026-05-23"`). **The bug was a 1-line code-correctness issue with no scientific or semantic impact.** Post-fix the driver accepts any approval status starting with `"PI_APPROVED"`. Unit tests 4/4 PASS post-fix. Driver SHA re-recorded as `4d004a4cb19cb4132f2ff1c21df3f87796dbf1f1ba83a88708cf99360590ded4` in GATE_V2_FREEZE.

Final verdict: **`PARTIAL_MISMATCH (scoped)`** — the remaining mismatches are documented in §5 (scoped deferrals); none of them block Phase B.1 launch.

Per `semantic-code-audit.md` blocking rules: this verdict is consumable by `/diagnostic-to-review` for Phase B.1. Phase B.2 segmentation / locality (R11) and Phase C M-PRM training (R12+) remain DEFERRED to subsequent `/experiment-bridge` calls.

---

## 2. Frozen SHAs (precheck)

All three frozen SHAs match `orbit-research/GATE_V2_FREEZE_2026-05-23.md`:

| File | Expected SHA | Match |
|---|---|---|
| `configs/eval/gate_v2.yaml.draft` | `34db933b67d06f3acc3780e70b2f492a20d685ef710777fc81eaffba1d2806e9` | ✓ |
| `configs/runs/phase_b1_reliability.yaml` | `365d67c9f605fb99704c2461930bca6d5c48e59f9584a2bf1577d4f503d1d28a` | ✓ |
| `scripts/phase_b1_reliability.py` | `4d004a4cb19cb4132f2ff1c21df3f87796dbf1f1ba83a88708cf99360590ded4` (post-fix) | ✓ |

---

## 3. Per-checklist findings (Codex thread `019e5086`, post-fix)

### A. Sample / sampling specification
- **A1 MATCH** — `phase_b1_reliability.yaml:72-80` mirrors `gate_v2.yaml.draft:310-318` for cfg, ERG, GI=0.5, scale=5.0, 30 steps, shift=3.0.
- **A2 PARTIAL (scoped)** — driver passes cfg_scale + steps as direct args; only cfg_type and ERG flags forwarded via `extras`. GI=0.5 / shift=3.0 are not explicitly passed through extras but rely on upstream defaults (which match the binding). Adapter default in `ace_step.py:593-598` is 0.5.
- **A3 MATCH** — prompt list disjointness verified; 64 ∩ 16 = ∅; both ⊂ dev.jsonl.

### B. σ curve binding
- **B1 MATCH** — primary {0.9,0.8,0.7,0.6}, late_reference {0.5,0.3}, excluded {0.1} bound at `phase_b1_reliability.yaml:94-122`.
- **B2 MATCH** — σ_actual + step_index match `SIGMA_CALIBRATION_REPORT_v2_2026-05-22.json` per_sigma_per_prompt exactly.
- **B3 MATCH** — cfg_active sequence = `[T, T, T, T, F, F]`.
- **B4 MATCH** — σ drift warns at driver `:543-549`; cfg_active drift fails at `:550-554`.
- **B5 MATCH** — driver reads `trajectory_model_outputs[k]` at `:515-518`; reconstructs `z0 = z_k - sigma_actual * v_eff` at `:555-559`; no `predict_velocity` recompute.

### C. Reliability metric + tiered H2 rule
- **C1 PARTIAL (scoped)** — Spearman implementation at `:73-89` is not tie-aware (basic rank correlation). Per_prompt_jsonl preserves raw values so canonical tie-corrected Spearman is recomputable offline before final gate interpretation. Acceptable for raw-data generation.
- **C2 MATCH** — `_classify_tier` priority order matches PI-locked rule (FAIL → near-threshold AMBIGUOUS → 1-pair AMBIGUOUS → STRONG_PASS → SUPPORTED_PASS → early-only AMBIGUOUS → defensive FAIL).
- **C3 MATCH** — late pairs collected separately at `:257-258`; emitted as descriptive-only at `:665-686`.
- **C4 MATCH** — near-threshold band restricted to primary at `:249-256`.

### D. Escalation routes
- **D1 PARTIAL (scoped)** — AMBIGUOUS action declared; driver does NOT auto-generate 128-prompt expansion. Config has TODO at `:236-238` to generate `PHASE_B1_RELIABILITY_PROMPTS_EXPANSION.json` on trigger. This is acceptable for the initial 64-prompt run; PI re-approval is required before any expansion.
- **D2 MATCH** — FAIL pivot to outcome-only per NULL_RESULT_CONTRACT §2 Block B.1.

### E. Reward stack
- **E1 MATCH** — 7 axes wired (CLAP + 4 Audiobox + Whisper-WER + MERT).
- **E2 MATCH** — lyric_intelligibility skipped on instrumental prompts; per-axis n reported.
- **E3 MATCH** — local-file SHAs verified for all 5 reward models against gate_v2 `sha_pinned` block.

### F. Figure outputs + CFG-branch metadata
- **F1 MATCH** — all 4 figure JSONs emitted (reward_emergence, reliability_curves, non_triviality, quartile_emergence).
- **F2 MATCH** — `_cfg_branch_metadata` contains transition [0.6, 0.5], branch_per_sigma, start/end_idx in each figure.
- **F3 MATCH** — quartile_emergence carries `must_not_influence_gate: true`.

### G. Audit gates + dual lock
- **G1 MATCH** — `_validate_consistency` cross-checks gate_v2 vs run config before launch.
- **G2 MATCH** — prompt disjointness enforced BEFORE PI gate AND BEFORE model loading.
- **G3 MATCH** (post-fix) — dual-lock now accepts `PI_APPROVED_*` prefix. Original verdict was CRITICAL on this line; fixed by replacing `gate_status != "PI_APPROVED"` with `not str(gate_status).startswith("PI_APPROVED")`. 4/4 unit tests PASS.
- **G4 MATCH** — `hard_cap_gpu_h=15` honored via mid-loop wall-clock abort.

### H. Outputs + ledger
- **H1 MATCH** — `results.jsonl`, `per_axis_sigma_rho.json`, `H2_VERDICT.json`, 4 figures all emitted.
- **H2 MATCH** — `run-final` ledger event with tier / elapsed / hard_cap / smoke flag / audit_trail.
- **H3 MATCH** — smoke artifacts exist under `runs/phase_b1_reliability_smoke/`; tier=FAIL is the structurally-expected outcome for n=1 (Spearman undefined).

### I. Boundaries
- **I1 MATCH** — gate_v1.yaml mtime UNCHANGED at 2026-05-16 22:35:35.
- **I2 MATCH** — driver imports only inference + reward paths; no Phase C / training imports.
- **I3 MATCH** — ERG disabled in config; gate_v2 explicitly scopes APG/ERG out; adapter docs the non-replication.

---

## 4. Critical issues (must-fix-before-launch)

**FIXED in this audit-and-patch round.** The only CRITICAL was:

- `scripts/phase_b1_reliability.py:217-224` — approval-status check rejected the frozen `PI_APPROVED_2026-05-23` value. Fixed by changing exact-match to prefix-check. Unit tests 4/4 PASS. Driver re-frozen with SHA `4d004a4cb19c…`; GATE_V2_FREEZE_2026-05-23 record updated.

No remaining CRITICAL_MISMATCH items.

---

## 5. Scoped deferrals (tolerated for Phase B.1 launch)

These mismatches do NOT block Phase B.1 launch but are tracked:

| # | Item | Scope | Tolerance basis |
|---|---|---|---|
| 1 | A2 — full sampler binding not explicitly forwarded via `extras` | Sampler | GI / shift defaults already match the binding (cfg-default 0.5, scheduler shift hardcoded in upstream). Captured-v parity = 0.0 confirms semantic equivalence at runtime. |
| 2 | C1 — Spearman not tie-aware | Statistics | `results.jsonl` retains raw per-prompt rewards; canonical tie-corrected Spearman is recomputable offline if final gate interpretation requires it. |
| 3 | D1 — 128-prompt ambiguous-expansion not auto-generated | Escalation | The trigger is documented; PI re-approval is required to expand regardless. Generating the expansion list during the run would over-couple the driver. |

---

## 6. What this audit does NOT cover

- **R11 (Phase B.2 — segmentation + locality probe)**: explicitly OUT OF SCOPE per PI directive 2026-05-23 ("不要跑 Phase B.2 segmentation/locality"). A separate `/experiment-bridge` call will be required if/when R11 is wired up.
- **R12+ (Phase C — M-PRM training rungs)**: explicitly OUT OF SCOPE.
- **APG / cfg_zero_star / ERG paths**: explicitly OUT OF SCOPE per the formal Phase B sampler binding.

---

## Document history

- **v1.0** — 2026-05-15T03:00Z. Initial Codex audit pass over Phase A scaffold. Verdict CRITICAL_MISMATCH.
- **v1.1** — 2026-05-15T03:30Z. Post-fix re-audit. Verdict PARTIAL_MISMATCH (advisory).
- **v1.2** — 2026-05-15T04:30Z. Second-round re-audit. Verdict PARTIAL_MISMATCH (3 blocking).
- **v1.3** — 2026-05-15T05:50Z. Final Phase A iteration. Verdict PARTIAL_MISMATCH (scoped) — Phase A ready, R10-R21 deferred.
- **v1.3-content-loss-note** — 2026-05-20T07:30Z. §2-§15 body deleted in agent doc-cleanup; only §1 verdict recovered.
- **v1.4** — 2026-05-23. Phase B.1 (R10) extension. Codex thread `019e5086-8406-77d3-bd45-d1a40949c840`. One CRITICAL approval-string bug found and fixed in the same round (unit tests 4/4 PASS). Final verdict PARTIAL_MISMATCH (scoped) — consumable by `/diagnostic-to-review` for Phase B.1; R11+ remain deferred.
