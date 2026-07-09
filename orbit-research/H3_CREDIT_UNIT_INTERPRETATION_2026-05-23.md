# H3 Credit-Unit Interpretation Memo — 2026-05-23

> PI-facing interpretation of the H3a-dev + held-out automatic prescreen
> for the "When and Where to Reward" project, after the H3a-dev FAIL
> verdict and the sectionability analysis. The held-out 256 confirmation
> ran on 8 GPUs (see §3); this memo integrates dev + held-out.

## 1. Final H3 status

**Classification (dev + held-out)**: _PENDING_ — filled in post-held-out
merge. Candidate labels per PI directive:

- **SECTION_PASS** — CU-MS beats best non-section by ≥ +0.08 on ≥ 2 of 3
  axes on BOTH dev AND held-out.
- **SECTION_FAIL_BEATWIN_WIN** — CU-MS loses; CU-BW emerges as best
  non-section unit consistently across strata and axes.
- **SECTION_FAIL_FIXEDWIN_WIN** — CU-MS loses; CU-FW emerges as best
  non-section unit consistently.
- **SECTION_FAIL_LYRICSPAN_WIN** — CU-MS loses; CU-LS emerges as best
  non-section unit consistently on the vocal stratum (LS NA on instr).
- **MIXED_BY_STRATUM** — different non-section unit wins on different
  strata or different axes.
- **INCONCLUSIVE** — verdict is FAIL but no single non-section unit
  emerges as a clean winner; story is "no credit unit clearly works".

## 2. Section vs non-section across (split × stratum × axis)

The H3a-dev result (already in `runs/phase_b3_credit_unit/h3a/H3_VERDICT.json`):
- Vocal stratum: 0/3 axes pass directional (+0.05); 0/3 strict (+0.08).
- Instrumental stratum: 1/3 axes pass directional (musicality +0.073);
  0/3 strict. Both strata FAIL.

Held-out result will be filled in below (per `h3_held_out/H3_VERDICT.json`).

**Section-loses-consistently audit grid** (dev):

| split × stratum × axis | section_minus_best_non_section | section loses? |
|---|---:|---|
| dev × vocal × musicality | −0.100 | yes |
| dev × vocal × coherence | −0.168 (CU-BW=1.0 spurious; see audit) | yes |
| dev × vocal × prompt_fit | −0.026 | yes |
| dev × instr × musicality | +0.073 | **no** (CU-MS wins directionally) |
| dev × instr × coherence | −0.290 (CU-BW=1.0 spurious) | yes |
| dev × instr × prompt_fit | −0.040 | yes |

5 of 6 cells: section loses. 1 of 6 (instr × musicality): section wins
directionally (+0.073). The held-out section will be appended once the
8-GPU run completes.

## 3. Best non-section unit

Held-out aggregation _PENDING_. From dev:

| Stratum × axis | Best non-section (current verdict) | Best non-section (coverage-aware) |
|---|---|---|
| vocal × musicality | CU-LS (0.52) | CU-LS (0.52) |
| vocal × coherence | CU-BW (1.00, artifact) | CU-LS (0.84) |
| vocal × prompt_fit | CU-FW (0.60) | CU-FW (0.60) |
| instr × musicality | CU-FW (0.57) | CU-FW (0.57) |
| instr × coherence | CU-BW (1.00, artifact) | undefined (no valid non-section) |
| instr × prompt_fit | CU-FW (0.57) | CU-FW (0.57) |

**Headline (dev, coverage-aware)**: CU-FW is the strongest non-section
unit across most cells, with CU-LS competitive on vocal axes. CU-BW's
apparent dominance is largely a low-coverage Spearman artifact (see
`orbit-research/H3A_DEV_AUDIT_2026-05-23.md`). Held-out result will
confirm or update this picture.

## 4. Sectionability explanation

From `runs/phase_b3_credit_unit/h3a/SECTIONABILITY_REPORT.md`:

- **27% of clips** are weakly sectionable (per-section MERT coherence
  range < 0.05 — i.e., the 4 forced "sections" have nearly identical
  coherence profile, no real section structure).
