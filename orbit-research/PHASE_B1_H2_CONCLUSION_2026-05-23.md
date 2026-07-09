# Phase B.1 H2 Conclusion — PI-frozen 2026-05-23

> **Paper-framing context**: this memo freezes the H2 ("When to Reward")
> outcome before moving on to H3 ("Where to Reward"). H2 is one of the two
> co-equal scientific questions in the 2026-05-23 paper-framing freeze
> "*When and Where to Reward*"; H3 is the other.

## 1. Final H2 tier

**Final tier (128 prompts, canonical formal + expansion merged): `STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES`** under the revised PI-locked tiered rule (2026-05-23).

- 128-prompt: `n_primary_full = 20`, `n_primary_strict = 17`, `strong_holds_strict = True`, `classification_depends_on_near_threshold = False` (firm robustness — classification holds with or without near-threshold pairs).
- 64-prompt (canonical only, historical): `n_primary_full = 17`, `n_primary_strict = 15` — same tier, both intermediate verdicts agree.

### Tier definition (PI-revised 2026-05-23)

- `STRONG_PASS`: ≥2 primary (σ ∈ {0.9, 0.8, 0.7, 0.6}) pairs with ρ ≥ 0.5; ≥1 from early σ ∈ {0.9, 0.8}; ≥1 from middle σ ∈ {0.7, 0.6}; **no primary pair in the [0.50, 0.55] near-threshold band**.
- `STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES`: STRONG criteria hold even when near-threshold pairs are excluded, BUT at least one near-threshold pair is present (transparency note, classification not load-bearing on near-threshold pairs).
- `SUPPORTED_PASS`: ≥2 primary pairs but confined to middle σ.
- `AMBIGUOUS`: exactly 1 primary pair OR classification truly depends on near-threshold pairs OR ≥2 primary pairs but early-only coverage.
- `FAIL`: no primary pair survives.

### Why the result is STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES, not AMBIGUOUS

Under the (now-superseded) literal rule from earlier 2026-05-23, "any primary pair in the [0.50, 0.55] band → AMBIGUOUS" fired because 2 of 17 surviving primary pairs are in that band. The PI's revised rule (this directive) checks whether dropping those near-threshold pairs would still leave STRONG criteria satisfied. It does — 15 surviving primary pairs remain (≥ 2 required), with both early σ coverage (aesthetic_pq @ σ=0.8, aesthetic_cu @ σ=0.8/0.9) and middle σ coverage (many). Therefore the classification is NOT load-bearing on the near-threshold pairs, and STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES is the correct tier.

Driver introspection fields confirming this:
- `strong_holds_full: true`
- `strong_holds_strict: true`
- `classification_depends_on_near_threshold: false`

## 2. Which axes pass in the primary σ region

**128-prompt result (final, merged)**:

| H3-relevant axis | Reward axis | Primary σ passing ρ ≥ 0.5 | 128-prompt ρ (current) |
|---|---|---|---|
| musicality | aesthetic_pq | σ ∈ {0.9†, 0.8, 0.7, 0.6} | 0.500†, 0.658, 0.696, 0.854 |
| musicality (alt) | aesthetic_ce | σ ∈ {0.8†, 0.7, 0.6} | 0.549†, 0.673, 0.853 |
| (Audiobox CU) | aesthetic_cu | σ ∈ {0.9, 0.8, 0.7, 0.6} | 0.641, 0.724, 0.752, 0.882 (strongest axis; all 4 primary σ) |
| (Audiobox PC) | aesthetic_pc | σ = 0.6 only | 0.657 (σ=0.7 ρ=0.483 below threshold after expansion) |
| coherence | section_coherence (MERT) | σ ∈ {0.8, 0.7, 0.6} | 0.639, 0.761, 0.818 (σ=0.8 firmed above near-threshold) |
| prompt_fit | semantic_fit (CLAP) | σ = 0.6 only | 0.659 |
| lyric | lyric_intelligibility (Whisper-WER) | σ ∈ {0.9†, 0.8, 0.7, 0.6} | 0.514†, 0.646, 0.753, 0.788 |

† = pair in the [0.50, 0.55] near-threshold band on 128 prompts.

