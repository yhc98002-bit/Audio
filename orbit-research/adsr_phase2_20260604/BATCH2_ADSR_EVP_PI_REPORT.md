# Batch 2 — EVPD + ADSR Core Offline Decision: PI Report

**Decision label: `ADSR_CONDITIONAL`**
**Recommended next action: a TARGETED online pilot on type-risk prompts only (after explicit PI approval) — NOT broad online ADSR.**

## 1. One-paragraph verdict
Vocal/instrumental type error is real (23% of candidates) and **survives common-score selection**
(~20% among the common-score winners), so it is method-relevant. An Early Vocal-Presence Detector
(EVPD) trained on early-σ log-mels predicts final vocal presence **strongly and early** (held-out
AUC 0.94 by σ0.7, vs 0.74 for the existing scalar proxy; usable already at σ0.9, AUC 0.87). In the
matched-compute offline simulation, using EVPD to **guard the output against predicted type
mismatches** cuts the selected candidate's type-error from 0.168 to 0.121 (**−28% relative, paired
95% CI [0.012, 0.078], significant**), reaching below even full BoN-8's type-error at 0.767×
compute, with common reward preserved (0.998→0.994). **But** the win is **selection-driven, not
restart-driven** (restart-only adds ~−7%), it does **not** broadly improve common reward, and it
carries a small lyric tradeoff (EN-vocal lyric mean 0.400→0.368). EVPD is therefore a valuable
**conditional type-safety control**, concentrated on type-risk and lyric-bearing prompts — not yet
a validated broad ADSR-restart method.

## 2. Pre-flight status
All 8 hard checks PASS (`BATCH2_PREFLIGHT_CHECK.{md,json}`): 4096 distinct records, 512 prompts,
all final vocal labels present, 12288 early-σ mels, EN-vocal vocal_scorable = 282 (keys ==
canonical), instrumental 1.0 lyric sentinel maskable, non-EN vocal = 34 excluded, dev256/held256
split prompt-consistent.

## 3. Label reliability
Demucs vocal-presence label is reliable enough as the EVPD target: clean **bimodality** (GMM means
~0.0003 / 0.34, separation 0.34) and strong **request-type separation** (vocal-req median 0.342 vs
instrumental-req 0.017). Whisper lyric proxy is **orthogonal** (P(present|words)≈P(present|no-words)
≈0.80) and confounded by hallucination, so it is NOT used to validate presence. Near-threshold
ambiguous rate 13.6% → `vocal_ambiguous_check_packet.jsonl` (manual spot-check prepared, NOT run).

## 4. Type-error prevalence
Candidate type-error **0.23** (vocal-req→no-vocal 533; instr-req→has-vocal 409; 942/4096),
prompt-level affected 0.637; vocal prompts 0.211, instrumental 0.261; EN-vocal 0.201.

## 5. Survivor-set type-error rate
By common score: top-1 **0.199**, top-2 0.214, top-4 0.213 → type errors persist after simple
common-score selection ⇒ EVPD has genuine method headroom.

## 6. EVPD best model and metrics
Deployed = **mel-summary GBDT fused** (best on validation). Held-out **AUC 0.938, AUPRC 0.955**
(vs presence prevalence 0.576), prompt-level bootstrap AUC 95% CI [0.876, 0.912]. Type-error
detection precision 0.61 / recall 0.64; survivor-top-1 catch 0.47; restart-rate 0.23, false-restart
39% of restarts. Mel features ≫ scalar proxy and ≫ the small CNN (small train set). Models, splits,
metrics: `EVPD_RESULTS.{md,json}`, `EVPD_SPLIT_REPORT.md`, `EVPD_MODEL_CARD.md`.