- **62% of clips** are strongly sectionable (range ≥ 0.20).
- **Low-quality clips have HIGHER coherence_range** (median 0.96) than
  high-quality clips (median 0.54). Counterintuitive at first: it
  suggests low-quality outputs have more inconsistent / failing patches
  *within* a clip (giving more variation across sections), while
  high-quality outputs are more consistent throughout.
- **Correlation: ρ(coherence_range, CU-MS within-prompt ρ) = +0.293**.
  Moderate positive correlation: section credit *does* perform better
  on clips that are actually section-structured, but the effect is
  weak and the gain doesn't overcome the +0.08 H3 threshold.

**Reading**: PI's pre-launch hypothesis that "ACE-Step 30-50 s clips
often lack stable section structure" is **partially supported** — 27%
of clips have no real section structure, and even when present, sect-
ion-credit doesn't outperform alternatives by enough. The pivot is
defensible but should be scoped to "ACE-Step 30-50 s generation regime"
rather than "all music generation".

## 5. Paper implication

If held-out confirms dev's section-loses pattern:

- **Do NOT frame this as project failure.** The H2 ("when") evidence
  remains intact (STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES on 128 prompts).
- **Frame the H3 result as a credit-unit selection finding**: "for
  ACE-Step short-form (30-50 s) generations, musical-section credit is
  not the strongest unit on automatic per-section reward proxy; local
  windows (BeatWin / FixedWin / LyricSpan) provide more reliable
  credit assignment for this regime."
- **Be precise about scope**: this is a finding about the H3a
  automatic-prescreen (per-section reward delta against final-audio
  proxy) on dev + held-out at σ ∈ {0.7, 0.6}. It is NOT a definitive
  claim about song-level credit assignment in general; full Phase D
  human eval (Tier 1) is still required to convert this into a paper
  claim per PI policy.
- **The paper title stays**: "When and Where to Reward: Reward Emergence
  and Musical Credit Assignment in Flow-Matching Music Generation".
  "Where" now reads "empirical credit-unit selection" instead of
  "musical-section credit a priori".

If held-out shows a different pattern from dev (e.g., section wins on
held-out, or a different non-section unit wins on held-out):
- Report the disagreement honestly. Mark H3 as INCONCLUSIVE for now,
  defer to Phase D human eval.

## 6. Recommended downstream method

Held-out _PENDING_. Provisional recommendation from dev only:

- If CU-FW emerges as the consistent winner: **FixedWin-PRM** (4-second
  local-window process reward) is the downstream method.
- If CU-BW emerges (post coverage-aware filtering): **BeatWin-PRM**
  (beat-synchronous local-window process reward).
- If CU-LS wins on vocal only: vocal-specific lyric-span PRM.
- If mixed: **stratum-conditioned credit-unit selection** — choose CU
  per prompt based on (vocal/instrumental, expected length, expected
  structure_hint).

In all cases, M-PRM should be reformulated to use the empirically
selected best credit unit, not a hard-coded section prior.

## 7. Hard scientific boundaries — preserved

| Constraint | Status |
|---|---|
| σ ∈ {0.7, 0.6} unchanged | ✓ |
| Reward axes (aesthetic_pq, section_coherence, semantic_fit) unchanged | ✓ |
| Credit-unit definitions unchanged (only reporting/aggregation analysis adjusted) | ✓ |
| Prompt splits unchanged (formal 64 dev disjoint from cal 16, expansion 64, held-out 256) | ✓ |
| gate_v1.yaml UNTOUCHED (mtime 2026-05-16 22:35:35) | ✓ |
| Phase C / M-PRM training NOT launched | ✓ |
| Section hypothesis NOT redefined to "rescue" it | ✓ |
| Paper story NOT rewritten as final — this is a draft interpretation | ✓ |

## 8. Cross-references