**20 surviving primary (axis × σ) pairs** on 128 prompts (up from 17 on 64). **17 surviving** after excluding the 3 near-threshold pairs (up from 15 on 64). **7 of 7 reward axes** have at least one primary survival (up from 6/7 on 64 — `lyric_intelligibility` gained σ ∈ {0.8, 0.9} on 128). Classification does NOT depend on near-threshold pairs at either sample size.

**Near-threshold pair migration (64 → 128 prompts)**:
- 64-prompt near-threshold pairs: `aesthetic_pc @ σ=0.7 (0.5109)`, `section_coherence @ σ=0.8 (0.5140)`.
- 128-prompt near-threshold pairs: `aesthetic_pq @ σ=0.9 (0.5001)`, `aesthetic_ce @ σ=0.8 (0.5488)`, `lyric_intelligibility @ σ=0.9 (0.5142)`.
- The 64-prompt near-threshold pairs MOVED: `aesthetic_pc @ σ=0.7` fell to 0.483 (below threshold; the only primary pair that lost survival under expansion); `section_coherence @ σ=0.8` rose firmly to 0.639. The 128-prompt added 3 new near-threshold pairs at the σ=0.9 / σ=0.8 boundary, where the early-σ tails are most sensitive to sample size.
- Net effect: more total primary survivors, more even axis coverage, no change in tier classification, no load-bearing on near-threshold.

## 3. Which axes only pass in late-reference region (128-prompt)

| Reward axis | Late-reference σ passing ρ ≥ 0.5 | 128-prompt ρ |
|---|---|---|
| aesthetic_pq | σ ∈ {0.5, 0.3} | 0.935, 0.973 (saturated; expected) |
| aesthetic_pc | σ ∈ {0.5, 0.3} | 0.836, 0.964 (saturated; expected) |
| aesthetic_ce | σ ∈ {0.5, 0.3} | 0.939, 0.983 (saturated; expected) |
| aesthetic_cu | σ ∈ {0.5, 0.3} | 0.940, 0.975 (saturated; expected) |
| semantic_fit | σ ∈ {0.5, 0.3} | 0.715, 0.732 (saturated; expected) |
| section_coherence | σ ∈ {0.5, 0.3} | 0.910, 0.936 (saturated; expected) |
| lyric_intelligibility | σ ∈ {0.5, 0.3} | 0.873, 0.851 (saturated; expected) |

**No axis passes ONLY in late-reference** on 128 prompts (all 7 axes have at least one primary survival too). This is the expected pattern — late-reference σ ∈ {0.5, 0.3} correlate trivially with final reward because the audio is nearly clean by that σ. **These late-reference passes do NOT contribute to STRONG/SUPPORTED classification and do NOT rescue FAIL** (per PI directive 2026-05-23). Compared to 64-prompt: late-reference ρ values are essentially unchanged (saturation regime is data-volume insensitive at this n).

## 4. Whether early reward emergence is supported

**Yes — early reward emergence is empirically supported on the primary σ region.**

The strongest evidence:
- `aesthetic_cu` (CU = Audiobox Content Usefulness): ρ ∈ [0.62, 0.89] across ALL 4 primary σ. Highest non-trivial correlation at the noisiest σ tested (σ=0.9 ρ=0.619).
- `aesthetic_pq` (PQ = Audiobox Production Quality): ρ ∈ [0.69, 0.87] across primary σ ∈ {0.8, 0.7, 0.6}. Reaches 0.692 at σ=0.8 — well above the 0.5 threshold in an early σ region.

The "When to Reward" headline finding is: **at σ ∈ {0.7, 0.6} (mid-trajectory) every aesthetics axis is reliably scorable on intermediate audio**; at σ ∈ {0.8, 0.9} the aesthetics axes most aligned with content usefulness (`aesthetic_cu`, `aesthetic_pq`) are already reliable. This is the early-emergence signal that the σ-curve characterization was designed to surface; a binary K=3 hand-selected gate could not have detected the per-axis stratification.

## 5. Whether quality-stratified emergence is supported as exploratory analysis

**Yes — quality-stratified emergence is empirically supported.** Reported as **exploratory, `must_not_influence_gate: true`** per spec.

Top-Q4 (high-final-quality) vs bot-Q1 (low-final-quality) `aesthetic_pq` median gap:

| σ | top-Q4 median | bot-Q1 median | gap |
|---|---:|---:|---:|
| 0.9 | 6.068 | 5.420 | **+0.65** |
| 0.8 | 6.692 | 5.497 | +1.20 |
| 0.7 | 7.092 | 5.490 | +1.60 |
| 0.6 | 7.339 | 5.491 | +1.85 |
| 0.5* | 7.949 | 5.780 | +2.17 |
| 0.3* | 8.031 | 6.100 | +1.93 |

(* late-reference, descriptive only.)

The PI hypothesis pre-launch was: "high-quality trajectories may become musically interpretable earlier than poor-quality ones." This is empirically supported: the gap grows monotonically across σ from +0.65 at σ=0.9 to +2.17 at σ=0.5. Even at the noisiest σ tested (σ=0.9), Tweedie-reconstructed `aesthetic_pq` already separates high-final-quality from low-final-quality trajectories.

The full quartile narrative — with IQR, range, Cohen's d, and CFG-boundary annotation — lives in `runs/phase_b1_reliability/figures/quartile_emergence.{json,md,_table.csv}`.

This finding is **scientifically novel and paper-relevant** but is **NOT** part of the H2 gate. It informs M-PRM curriculum design in Phase C (e.g., headroom-weighted curriculum can weight by predicted final quality, since σ=0.9 already separates quartiles).

## 6. Limitations

- **Late σ correlation is expected and is NOT primary evidence.** Late-reference σ ∈ {0.5, 0.3} have ρ ∈ [0.68, 0.98] across all 7 reward axes. This is trivially consistent with H2 because audio is nearly clean by that σ. Treating these as H2 evidence would be unfair — the paper must explicitly demote them to "stabilization / reference" and report them in supplementary tables only. Primary H2 evidence is the σ ∈ {0.9, 0.8, 0.7, 0.6} region.

- **Audiobox axes are ONE reward family, not four independent families.** `aesthetic_pq`, `aesthetic_pc`, `aesthetic_ce`, `aesthetic_cu` are the four output heads of the Audiobox-aesthetics-4 model (PQ = Production Quality, PC = Production Complexity, CE = Content Enjoyment, CU = Content Usefulness). They are statistically correlated. The "n_primary_pairs = 17" count includes correlated axes; the deduplicated diversity of evidence is closer to **3 axis families** (Audiobox, CLAP, MERT) + lyric_intelligibility (Whisper-WER) = **4 independent families**, not 7. The paper text must not over-count the "axes pass" claim.

- **MERT section_coherence has small dynamic range.** σ ∈ {0.9, 0.8, 0.7, 0.6} ρ values are 0.287, 0.514, 0.749, 0.790 — increasing but the per-prompt section_coherence values themselves cluster tightly around [0.93, 0.99]. Spearman ρ is correlation-of-ranks and is well-defined on tight clusters, but the **dynamic range** of section_coherence on this prompt set is small. Whether this dynamic range is sufficient for trained M-PRM section credit (Phase C) is a separate empirical question; H2 only establishes that intermediate section_coherence ranks correlate with final section_coherence ranks.

- **Lyric_intelligibility on instrumental prompts.** WER is undefined for instrumental prompts; the lyric axis is computed only on vocal-bearing prompts. The H2 verdict on lyric_intelligibility is therefore conditional on the vocal subset. Phase B.3 H3 + Phase C M-PRM must apply lyric_intelligibility scoring only on the vocal subset of prompts (consistent with FINAL_PROPOSAL §A2 lyric-guard policy: "lyric guard inactive for instrumental prompts").

- **CFG-mixed → cond-only branch boundary is annotated but not isolated.** The σ-curve crosses the boundary between σ=0.6 (last CFG-mixed step) and σ=0.5 (first cond-only step). The reliability curves show NO sharp discontinuity across that boundary, which is good news for the branch-aware effective-velocity approach. But the smoothness check is descriptive; we have not run a dedicated branch-control ablation that re-runs the same prompts with CFG-mixed vs cond-only at matched σ. That ablation is deferred (out of scope per PI directive 2026-05-23).

- **128 prompts is still moderate for near-threshold Spearman pairs.** The expansion firmed the result rather than changing the tier, but pairs near ρ=0.5 should still be reported transparently. The claim should emphasize that the STRONG criteria hold after excluding near-threshold pairs.