## 7. EVPD onset σ
EVPD *detection* is usable by **σ≤0.7** (AUC 0.940); earlier works for detection too (σ0.8 0.916,
σ0.9 0.872, all ≫ 0.74 scalar proxy). **BUT the σ-decision sim frontier (`ADSR_SIGMA_FRONTIER.md`,
addendum on an22) shows the POLICY benefit needs σ≥0.8:** at σ0.8 (compute 0.70) type-error
0.191→0.133 (−31%), at σ0.7 (0.767) 0.168→0.121 (−28%), but at **σ0.9 (0.617) the reduction is 0.0**
— the weaker σ0.9 model's false-restarts offset its true ones. Lesson: high AUC ≠ policy value; the
earliest *effective* decision point is **σ0.8** (cheapest compute at which the win holds).

## 8. ADSR+EVPD offline result
Matched compute 0.767 (`ADSR_FULL_OFFLINE_RESULTS.{md,json}`, `ADSR_COMPUTE_ACCOUNTING.md`):
full_bon8 TE 0.184 (compute 1.0); common_restart 0.168; adsr_evpd (restart-only) 0.156;
**adsr_evpd_select 0.121**; bon4 0.172 (compute 0.5). Reward_fraction stays ≥0.994 for all EVPD
policies. ADSR-noEVPD == common_restart in this fixed-pool sim.

## 9. Comparison against common-score restart
adsr_evpd_select vs common_restart at matched compute: type-error **0.168→0.121 (−28% rel)**,
paired 95% CI [0.012, 0.078] (significant; 16 prompts fixed vs 4 regressed, net 12/256),
reward_fraction Δ −0.0046 (negligible). Restart-only is only −7% — **the gain is EVPD-aware
selection, not restart**.

## 10. Lyric-bearing subset result
EN-vocal vocal_scorable (sentinel excluded): type-error common 0.163 → adsr_evpd_select **0.088**
(nearly halved); reward_fraction 0.976→0.970; lyric mean 0.400→0.368 (small dip — the one tradeoff).

## 11. Compute accounting
Project-standard steps: σ0.9=7, σ0.8=12, σ0.7=16, FULL=30. σ0.7-decision policies: 8 cands to σ0.7
(128 steps) + 4 to final (56) = 184/240 = **0.767**. BoN-4=0.5, BoN-8=1.0. Limitation: fixed-pool
"restart" ≠ true online fresh-seed restart; small EVPD inference overhead ignored.

## 12. Codex audit verdicts
Stage-2 plan audit: sound, no critical flaw (blocking safeguards baked in). Stage-5 results audit
(`CODEX_REVIEW_BATCH2_RESULTS.md`): decision `ADSR_CONDITIONAL`; leakage/threshold/AUPRC/compute/
lyric-scope all PASS; prevalence & survivor-set correct; 3 BLOCKING doc/stats fixes (document
adsr_evpd_select, attribute win to selection not restart, add paired uncertainty) — **all applied**.
Codex flagged overreach risk on "ADSR restart works" / "quality preserved without cost"; report
wording avoids both.

## 13. Boundary confirmation
- no RL launched; no pruning+RL launched; no Phase D launched; no crowdsourcing/human-eval launched;
  no online ADSR pilot launched.
- no `gate_v1.yaml` modification; no reward-definition change; no prompt-split change.
- no lyric-sentinel leakage (instrumental 1.0 excluded from every lyric metric; EVPD has no lyric/
  Whisper input).
- no proposal/paper rewrite; **no paper success claim made.**
- EVPD models are lightweight (logistic/GBDT/small CNN); no large transformer; CPU labeling (0 GPU-h),
  EVPD training on an17 GPUs.

## 14. Recommended next action
Run a **targeted online pilot on type-risk prompts only** (vocal/instrumental constraint-bearing),
using EVPD as an early type-mismatch guard **at selection** (and as a restart trigger to recover
compute), at a **σ0.8 decision point** (the cheapest σ at which the type-error reduction holds per
the frontier; σ0.9 is too early in-policy), **after explicit PI approval** (online pilot is a
Batch-3 boundary item, NOT launched here). Do NOT run broad online ADSR: the common-reward gain is ~nil and the restart mechanism alone
is not validated. Optional pre-pilot: manual spot-check of the ambiguous packet to firm up the
Demucs label as ground truth; consider lyric-defer refinement to remove the small lyric dip.