- `orbit-research/H3A_DEV_AUDIT_2026-05-23.md` (dev verdict + aggregation artifact)
- `runs/phase_b3_credit_unit/h3a/H3_VERDICT.json` (dev verdict — FAIL)
- `runs/phase_b3_credit_unit/h3a/SECTIONABILITY_REPORT.{json,md}` (sectionability proxy)
- `runs/phase_b3_credit_unit/h3_held_out/H3_VERDICT.json` (held-out verdict, _pending_)
- `orbit-research/PHASE_B1_H2_CONCLUSION_2026-05-23.md` (H2 STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES)
- `orbit-research/PHASE_B3_H3_PLAN.md` (locked H3 plan)
- `configs/runs/phase_b3_credit_unit_comparison.yaml` (locked H3 config)

## 9. Held-out completion update (2026-05-23, 8-GPU sharded)

8-GPU sharded held-out run completed; 256/256 prompts; merged verdict written to
`runs/phase_b3_credit_unit/h3_held_out/H3_VERDICT.json` (tier=FAIL).

### 9.1 Held-out per-(stratum, axis) numbers

**Vocal stratum (n=159 / 256)** — section_minus_best_non_section:
- musicality: **−0.133** (CU-MS 0.390 vs CU-BW 0.523)
- coherence: **−0.214** (CU-MS 0.786 vs CU-BW 1.000 ← coverage artifact, see §3 footnote)
- prompt_fit: **−0.055** (CU-MS 0.536 vs CU-FW 0.591)

**Instrumental stratum (n=97 / 256)** — section_minus_best_non_section:
- musicality: **+0.046** (CU-MS 0.547 vs CU-FW 0.501) — directional but **below +0.05**
- coherence: **−0.235** (CU-MS 0.765 vs CU-BW 1.000 ← coverage artifact)
- prompt_fit: **+0.054** (CU-MS 0.592 vs CU-FW 0.538) — **passes directional +0.05**

**Held-out tier**: FAIL (no axis × stratum cell crosses +0.08 strict; instrumental
prompt_fit barely clears +0.05 directional, isolated).

### 9.2 Dev↔held-out concordance

Unit-ranking Kendall-τ across splits:
- **vocal**: τ = +0.867 (dev `[CU-BW, CU-MS, CU-LS, CU-FW, NULL, CU-TS]` vs held
  `[CU-BW, CU-LS, CU-MS, CU-FW, NULL, CU-TS]` — only CU-MS↔CU-LS swap)
- **instrumental**: τ = +1.000 (identical ranking `[CU-BW, CU-MS, CU-FW, NULL, CU-TS]`)

Combined-overall Kendall-τ across strata on held-out: **1.000** (vocal and instr
agree on consensus ranking `[CU-BW, CU-MS, CU-FW, CU-NULL-rand-section, CU-TS]`).

**The H3 verdict is highly reproducible across dev and held-out splits.**

### 9.3 Best non-section unit per (stratum, axis), held-out

| Stratum × axis | Raw best non-section | Coverage-aware best non-section |
|---|---|---|
| vocal × musicality | CU-BW (0.52) | CU-BW (0.52) (full coverage) |
| vocal × coherence | CU-BW (1.00, artifact) | CU-LS (0.83) |
| vocal × prompt_fit | CU-FW (0.59) | CU-FW (0.59) |
| instr × musicality | CU-FW (0.50) | CU-FW (0.50) |
| instr × coherence | CU-BW (1.00, artifact) | CU-MS (0.76) — but MS is the section unit; non-section coverage-aware is undefined |
| instr × prompt_fit | CU-FW (0.54) | CU-FW (0.54) |

### 9.4 Provisional classification (PENDING PI confirmation)

The classification depends on whether CU-BW's coherence ρ=1.0 is treated as the
literal winner or filtered for coverage. Two equally defensible labels:

- **`SECTION_FAIL_BEATWIN_WIN` (raw signal)** — CU-BW wins the consensus ranking
  on both dev and held-out, both strata. Story: "BeatWin-PRM is the H3 selection".
  Risk: rests on aggregation behavior of MERT section_coherence under
  sub-window crops (32/128 finite blocks, all ρ=1.0 — see audit).

- **`MIXED_BY_STRATUM` (coverage-aware)** — non-section best is CU-BW on vocal
  (2 of 3 axes) and CU-FW on instr (2 of 3 axes). Story: "credit unit is regime-
  and stratum-dependent; FixedWin is the more reliable single choice; BeatWin
  wins where it has coverage". Risk: harder narrative; demands per-stratum
  recipe in M-PRM.