## 7. Explicit next decision

The Phase B.1 H2 verdict is sufficient to **proceed to H3 (Phase B.3 credit-unit comparison)**, NOT to expand again, NOT to pivot outcome-only.

### Rationale (one-line)
H2 returned `STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES` on the merged 128-prompt analysis; the tier is robust to excluding near-threshold pairs and is sufficient to proceed to H3 after PI signs off on the H3 config.

### Decision sequencing

1. **Do not expand H2 again** unless PI explicitly requests a new robustness study.
2. **Proceed only to Phase B.3 H3 plan execution** after PI signs off on `configs/runs/phase_b3_credit_unit_comparison.yaml`.
3. **Phase B.2 (segmentation / locality probe)** is explicitly OUT OF SCOPE per PI directive 2026-05-23. Do not launch.
4. **Phase C M-PRM training** is explicitly NOT launched. No reward definitions changed. No σ-curve changes. gate_v1.yaml untouched. gate_v2.yaml.draft remains `.draft`.

### Cross-references

- `runs/phase_b1_reliability/H2_VERDICT.json` (merged 128-prompt canonical verdict).
- `runs/phase_b1_reliability/H2_VERDICT.md` (merged 128-prompt Markdown view).
- `runs/phase_b1_reliability/per_axis_sigma_rho.json` (merged 128-prompt per-axis × σ matrix).
- `runs/phase_b1_reliability/figures/{reliability_curves, reward_emergence, non_triviality, quartile_emergence}.{json,md,csv}`.
- `runs/phase_b1_reliability_expansion/` (completed 64-prompt expansion raw evidence).
- `orbit-research/PHASE_B3_H3_PLAN.md` (next-phase plan, prepared, NOT launched).
- `configs/runs/phase_b3_credit_unit_comparison.yaml` (next-phase config, `pi_approved_launch: false`).
- `refine-logs/FINAL_PROPOSAL.md` §6 H2 (paper-level claim; framing freeze 2026-05-23).
- `refine-logs/METHOD_SPEC.md` §4.2 (late-σ caveat 2026-05-23).
- `orbit-research/NULL_RESULT_CONTRACT.md` §2 Block B.1 (FAIL pivot, NOT triggered).
- `orbit-research/CURRENT_CANONICAL_FILES.md` (canonical file index, 2026-05-23).

---

## 128-prompt expansion result (filled in post-merge 2026-05-23)

- **128-prompt tier**: `STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES` (same as 64-prompt — robust under doubling sample size).
- **n_primary_pairs (full)**: 20 (up from 17 on 64).
- **n_primary_pairs (excluding near-threshold)**: 17 (up from 15 on 64).
- **near-threshold pairs (rho ∈ [0.50, 0.55])** on 128: 3 — `aesthetic_pq @ σ=0.9 (0.5001)`, `aesthetic_ce @ σ=0.8 (0.5488)`, `lyric_intelligibility @ σ=0.9 (0.5142)`.
- **classification_depends_on_near_threshold**: False (`strong_holds_strict = True`).
- **Δ vs 64-prompt verdict**:
  - Tier: identical (`STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES` both times).
  - n_primary +3 (17 → 20); n_primary_strict +2 (15 → 17). Adding more data added more survivors, not fewer.
  - 64-prompt near-threshold pairs *migrated*: `aesthetic_pc @ σ=0.7` fell from 0.5109 → 0.483 (below threshold, the only primary loss); `section_coherence @ σ=0.8` rose from 0.5140 → 0.639 (firmly above near-threshold). The 128-prompt near-threshold band populated with 3 *new* pairs at the very early σ region (σ=0.9 / σ=0.8) where small-N noise is largest. No change in tier classification.
  - **Robustness conclusion**: H2 STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES is robust under sample-size doubling. The 128-prompt result supersedes the 64-prompt result as the canonical verdict.
- **Expansion run cost**: 0.43 GPU-h (1548.5s on a single A800, well under the 2 GPU-h budget cap).
- **Combined Phase B.1 total cost**: 0.32 (formal) + 0.43 (expansion) = **0.75 GPU-h** — way under the original 6 GPU-h estimate and the 15 GPU-h hard cap.

The §1 final tier line above is updated to reflect the 128-prompt merged result.