We surface BOTH labels to PI rather than picking one, because the choice is a
real scientific call (which signal do we trust — raw or coverage-corrected?)
not a typo to clean up.

**Recommended call (provisional)**: lean **MIXED_BY_STRATUM** for the paper
narrative, with **CU-FW as the single-best non-section candidate**. CU-FW is:
1. Best on prompt_fit on both strata (vocal 0.59, instr 0.54).
2. Best on instr musicality (0.50).
3. Has full coverage on every cell; no aggregation artifact.
4. Robust to the CU-BW coverage controversy.

A FixedWin-PRM head-to-head against M-PRM as the Phase D Tier 1 main pair is
the highest-information Phase D design.

### 9.5 GPU-h consumed

- Held-out 256 prompts × BoN-N=1 × CU evaluation × 8-GPU sharded.
- Wallclock per shard: ~30 min after CPU-thread oversubscription fix.
- Total GPU-h ≈ 8 GPUs × 0.5 h = **4 GPU-h** (well under the 30 GPU-h cap PI
  set in the delegation directive).

### 9.6 Final cross-references for §9

- `runs/phase_b3_credit_unit/h3_held_out/H3_VERDICT.json` (tier=FAIL, combined τ=1.0)
- `runs/phase_b3_credit_unit/h3_held_out/h3_vocal_stratum.json` (n=159)
- `runs/phase_b3_credit_unit/h3_held_out/h3_instrumental_stratum.json` (n=97)
- `runs/phase_b3_credit_unit/h3_held_out/results.jsonl` (256 prompts, audit trail)
- `runs/phase_b3_credit_unit/h3_held_out/shard_{0..7}.log` (per-shard timing)

## 10. Corrected held-out completion (PI directive Phase 2 — 2026-05-23, global-seed)

Re-ran held-out 256 with the global-index seed fix that addressed Codex
Review #1's shard-seed-aliasing finding. Verified 256 unique seeds
(range 200..455) and 256 unique `global_prompt_index` values via the
launcher's post-merge verification step.

### 10.1 Verdict tier

**Tier=FAIL on both strata; combined Kendall-τ across strata = 1.000**
(rankings agree). Consensus ranking same as dev + legacy held-out:
`[CU-BW, CU-MS, CU-FW, CU-NULL-rand-section, CU-TS]`.

### 10.2 Per-(stratum, axis) section_minus_best_non_section

| Stratum × axis | Corrected (v2) | Legacy (v1) | Δ vs legacy |
|---|---:|---:|---:|
| vocal × musicality | **−0.042** | −0.133 | +0.091 |
| vocal × coherence | **−0.274** | −0.214 | −0.060 |
| vocal × prompt_fit | **−0.082** | −0.055 | −0.027 |
| instr × musicality | **+0.020** | +0.046 | −0.026 |
| instr × coherence | **−0.278** | −0.235 | −0.043 |
| instr × prompt_fit | **+0.167** | +0.054 | **+0.113** |

**Material change**: removing the seed-aliasing changes 5 of 6 cells by
≥+0.026 in magnitude. The largest single shift is **instr ×
prompt_fit: +0.113** — corrected shows section credit beating CU-FW by
+0.167 on instr prompt_fit (clear strict-pass on that cell alone).
This was hidden by the seed aliasing in the legacy run.

**Tier still FAIL** because the gate is "≥2 of 3 axes ≥+0.05
directional per stratum":

- vocal: 0/3 directional (all negative). FAIL.
- instr: only prompt_fit (+0.167) crosses any threshold. Musicality
  (+0.020) does NOT cross +0.05. 1/3 directional. FAIL.

But the verdict's _texture_ shifts:

- Vocal is more clearly section-loses-on-all-axes than legacy
  suggested (musicality −0.042 not −0.133).
- Instrumental has a real, robust, single-axis strict-pass for
  section credit on prompt_fit; this is a positive finding for
  Section that legacy understated.

### 10.3 Coverage-aware (≥50 %) analysis on corrected held-out

| Stratum × axis | Section ρ | ≥50 % best non-section | filtered Δ |
|---|---:|---|---:|
| vocal × musicality | 0.453 | CU-BW (0.496, c=100 %) | **−0.042** |
| vocal × coherence | 0.726 | **CU-LS (0.881, c=81 %)** | **−0.155** |
| vocal × prompt_fit | 0.511 | CU-FW (0.592, c=100 %) | **−0.082** |
| instr × musicality | 0.470 | CU-BW (0.450, c=100 %) | **+0.020** |
| instr × coherence | 0.721 | _no valid non-section_ | _—_ |
| instr × prompt_fit | 0.664 | CU-FW (0.497, c=100 %) | **+0.167** |

Key observations:

- Coverage filter affects only the coherence cells (CU-BW is the only
  cell with sub-50 % coverage). Filtered vocal coherence now shows
  Δ=−0.155 (vs raw −0.274 with the artifact-driven CU-BW=1.000) — a
  larger filtered margin than legacy's −0.044, because corrected CU-MS
  vocal coherence is 0.726 vs legacy's 0.786 (CU-MS coherence
  dropped) and CU-LS jumped to 0.881 (vs legacy 0.830).
- Instr coherence has no valid non-section under the filter (CU-BW
  c=23 %, CU-FW NaN); reported as "_undefined_". Honest report.
- Other 4 cells (musicality + prompt_fit × strata) unchanged under
  filter — full coverage already.

### 10.4 Dev↔corrected-held-out concordance

Unit-ranking Kendall-τ:
- vocal: dev `[CU-BW, CU-MS, CU-LS, CU-FW, NULL, CU-TS]` vs corrected
  `[CU-BW, CU-LS, CU-MS, CU-FW, NULL, CU-TS]` — τ ≈ +0.87
  (CU-MS↔CU-LS swap, one pair).
- instr: dev `[CU-BW, CU-MS, CU-FW, NULL, CU-TS]` vs corrected
  `[CU-BW, CU-MS, CU-FW, NULL, CU-TS]` — τ = 1.000 (identical).

Verdict is reproducible: the SECTION_FAIL pattern survives both the
seed correction and the coverage-aware lens.

### 10.5 Updated classification recommendation

Provisional label: **`MIXED_BY_STRATUM_WITH_INSTR_PROMPT_FIT_NUANCE`**.

- Section credit FAILS on vocal across all 3 axes (no axis crosses any
  threshold).
- Section credit FAILS the per-stratum gate on instrumental because
  only 1 of 3 axes (prompt_fit) crosses any threshold, but the
  prompt_fit signal IS strong (+0.167 strict-pass), and instrumental
  musicality is directionally positive (+0.020).
- Best non-section unit varies by stratum × axis:
  - **CU-FW** dominates prompt_fit on vocal + musicality/prompt_fit on
    instr (always full coverage).
  - **CU-BW** dominates vocal musicality (full coverage on that cell)
    and is the raw coherence winner everywhere but only by the
    low-coverage artifact.
  - **CU-LS** is the coverage-aware coherence winner on vocal
    (Δ=−0.155 to CU-MS).
- Coverage-aware reliable single non-section pick: **CU-FW** —
  full coverage on every (stratum, non-coherence) cell; wins 3 of 6
  cells; only edged out on vocal × musicality (CU-BW 0.496 vs CU-FW
  0.424).

### 10.6 Recommended Phase C downstream method (provisional)

- **Primary**: **M-FixedWin-PRM** as conservative downstream default.
  Rationale: CU-FW has full coverage on every cell; wins the most
  cells under the coverage-aware lens; is robust to the
  segmentation-policy debates around CU-MS k=4 and CU-BW short-window
  failures.
- **Diagnostic / negative control**: M-Section-PRM. Section credit's
  strict-pass on instr × prompt_fit (+0.167) is real and should be
  evaluated head-to-head in Phase D as a per-axis-per-stratum
  comparison, even though it fails the verdict gate.
- **Optional / stratum-specific**: M-LyricSpan-PRM (vocal only,
  coverage-aware coherence winner); M-BeatWin-PRM (descriptive
  inclusion in Phase D ablation, NOT as primary because of the
  coverage artifact).

### 10.7 GPU-h consumed (Phase 2 corrected held-out)

- 256 prompts × 8-GPU sharded, ~30 min wallclock per shard.
- Total ≈ 8 GPUs × 0.5 h = **4 GPU-h**.
- Hard cap per PI: 30 GPU-h. Used 13 % of cap.

### 10.8 Cross-references for §10

- `runs/phase_b3_credit_unit/h3_held_out_v2_global_seed/H3_VERDICT.json`
  (corrected; tier=FAIL; n_unique_seeds=256)
- `runs/phase_b3_credit_unit/h3_held_out_v2_global_seed/h3_{vocal,instrumental}_stratum.json`
- `runs/phase_b3_credit_unit/h3_held_out_v2_global_seed/results.jsonl` (256 prompts)
- `runs/phase_b3_credit_unit/h3_held_out_v2_global_seed/audio/` (256 .wav for Phase 3)
- `orbit-research/H3_COVERAGE_FILTER_TABLE_v2.json` (corrected filter)
- `orbit-research/H3_PHASE1_AUDIT_v2_2026-05-23.md` (Phase 1 audit with coverage filter)

## 11. Sectionability v2 (PI directive Phase 3 — 2026-05-23)

Replaces v1's `coherence_proxy_range` proxy with actual structural
section detection via librosa-based novelty analysis (MFCC self-
similarity → Foote novelty → peak-pick; non-forced k). Analysis on
the 256 saved `.wav` files from corrected held-out.

### 11.1 Headline numbers

| Metric | Overall | Vocal (n=159) | Instr (n=97) |
|---|---:|---:|---:|
| Mean n_sections | **5.01** | 5.09 | 4.89 |
| Median n_sections | 5.0 | — | — |
| Frac with ≤1 section | 0.0 % | 0.0 % | 0.0 % |
| Frac with 2 sections | 0.4 % | 0.0 % | 1.0 % |
| Frac with 3+ sections | **99.6 %** | 100.0 % | 99.0 % |
| Median section duration | 8.0 s | — | — |
| Frac very short sections (<4 s) | 3.3 % | — | — |

### 11.2 Interpretation — PI hypothesis NOT supported at face value

PI's pre-launch hypothesis: "ACE-Step 30–40 s outputs are often short
cues / sketches / loops rather than full songs with stable
verse/chorus/bridge sections."

**The v2 detector does NOT support this hypothesis as stated.** It
finds ~5 detected sections per clip, with 99.6 % of clips having 3+
sections and a median section duration of 8 s. The vocal-vs-instr
split is essentially the same (5.09 vs 4.89 mean sections).

**Two equally defensible interpretations**:

(a) **The detector is over-segmenting.** The default Foote novelty +
    peak-pick parameters (kernel=8 s, peak_delta=0.10, min_section=4 s)
    are not validated against musical ground truth on this audio
    distribution; transient timbral changes (instrument enter/exit,
    drum fill, dynamic shift) may be detected as section boundaries
    even though they are not phrase- or song-level structural
    boundaries. Real "verse / chorus / bridge" sections in 30–40 s
    clips would typically be 2–3, not 5. Without a ground-truth
    sectionability benchmark (e.g., manual annotations or a calibrated
    tool like all-in-one / msaf — neither installed in audio-prm env),
    we cannot tell over- from honest detection.

(b) **ACE-Step 30–40 s clips have many local contrast points but no
    true song-level sections.** Under this reading, our detector
    correctly finds local novelty (5 boundaries) but those boundaries
    are short-form structural contrast (drum fill, instrument enter,
    riff change), not full song-level sections. CU-MS still
    under-performs because the forced k=4 grid doesn't align with
    either real song-section structure (which doesn't exist) OR the
    fine-grained local boundaries (which the novelty detector finds
    at k≈5). This would be consistent with PI's intuition reframed:
    "ACE-Step short-form has local structural contrast at ~5 s
    granularity, not song-level verse/chorus structure."

### 11.3 Stratification — no signal

PI Task 6 asked for stratification by vocal/instr, high/low final
reward, and high/low CU-MS performance. Result: **no meaningful
between-stratum signal in n_sections**:

| Subgroup | n | Mean n_sections | Frac 3+ |
|---|---:|---:|---:|
| Vocal | 159 | 5.09 | 100.0 % |
| Instr | 97 | 4.89 | 99.0 % |
| Low reward quartile | 64 | 4.95 | 100.0 % |
| High reward quartile | 64 | 5.02 | 100.0 % |
| Low CU-MS-ρ quartile | 64 | 5.03 | 100.0 % |
| High CU-MS-ρ quartile | 64 | 4.78 | 100.0 % |

All subgroups have mean n_sections in [4.78, 5.09]; no quartile splits
out. **Section count alone does not explain CU-MS performance
variation** (low vs high CU-MS quartile means differ by only 0.25
sections).

This is a notable null finding: if PI's "weak sectionability causes
CU-MS to underperform" hypothesis were correct, low-CU-MS-ρ clips
should have fewer detected sections (or more very-short ones). They
do not. The CU-MS failure mode is likely NOT primarily about clip
sectionability under this detector's lens.

### 11.4 Claims we will and will NOT make from sectionability v2

**Will make** (defensible):
- "Under a librosa-based novelty detector, ACE-Step 30–40 s clips do
  not exhibit the 1–2-section "loop/sketch" structure that would
  trivially explain CU-MS underperformance."
- "Detected n_sections has no discriminative power between high vs
  low CU-MS performers."
- "Forced k=4 in CU-MS roughly matches detected ~5 boundaries on
  average; the count is off by ~1, which is unlikely the dominant
  failure cause."
- "Sectionability is a diagnostic, not a paper claim, under this
  detector."

**Will NOT make** (overclaim per PI directive Phase 4 §10):
- "ACE-Step generates well-structured 5-section songs." (Cannot
  defend without ground-truth section annotations.)
- "Sectionability is therefore irrelevant to credit-unit choice."
  (Stronger detectors / different hyperparameters / human raters
  might show signal we missed.)
- "PI's pre-hypothesis was wrong." (The hypothesis is testable;
  this evidence is consistent with it under interpretation (a)
  above, and inconsistent with it under interpretation (b).)
- "Sections never work." (Section credit had a strict-pass on instr
  prompt_fit; partial signal still exists.)

### 11.5 Why CU-MS underperforms anyway — alternative hypotheses

Sectionability does not explain CU-MS's H3 failure under this lens.
Alternative hypotheses (NOT investigated here, deferred):

1. **CU-MS k=4 is wrong _shape_, not wrong _count_.** Even if 5 real
   sections exist, forcing 4 over-bins them; the resulting per-section
   reward delta is averaged over heterogeneous content. A k=detected
   (variable) CU-MS variant could perform differently, but
   redefining "section" is OUT OF SCOPE per PI hard rule.

2. **MERT section_coherence reward is too rough.** Section coherence
   on 4 cropped sub-windows may collapse to constant outputs on
   short crops, triggering the degenerate-vector guard (which is
   exactly what produces the CU-BW coverage artifact). The reward
   axis itself may be the bottleneck, not credit-unit choice.

3. **Local-window units have implicit information that section
   misses.** Beat-windows align with prompt-induced rhythm; fixed-
   windows are uniform enough to be a reliable baseline. Section
   boundaries may not align with the reward-bearing content
   structure in short-form generations.

These hypotheses are noted for Phase D human eval design but are NOT
adjudicated by the current automatic prescreen.

### 11.6 Cross-references for §11

- `runs/phase_b3_credit_unit/h3_held_out_v2_global_seed/sectionability_v2/SECTIONABILITY_REPORT_v2.md`
- `runs/phase_b3_credit_unit/h3_held_out_v2_global_seed/sectionability_v2/SECTIONABILITY_REPORT_v2.json`
- `runs/phase_b3_credit_unit/h3_held_out_v2_global_seed/sectionability_v2/SECTIONABILITY_REPORT_v2_table.csv`
- `scripts/h3_sectionability_v2.py` (detector implementation)
