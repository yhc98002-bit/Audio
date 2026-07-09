# Experiment Plan Exec v4.0 — Axis-Deferred Speculative Restart (ADSR) for Flow-Matching Music Generation

| Field | Value |
|---|---|
| Version | **v4.0 ADSR reframe, 2026-06-04** |
| Status | `STOP_A_READY_FOR_PI_APPROVAL` — supersedes v3.0.1 (ETV pruning ladder). The ETV pruning ladder is retained as a **baseline** (raw ETP + learned-verifier selection), not the headline; the M-PRM ladder remains the boundary RL paragraph and is not in the active run order. |
| Authoritative spec | `ADSR_Research_Plan_FINAL_EN_2026-05-29.md` (PI frozen FINAL plan). This exec plan implements ADSR §6 (E1–E9) under the execution staging of ADSR §11 (Phases 1–7). |
| Pre-revise (ETV) snapshot | `orbit-research/archive/etv_pre_adsr_20260604/refine-logs_EXPERIMENT_PLAN_EXEC.md` |
| Paper-framing reminder | C1 (axis×σ observability map + human early→final validation) + **C2 ADSR (main; reallocation via restart/defer/continue, not selection)** + **C3 prompt-type match via learned EVPD (NEW)** + C4 compute–quality Pareto over BoN-k / Full-BoN / random / raw-ETP / learned-verifier / type-match restart / ADSR + **C5 lyric as first-class late-observable axis (lyric-bearing vocal subset only)** + C6 RL post-training boundary. See `FINAL_PROPOSAL.md` v4.0 §3 and ADSR §3. |
| Evidence status | **Plan-stage proposal for the ADSR method, anchored on existing foundation evidence.** Foundation EXISTS (H1/H2 persistence; Track A raw-ETP Schedule-A 0.9864@0.500; lyric 0.682 EN-vocal n=282; Track B globalness 0.861; C1 RL boundary; large-scale human listening). **NOT yet run:** E3 EVPD is not trained; E6 restart/ADSR not run (offline-simulatable only on the 4096 pool); vocal-presence labels not yet derived; H2b presence/content split unmeasured; cross-backbone not started. **Do NOT claim ADSR results that do not exist.** |
| Compute envelope | ~0 GPU-h for the offline-first core (E1, E4, E5, E6-offline, E7-offline on cached records); EVPD training (E3) is GPU but small (≤ ~30 GPU-h on cached early-σ mel + relabeling); E6/E7 small real-generation confirm ≤ ~150 GPU-h; E9 cross-backbone is parallel and does NOT gate submission; ~10–15 listener-hours for E2 + E8 human work. |

---

## 0. Paper-framing summary

The paper's primary deliverable is **ADSR — axis-deferred speculative
restart** — a compute **reallocation** method (RESTART / DEFER / CONTINUE),
**not** a fixed-pool prune/select method. The headline artifacts are:

1. The **axis×σ observability map** (E1) with vocal *presence* and lyric
   *content* as **separate rows**, expecting vocal-presence-onset ≪
   lyric-onset (the scientific core, H2/H2b).
2. The **same-compute Pareto curve** (E4 + E5 + E6) of
   (reward_fraction, expected_compute_fraction) across
   {Full BoN-8, BoN-4, random prune/restart, raw ETP Schedule {A, B, C,
   bottom-prune σ0.7}, learned-verifier selection, **type-match restart**,
   **ADSR**}, scored at **matched expected total NFE**.
3. The **EVPD + prompt-type-error study** (E3) — a learned early
   vocal-presence detector (an audio model) establishing that gross
   type errors (vocal↔instrumental) are early-catchable (C3, H5).
4. The **lyric-focused deferred evaluation** (E7) on the **lyric-bearing
   vocal subset only** (no instrumental-sentinel pollution), demonstrating
   why deferral is necessary (C5).
5. **Human early→final validation** (E2) as the empirical license for
   restart, and a **human spot-check** (E8) where human judgment overrides
   automatic reward.

The boundary section (M-PRM RL first-wave, §7) reuses
`PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md` directly; **no new RL training
is scheduled.**

**What is new vs the ETV exec plan (v3.0.1):**
- The headline is **restart/defer/continue reallocation**, not pruning a
  fixed candidate pool. Raw ETP becomes a baseline (E4).
- A new **learned audio model (EVPD)** is trained (E3) and a new
  **vocal-presence label** is derived for the 4096 candidates.
- A new **presence-vs-content split (H2b)** disentangles lyric-zero
  candidates into type errors vs content failures.
- **Lyric** is promoted to a first-class late-observable axis on the
  **lyric-bearing vocal subset** with the corrected 0.682 EN-vocal (n=282)
  number; the masked instrumental-sentinel 1.0 is excluded.
- E1–E6 → **E1–E9**; the §11 ICLR audit and the Claude Code audits are
  preserved and extended for the restart-accounting and EVPD-leakage cases.

---

## 0.5. Dataset construction (candidate-level)

ADSR consumes the cached Track A 4096-candidate record set plus a **new
retroactive vocal-presence relabeling pass**. Offline ADSR simulation and
the learned quality verifier require **no new GPU forward passes**; EVPD
training and the small real-generation confirm are the only GPU items.
Construction is a strict, auditable read-only pipeline that converts the
cached JSONL records (+ the relabel pass) into a feature matrix + label
vector with provenance.

### 0.5.1 Source records

- Run root: `runs/early_tweedie_validation_512_bon8_20260527_full01/` (380
  unchanged prompts) + `runs/early_tweedie_validation_final_lyricfix_20260603/`
  (132 regenerated, 2026-06-03 lyric fix). Canonical merged reward set:
  `orbit-research/trajectory_candidate_dataset.jsonl` (promoted 2026-06-04).
- Per-shard JSONL: `shard{00..07}/candidate_records.jsonl` (~512
  candidates per shard, 4096 total).
- Each record holds: `prompt_id`, `candidate_idx` ∈ {0..7},
  `prompt_type` (vocal / instrumental, **requested**), per-σ scores
  (`r_lcb`, `aesthetic_pq`, `clap`, `mert`, `lyric_wer` where applicable)
  at σ ∈ {0.9, 0.8, 0.7, final}, and the final scores.
- **Lyric scoring (R2 lyric-fix, retained).** `lyric_intelligibility` is
  scored **EN-vocal only** (n=282 lyric-bearing English vocal prompts;
  248/282 = 88 % carry usable signal). Instrumental prompts carry a masked
  `1.0` sentinel that **must never enter** any lyric metric; non-English
  prompts are excluded from the EN headline (stress arm reported
  separately). See
  `orbit-research/prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md`.

### 0.5.2 Per-candidate feature extraction

**(a) Scalar quality features** (for the learned quality verifier and for
the offline ADSR decision logic) — for candidate `(c, i)` with σ ∈ {0.9,
0.8, 0.7}:

| Feature | Definition |
|---|---|
| `r_lcb_sigma9` | `r_lcb(â_{c,i,σ=0.9})` |
| `r_lcb_sigma8` | `r_lcb(â_{c,i,σ=0.8})` |
| `r_lcb_sigma7` | `r_lcb(â_{c,i,σ=0.7})` |
| `slope_lcb` | `r_lcb_sigma7 − r_lcb_sigma9` |
| `rank_sigma9` | within-prompt rank at σ=0.9 (1 = best of 8) |
| `rank_sigma8` | within-prompt rank at σ=0.8 |
| `rank_sigma7` | within-prompt rank at σ=0.7 |
| `prompt_type` | categorical: `vocal` / `instrumental` (requested) |
| `lyric_bearing_flag` | binary; lyric-bearing vocal prompt (EN-core / stress arm tag) |
| `aux_pq_sigma7` (ablation) | `aesthetic_pq(â_{c,i,σ=0.7})` |
| `aux_clap_sigma7` (ablation) | `clap_semantic(â_{c,i,σ=0.7})` |
| `aux_mert_sigma7` (ablation) | `mert_section_coherence(â_{c,i,σ=0.7})` |
| `uncertainty_sigma7` (ablation) | per-ensemble reward std at σ=0.7 |

**(b) Audio/spectrogram features** (for the EVPD audio model) — the
**early Tweedie-clean mel-spectrogram** of `x̂₀ = x_σ − σ·v_θ` decoded at
σ ∈ {0.9, 0.8, 0.7}. EVPD reads the mel directly; it does NOT use the
scalar features. The mel cache is built once from the cached latents /
re-decoded Tweedie estimates and stored under
`runs/adsr_evpd_melcache_<YYYYMMDD>/`.

### 0.5.3 Labels (per candidate)

- `r_final` — final robust-LCB after full denoising (target for the
  quality-verifier regression).
- `final_rank` — within-prompt rank of `r_final` (target for the
  ranking objectives).
- `is_winner` — `1` iff candidate is the within-prompt top-1 by
  `r_final`.
- **`final_vocal_presence` (NEW).** Binary final vocal-presence label per
  candidate, derived in §0.5.6. This is the EVPD ground-truth target and
  the H2b presence axis.
- **`type_match` (NEW, derived).** `1` iff `final_vocal_presence` matches
  the requested `prompt_type` (vocal-requested→voice-present, or
  instrumental-requested→voice-absent). Mismatch = gross type error.
- **`lyric_zero_cause` (NEW, derived; lyric-bearing vocal only).**
  Categorical: `type_error` (no voice → no transcription) vs
  `content_failure` (voice present but unintelligible) vs `ok`. This
  operationalizes the presence/content split (H2b).

### 0.5.4 Group structure

Each prompt is a query group (8 candidates) for the ranking objectives
(LGBMRanker, LambdaMART) and for the offline ADSR pool ("restart" draws
the next independent candidate within the same prompt's pool — see §0.7).
No cross-prompt pairs are sampled.

### 0.5.5 Provenance

The feature-extraction + relabel pipeline must log to `RUN_LEDGER.jsonl`:
- record file SHA256 (per shard).
- feature schema version (`adsr_features_v1`; supersedes `etv_features_v1`).
- vocal-presence relabel method + threshold + tool version
  (`adsr_vocalpresence_v1`).
- prompt-count check (`512 ± 0`).
- candidate-count check (`4096 ± 0`).
- lyric-subset count check (`EN-vocal n = 282`).
- post-extraction matrix dimensions + mel-cache dimensions.

Any deviation → STOP and escalate. The Claude Code leakage audit (§5.1)
verifies no field derived from `r_final`, `final_vocal_presence`, or
`type_match` is present in the scalar feature matrix, and that the EVPD
mel features are computed from the **early Tweedie estimate**, never the
final audio.

### 0.5.6 Vocal-presence label derivation (NEW — Phase 1)

Final vocal-presence per candidate is derived from the **final** rendered
audio (label, not feature):

1. **Primary:** source-separation vocal-energy ratio — Demucs (or
   Spleeter) 4-stem; compute `vocal_energy / total_energy`; threshold
   calibrated on a small hand-labeled audit set (≥ 100 candidates,
   balanced vocal/instrumental) to fix the presence cut.
2. **Cross-check:** a dedicated singing-voice-detection (SVD) model where
   available; disagreements are hand-audited.
3. **Coarse pre-filter only:** Whisper `no_speech_prob` may pre-screen,
   but is NOT the label — Whisper targets speech not singing, and
   instrumental audio can false-trigger. Pre-register this caveat.

The label is written back to all 4096 candidates (`final_vocal_presence`,
`type_match`, `lyric_zero_cause`). This relabel is a **Phase-1 gate item**;
no EVPD training (E3) or ADSR type-match branch (E6) may run until it
exists and passes the leakage audit.

**Evidence status:** the vocal-presence label is **not yet derived** —
this is new work. All downstream EVPD / type-match claims are PLANNED.

---

## 0.6. Prompt-level train / val / test split

ADSR uses a **three-way split at the prompt level** to separate
hyperparameter selection from final evaluation, preserving the canonical
Track A dev/held-out boundary. The split is shared by the quality verifier
(E5), the EVPD audio model (E3), the offline ADSR simulation (E6/E7), and
all calibration.

| Split | Source | n_prompts | Use |
|---|---|---:|---|
| **train** | Track A dev (random 80 % within dev split, seed 20260528) | 205 | quality-verifier + EVPD fit; risk/threshold calibration target construction |
| **val** | Track A dev (remaining 20 %, same seed) | 51 | hyperparameter selection (GBDT leaves/lr; EVPD architecture/early-stop; ADSR thresholds σ_c, decision cutoffs); 5-fold CV reported |
| **test** | Track A held-out (untouched 256 prompts) | 256 | E1 / E3 / E6 / E7 final evaluation; NOT used for any model selection |

Notes:
- **Generalization scope (prompt-set audit `prompt_set_audit_20260529/`).**
  The dev/held-out split is **cross-prompt** (seen vocabulary, unseen prompt
  combination), **NOT cross-content**: the instrument-clause vocabulary is
  81–94 % shared across dev/held-out. This is benign for the scalar quality
  verifier (no instrument-text feature; only early-σ reward/rank + a binary
  vocal flag; within-prompt ranking marginalizes prompt-level constants) and
  for EVPD (it reads audio, not prompt text) — but the paper must word it as
  **cross-prompt, not novel-content.** Report all dev→held-out comparisons
  **per specificity stratum**: dev rewrote 100 % of its broad prompts to
  natural style vs held-out 47 %, a confound the aggregate "splits matched on
  reward" check hides (it passes only by a coincidental composition offset).
  `lyric_intelligibility` comparisons are **EN-vocal only (n=282)**.
- 80/20 train/val split is at the **prompt level**, not the candidate
  level. All 8 candidates of a prompt either appear in train, val, or
  test — never split across. **Split by `prompt_id`, never by
  `candidate_id`** (prevents same-prompt candidate leakage; this is
  critical for both the verifier and EVPD).
- The **lyric-bearing vocal subset** (EN-core n=282 + stress arm) inherits
  the same prompt-level boundary; lyric metrics are reported per stratum
  (clean-English-core / broader-lyric-bearing-vocal / multilingual-or-
  thin-lyric stress arm) and never mixed with instrumental prompts.
- Seed `20260528` is recorded in `RUN_LEDGER.jsonl`; the split is
  reproducible via `scripts/adsr_split.py` (to be written by
  `/experiment-bridge`; supersedes `scripts/etv_split.py`).
- The held-out 256 prompts (test) are touched **once** for the final
  Pareto curve and the final observability/EVPD/ADSR evaluation. Repeated
  test-set evaluation during development is forbidden by the
  same-compute-fairness audit (§5.2).
- EVPD and ADSR-threshold calibration use 5-fold cross-validation on the
  train+val pool; thresholds are calibrated on each fold's held-out
  portion to avoid leakage.

The boundary RL section (§7) cites the existing Phase C1 evaluation
unchanged; no new prompt split is required for the boundary paragraph.

---

## 0.7. Offline-first ADSR protocol (the load-bearing accounting trick)

ADSR is **validated offline first** on the existing 4096-candidate pool,
then confirmed by a small real-generation run. This is the cheapest valid
diagnostic and the primary defense against optimistic compute accounting.

**Offline simulation semantics.** Within a prompt's 8-candidate pool, an
ADSR run proceeds candidate-by-candidate in a fixed seed order:
- For the candidate under inspection, the decision logic reads its cached
  early-σ scores (and, for the type-match branch, its EVPD prediction on
  the cached early mel).
- **RESTART** = terminate this candidate at σ_c and **draw the next
  independent candidate from the pool** (a new seed already generated).
  Cost charged = partial cost to σ_c only.
- **DEFER** = continue this candidate to a later σ before deciding;
  cost charged = the extra denoising steps to that σ.
- **CONTINUE** = run this candidate to completion; cost charged = full
  denoise.
- The run ends when the budget (expected total NFE) is exhausted; the
  selected output is the best CONTINUE-completed candidate by `r_final`.

**Compute accounting (matched expected total NFE; ADSR §4.5).** No
optimistic accounting. Total charged NFE =
`Σ partial-to-σ_c (restarted) + Σ full (continued) + Σ deferred-continuation
+ restart new-seed cost`. All baselines are evaluated at the **same expected
total NFE** so the Pareto x-axis is honest. The pool is finite (8/prompt),
so the offline simulation reports both (a) the in-pool result and (b) an
extrapolated-restart estimate where "the next seed" is sampled from the
empirical within-prompt reward distribution; the real-generation confirm
(below) checks the extrapolation.

**Real-generation confirm (small).** After the offline result is positive,
confirm on a **stratified subset of ≤ 64 held-out prompts** by actually
launching restart seeds at decision time (true new independent seeds, not
pool draws). This is the only place ADSR consumes non-trivial new GPU
(≤ ~150 GPU-h). It validates that pool-draw "restart" is a faithful proxy
for true restart.

**Evidence status:** the offline ADSR simulation and the real-generation
confirm are **not yet run.** Only the foundation (Track A pruning, H2
persistence) exists. ADSR's reallocation result is PLANNED.

---

## 1. Nine experiments — run order and go/no-go

Run in the staged order of §8 (Phases 1–7). Each gate must pass before
the dependent experiment commits non-trivial compute. The offline-first
core (E1, E4, E5, E6-offline, E7-offline) is ~0 GPU-h; the gates exist to
avoid wasting GPU on EVPD training / real-gen confirm / listener-hours on a
foundation that hasn't re-confirmed, and to honor the make-or-break Phase-3
gate (ADSR must beat BoN-k/random under fair compute).

Legend: **[REUSES]** = runs post-hoc on cached records / existing evidence;
**[NEW-RUN]** = needs new compute (GPU training or real generation).

### E1 — Axis × σ observability matrix (FOUNDATION) [REUSES + small relabel]

**Pre-condition:** Track A cached records exist; verifier signature matches
`EARLY_TWEEDIE_VALIDATION_VERIFICATION_REPORT.json`; vocal-presence
relabel (§0.5.6) complete.

**Workload:**
- Recompute (paper-grade) the per-(axis, σ) Spearman early-vs-final table
  on 512 prompts × 8 candidates from cached records.
- **Axes (rows):** common/robust quality, aesthetic/production,
  **vocal presence (coarse)**, semantic_fit, coherence,
  **lyric intelligibility (fine) on the lyric-bearing vocal subset only
  (EN-core n=282)**. Vocal presence and lyric intelligibility are
  **separate rows** (H2b).
- σ (columns): 0.9 / 0.8 / 0.7 / 0.5 / 0.3 / final (cached σ are 0.9/0.8/0.7
  + final; intermediate σ that are not cached are marked N/A and filled by
  the real-gen confirm if needed).
- Winner-retention top-{1, 2, 4} per σ; bottom-25 false-negative per σ;
  vocal vs instrumental stratification; per-specificity-stratum reporting.
- **Fix the lyric stratum first:** remove the instrumental `1.0` sentinel;
  use the EN-vocal n=282 lyric scoring; report 0.682 ETP@50 as the
  foundation lyric number, not 0.8432.

**Compute:** 0 GPU-h, <1 CPU-h (relabel pass is a separate Phase-1 item).

**Output:** `AXIS_OBSERVABILITY_MATRIX.{md,csv}` + heatmap. Pre-register
the early/late σ thresholds.

**Go gate to E2 / E3:**
- σ=0.7 Spearman ≥ 0.5 on `common_robust_lcb` for ≥ 1 stratum (already
  satisfied per Track A 2026-05-28/2026-06-04).
- σ=0.9 top-4 retention ≥ 0.6 (already 0.6836).
- No regression vs Track A canonical numbers.
- **vocal-presence-onset ≪ lyric-onset** is observed (the scientific-core
  ordering H2/H2b is directionally supported). If vocal-presence onset is
  NOT earlier than lyric onset, flag for the Phase-1 gate decision (§8) —
  this routes to the H2b failure branch (§9).

**No-go:** if cached records have changed and the verifier signature
mismatches the canonical artifact, STOP and escalate to PI.

**Owner:** implementer (post `/experiment-bridge` Phase 1).

### E2 — Human early→final validation (license for restart) [REUSES + small listening]

**Pre-condition:** large-scale human-listening evidence exists (already
obtained, H6). E1 lyric stratum fixed.

**Workload:** write up the large-scale human listening as a first-class
result: (a) early-σ perceptual quality predicts final **human-judged**
quality; (b) uniform-badness quantified; (c) late-bloomer rarity; (d)
**humans can identify vocal presence early** — a small targeted listening
check on early Tweedie estimates at σ ∈ {0.9, 0.8, 0.7}. Distinct from the
method-preference spot-check (E8). This is the core defense against
reward-circularity and "what if you restart a late-bloomer."

**Compute:** 0 GPU-h; ~3–5 listener-hours for the targeted early
vocal-presence listening (the bulk reuses existing listening evidence).

**Go gate to restart claims:** humans support early decidability (both
overall quality persistence AND early vocal-presence audibility). If
humans do NOT hear vocal presence early, demote the type-match branch to a
later σ (§9) and report onset honestly.

**Owner:** human eval coordinator.

### E3 — Early Vocal-Presence Detector (EVPD) + prompt-type-error study (NEW) [NEW-RUN]

**Goal:** establish that vocal presence is early-decidable and that gross
type errors (vocal↔instrumental) are catchable early. This trains the
**learned audio model** that distinguishes ADSR from a scalar-feature
pruner.

**Pre-condition:** vocal-presence relabel (§0.5.6) complete; mel-cache
built (§0.5.2b); E1 directional ordering supports vocal-presence-onset
earlier than lyric-onset (or the Phase-1 gate explicitly authorizes
training anyway to measure the onset).

**Workload:**
1. **Ground truth:** `final_vocal_presence` per candidate (§0.5.6).
2. **Prevalence:** rate of vocal-prompt→instrumental and
   instrumental-prompt→vocal errors (a useful result in itself).
3. **Detector:** train EVPD on early Tweedie-clean mel-spectrograms (σ ∈
   {0.9, 0.8, 0.7}) with the `final_vocal_presence` label. Architecture:
   small CNN OR fine-tuned pretrained audio encoder (per METHOD_SPEC ADSR
   §4.2b); model selection on val. Report early-detectability **AUC** and
   the **vocal-presence decidability onset σ** (smallest σ at which AUC ≥
   pre-registered cut, e.g. 0.85). For error cases specifically, test
   whether the early estimate already shows the wrong type.
4. **Baseline:** off-the-shelf (clean-audio-trained) vocal detector applied
   to the early estimate, to show the early-σ domain is OOD and warrants a
   learned early detector.
5. **Disentangle existing data (H2b):** split the current lyric-zero
   candidates into `type_error` (no voice → no transcription) vs
   `content_failure` (voice present but unintelligible) using
   `lyric_zero_cause` — exactly the presence/content distinction.
6. **Closed loop (offline):** show that type-match restart improves the
   final selected output's **prompt-type-match rate** vs no restart on the
   cached pool.

**Compute:** ≤ ~30 GPU-h (mel-cache build + EVPD training on cached
early-σ mel; small models, train/val only). Inference is cheap.

**Metrics:** AUC per σ, onset σ, type-error prevalence, prompt-type-match
rate after restart, false-restart rate on type, EVPD-vs-off-the-shelf gap.

**Go gate (make-or-break with E6):** EVPD AUC at some early σ is
materially above chance and above the off-the-shelf baseline, AND the onset
σ is earlier than the lyric onset. If vocal presence is NOT early-decidable
(onset late) → demote type-match to a later-σ check; report onset honestly
(§9); ADSR can still run without the EVPD branch.

**Evidence status:** **EVPD is NOT trained; this is new work.** No AUC /
onset number may be reported as existing until E3 runs.

**Owner:** implementer.

### E4 — Raw pruning & same-compute baselines [REUSES]

**Pre-condition:** E1 passed.

**Workload:** compare Full BoN-8 / BoN-4 (same compute) / random prune /
**raw Early-Tweedie Pruning (raw ETP, now a baseline)**. Schedules
A (σ0.9 top4 → σ0.7 top2 → top1), B (σ0.8 top4 → σ0.7 top2 → top1),
C (σ0.8 top6 → top1), bottom-prune (remove bottom-25 at σ0.7/0.8).
Compute fractions ∈ {0.500, 0.583, 0.850, 0.883, 1.000} (Track A canonical
points).

**Metrics:** compute/reward fraction, winner_match, top-2 retention,
false_negative, median regret.

**Critical comparison (frames why selection is low-stakes):** **raw ETP
Schedule-A vs BoN-4.** Track A canonical: Schedule A recovers **0.9864**
reward_fraction at **0.500** compute (regenerated 2026-06-04 on the
lyric-fix dataset; was 0.9858 on 2026-05-28); bottom-prune σ=0.7
false-negative **0.0195**. The known **raw-ETP-over-BoN-4 delta ≈ +0.0036**
(median regret ≈ 0) means **raw ETP cannot be the headline** — it motivates
restart (H3): fixed-pool selection is near-tied, so the leverage is in
reallocating compute, not in picking better within a tied pool.

**Compute:** 0 GPU-h, ≤2 CPU-h.

**Go gate to E6:** raw-ETP / BoN-4 / random baselines reproduce the Track A
canonical numbers within tolerance; the near-tie (delta ≈ 0.0036, regret
≈ 0) is confirmed as the motivation for restart.

**Owner:** implementer.

### E5 — Learned quality verifier [REUSES]

**Pre-condition:** E4 baselines reproduced.

**Workload:** train the **lightweight scalar quality verifier** (the
second learned component; NOT the headline, NOT a large model). Targets:
final robust-reward regression, final rank, top-1/2/4 survival, safe-restart
label, late-axis risk label. Models: raw early score (baseline) →
linear/ridge → GBDT / LambdaMART / pairwise (primary). No MLP/large model for
the scalar verifier (near-saturated: ridge within-prompt NDCG ~0.995, capacity
is not the bottleneck); EVPD (E3) is the only learned neural component.
Calibrate safe-restart and late-axis-risk thresholds on train+val 5-fold.

**Metrics:** Spearman, NDCG, survival AUC, false-negative at calibrated
thresholds, winner retention, reward_fraction under selection.

**Framing:** the verifier is useful if it improves **safe-restart
calibration / late-axis defer / Pareto** — not because it is complex.
Ridge already saturates within-prompt NDCG (~0.995); capacity is NOT the
bottleneck (the scalar-ranking label signal is limited by near-tied
candidates). This is the explicit answer to "why not a transformer here" —
and the contrast with EVPD (where audio perception under heavy noise IS a
genuine learning problem).

**Compute:** 0 GPU-h, ≤2 CPU-h.

**Go gate to E6:** verifier produces calibrated safe-restart and
late-axis-risk signals usable by the ADSR decision logic (the verifier
feeds the §4.4 priority-2/3 branches).

**Owner:** implementer.

### E6 — Axis-Deferred Speculative Restart (MAIN METHOD) [REUSES offline + NEW-RUN confirm]

**Pre-condition:** E3 (EVPD) trained; E5 (quality verifier) calibrated;
E1/E4 confirm the observability ordering and the selection near-tie.

**Workload:** run ADSR (restart / defer / continue per ADSR §4.4 priority
logic) on the cached pool (offline, §0.7), then a small real-generation
confirm. Compare, at **matched expected total NFE**:
Full BoN-8 / BoN-4 / random restart / raw restart / learned-verifier
restart / **type-match restart** / **axis-deferred restart (full ADSR,
including the EVPD type-match branch)**.

**Metrics:** expected compute (matched-NFE accounting, §0.7), final robust
reward, semantic & lyric preservation, **prompt-type-match rate**, winner
retention, false-restart rate, human preference (from E8).

**Ablations:**
- σ_c (decision σ), decision thresholds.
- sequential vs batch-speculative restart.
- restart budget.
- **two-factor ablation: axis-awareness × restart-reallocation** (the
  CONTROL_DESIGN headline ablation: is it the axis-deferral, the restart, or
  both?).
- **with / without the EVPD type-match branch.**

**Compute:** 0 GPU-h for the offline simulation (≤2 CPU-h); ≤ ~150 GPU-h
for the real-generation confirm on ≤ 64 stratified held-out prompts.

**Critical question (paper headline):** *At matched expected NFE, does ADSR
(with the EVPD type-match branch) beat same-compute BoN-k and random restart
on common/robust reward while preserving semantic/lyric preservation and
improving prompt-type-match rate?*

**Go gate (Phase-3 make-or-break, §8):**
- Offline ADSR beats same-compute BoN-4 and random restart on
  `common_robust_lcb` (pre-registered: ≥ 0.002 absolute reward_fraction
  gap with paired-bootstrap CI excluding zero) **and** does not regress
  lyric/semantic preservation on the lyric-bearing vocal subset.

**No-go decision tree** (per `orbit-research/NULL_RESULT_CONTRACT.md`
"2026-06-04 ADSR Pivot Addendum"):
- **ADSR ≤ BoN-4** → ADSR too weak as the main ICLR claim; fall back to an
  **axis-observability + trajectory-analysis paper** (C1 + E1 + E2 + Track B
  globalness mechanism), or a workshop/audio venue. Still run E7/E8/E9 to
  characterize the negative honestly.
- **ADSR ≤ random restart within noise** → restart-reallocation signal not
  separable; investigate decision logic / σ_c; report honestly.
- **ADSR improves common quality but hurts lyric** → axis-deferred logic
  insufficient; strengthen the defer branch (later σ for lyric) or restrict
  to non-lyric settings (§9).
- **EVPD branch adds nothing** (with≈without) → report type-match as a
  separate-axis result (C3) but drop it from the ADSR decision headline.

**Evidence status:** **ADSR / restart NOT run.** Offline-simulatable only;
real-gen confirm is new. No ADSR reward/Pareto number exists yet.

**Owner:** implementer.

### E7 — Lyric-focused deferred evaluation [REUSES offline + small confirm]

**Pre-condition:** E6 offline result available; lyric-bearing vocal subset
fixed (EN-core n=282 + stress arm).

**Workload:** on the **lyric-bearing vocal subset only**, compare
aesthetic-only restart / common-score restart / **axis-deferred restart
(ADSR)** / Full BoN / BoN-k. **Never mix instrumental prompts into headline
lyric metrics.**

**Metrics:** lyric intelligibility (Whisper/ASR-based, EN-vocal n=282),
**lyric-decidability onset vs ASR-transcribability onset (mechanistic
anchor)**, semantic prompt fit, overall quality, false lyric-degradation
rate. Report per stratum (clean-English-core / broader-lyric-bearing-vocal /
multilingual-or-thin-lyric stress arm). The multilingual arm uses
language-matched ASR or is clearly scoped.

**Compute:** 0 GPU-h for the offline subset analysis (<1 CPU-h); folds into
the E6 ≤150 GPU-h real-gen confirm budget (same held-out subset where
lyric-bearing).

**Success:** ADSR improves lyric/semantic preservation over naive early
(aesthetic-only) restart while retaining most common-quality gains.

**Fail interpretation:** if the lyric subset is too noisy, lyric stays
first-class but the claim becomes "lyric observability is difficult and
needs better measurement"; do not force a headline lyric result (§9).

**Owner:** implementer.

### E8 — Human spot-check (method preference) [NEW-RUN listening]

**Pre-condition:** E6 produced ADSR outputs (offline-selected + the
real-gen confirm subset).

**Workload:** 32–64 blind A/B comparisons, same prompt:
- Full BoN-8 vs ADSR.
- BoN-4 vs ADSR.
- random restart vs ADSR.
- raw restart vs axis-deferred restart (isolates the axis-deferral).

5 raters per pair (anti-fatigue session design: ≤ 250 axis-judgments /
rater / session). Rubric (5+ axes): overall, musicality, prompt fit,
**vocal presence / type correctness**, lyric correctness/intelligibility,
vocal artifacts.

**Compute:** 0 GPU-h, ~10 listener-hours (32 × 5 × 5 ≈ 800 axis-judgments
/ 80 per session ≈ 10 hours; scale with pair count).

**Pass criterion:** mixed-effects analysis — ADSR preference > 0.50 vs
BoN-4 (CI excluding 0.50).

**Fail interpretation:** **human judgment overrides automatic reward** in
framing when they conflict; the automatic-pruning claim weakens to
"automatic-metric Pareto only" (§9).

**Owner:** human eval coordinator.

### E9 — Robustness + cross-backbone (PARALLEL; does NOT gate submission) [NEW-RUN]

**Pre-condition:** none beyond E1; cross-backbone engineering started in
Phase 1 as a long-lead item.

**Workload:**
- **Required (cheap) cross-regime within ACE-Step** [REUSES]: vocal vs
  instrumental, lyric-bearing vs non-lyric, genre/style buckets, BoN-8 vs
  BoN-16 (optional subset), easy vs hard prompts.
- **High-priority, Phase-1-parallel-started cross-backbone** [NEW-RUN]:
  replicate **E1 + E3 + E6** on a second flow-matching audio/music backbone
  (e.g., **Stable Audio Open**), elevating the finding from an ACE-Step fact
  to a flow-matching principle.

**Graceful fallback:** if the second backbone is not ready in time, fall
back to cross-regime + an honest target-regime limitation. Cross-backbone
is **pursued in parallel from the start and simply does not gate
submission** — it is NOT a Phase-5 afterthought, and its absence does not
block the paper.

**Compute:** cross-regime 0 GPU-h (cached); cross-backbone GPU is a
separate parallel budget (backbone integration + re-running E1/E3/E6 on
SAO), tracked independently and not on the submission critical path.

**Evidence status:** cross-backbone **not started.** SAO is appendix-only
unless the parallel track delivers.

**Owner:** implementer + (cross-backbone) backbone-integration owner.

---

## 2. Run-order constraints

```
                 ┌─────────────── E9 (cross-regime + cross-backbone; PARALLEL, started Phase 1, no gate)
                 │
E1 ──┬── E2 ──┬── E3 (EVPD) ──┬── E6 (ADSR: offline → real-gen confirm) ──┬── E7 (lyric deferred)
     │        │               │                                          └── E8 (human spot-check)
     │        └── E4 (raw ETP baselines) ── E5 (quality verifier) ────────┘
     │
     └──────────────────────────────────────  (Track B globalness mechanism panel; parallel, no dependency)
```

- **E1 → E3 → E6** is the load-bearing dependency chain (observability →
  EVPD → ADSR). E4 (baselines) + E5 (verifier) feed E6 in parallel.
- E2 (human early→final) gates the restart license but reuses existing
  listening; its targeted check runs early.
- E7 and E8 follow E6. E9 runs in parallel from Phase 1 and never gates.
- The Track B globalness mechanism panel (median 0.861, sign consistency
  1.000, crossing frequency 0.000) is parallel and explains why early
  signal is global.

---

## 3. Compute budget (ADSR program forward cost; matched-expected-NFE)

| Workload | GPU-h | CPU-h | Listener-h | Reuse |
|---|---:|---:|---:|---|
| Vocal-presence relabel (§0.5.6) of 4096 candidates | ≤10 | <1 | 0 | NEW |
| EVPD mel-cache build (§0.5.2b) | ≤10 | <1 | 0 | NEW |
| E1 axis×σ observability matrix | 0 | <1 | 0 | REUSES |
| E2 human early→final validation (targeted listening) | 0 | 0 | ~3–5 | REUSES |
| E3 EVPD training + type-error study | ≤30 | <1 | 0 | NEW |
| E4 raw ETP + same-compute baselines | 0 | ≤2 | 0 | REUSES |
| E5 learned quality verifier + calibration | 0 | ≤2 | 0 | REUSES |
| E6 ADSR offline simulation | 0 | ≤2 | 0 | REUSES |
| E6/E7 small real-generation confirm (≤64 prompts) | ≤150 | <1 | 0 | NEW |
| E7 lyric-focused deferred eval (offline) | 0 | <1 | 0 | REUSES |
| E8 human spot-check | 0 | 0 | ~10 | NEW |
| E9 cross-regime within ACE-Step | 0 | ≤1 | 0 | REUSES |
| Boundary RL (cited only; no new compute) | 0 | 0 | 0 | REUSES |
| **Submission-critical subtotal (no cross-backbone)** | **≤210** | **≤12** | **~15** | |
| E9 cross-backbone (SAO; parallel, off critical path) | separate parallel budget | — | — | NEW |
| Optional BoN-16 upper-bound subset (≤64 prompts) | ≤80 | 0 | 0 | conditional |

The submission-critical ADSR program is **≤ ~210 GPU-h** (dominated by the
EVPD training + the small real-gen confirm); the offline-first core is
~0 GPU-h. The remaining ~5,400 − 210 ≈ 5,190 GPU-h budget is essentially
untouched by the critical path; the cross-backbone replication draws from a
separate parallel allocation and does not gate submission.

---

## 4. Required artifacts (output)

Per `/experiment-bridge` Phase 1 contract, each experiment must produce:

| Experiment | Required outputs |
|---|---|
| Relabel | `runs/adsr_vocalpresence_relabel_<YYYYMMDD>/{labels.jsonl, threshold_calibration.json, audit_set_handlabels.csv}` + RUN_LEDGER row. |
| E1 | `runs/adsr_e1_observability_<YYYYMMDD>/AXIS_OBSERVABILITY_MATRIX.{md,csv}`, per-axis-σ Spearman/retention CSV, heatmap (PNG/PDF), Markdown summary. |
| E2 | `runs/adsr_e2_human_early_final/{early_quality_report.md, vocal_presence_listening.json}`. |
| E3 | `runs/adsr_e3_evpd/{evpd_model.pt, auc_by_sigma.csv, onset_sigma.json, type_error_prevalence.csv, lyric_zero_cause_split.csv, offline_typematch_closedloop.json, offthe_shelf_baseline.json}`. |
| E4 | `runs/adsr_e4_baselines/{pareto.csv, winner_match.csv, false_negative.csv, regret_distribution.json}` (reproduces Track A: Schedule-A 0.9864@0.500, bottom-prune σ0.7 FN 0.0195, raw-ETP-over-BoN-4 ≈ 0.0036). |
| E5 | `runs/adsr_e5_quality_verifier/{linear,gbdt,lambdamart}_results.json`, safe-restart + late-axis-risk calibration JSON, model artifacts (`model.joblib`). |
| E6 | `runs/adsr_e6_main/{offline_sim.json, realgen_confirm.json, pareto_matched_nfe.csv, typematch_rate.csv, false_restart.csv, ablation_twofactor.csv, ablation_evpd_branch.csv}`. |
| E7 | `runs/adsr_e7_lyric_deferred/{lyric_intelligibility_by_stratum.csv, decidability_vs_transcribability_onset.json}` (EN-vocal n=282 headline; stress arm separate). |
| E8 | `runs/adsr_e8_human/pair_responses.json`, mixed-effects analysis report. |
| E9 | `runs/adsr_e9_robustness/{cross_regime.csv}` + (parallel) `runs/adsr_e9_cross_backbone_sao/{e1,e3,e6}_replication.json` if delivered. |
| All experiments | append a row in `orbit-research/RUN_LEDGER.jsonl` per run; consolidate final results in `runs/adsr_program_final_summary_<YYYYMMDD>.md`. |

---

## 5. PLAN_CODE_AUDIT verification (after `/experiment-bridge` Phase 1)

The checklist in METHOD_SPEC ADSR §4 / §12.9 must pass before any model
fit (EVPD or quality verifier) or any real-gen confirm consumes compute.
Critical items:

- (1) The scalar quality verifier reads ONLY from cached Track A records
  + the derived scalar features (§0.5.2a).
- (2) EVPD reads ONLY the **early Tweedie-clean mel** (§0.5.2b), NEVER the
  final audio.
- (3) NO leakage of `r_final`, `final_vocal_presence`, `type_match`, or
  `final_rank` into any training feature.
- (4) ADSR compute is accounted at **matched expected total NFE** with the
  §0.7 / §4.5 four-term rule (no optimistic accounting).
- (10) The offline-first core (E1/E4/E5/E6-offline/E7-offline) is `0 GPU-h`;
  EVPD training + real-gen confirm are the only authorized GPU items and
  stay within the §3 budget.

`PARTIAL_MISMATCH` is acceptable on items 5 (calibration disjointness), 6
(no GPU re-decoding beyond the mel-cache build) if the deviation is scoped
and justified. `CRITICAL_MISMATCH` if items 2, 3, or 4 deviate.

### 5.1 Claude Code audit — feature / label leakage (scalar + EVPD)

Run before any model fit. The audit must verify, by reading the extraction
code:

1. The scalar feature matrix contains ONLY the columns listed in §0.5.2a.
   No column is derived from `r_final`, `final_rank`, `is_winner`,
   `final_vocal_presence`, or `type_match`.
2. `prompt_type` is taken from prompt metadata (the **requested** type),
   NOT from any post-hoc classification of generated audio.
3. **EVPD inputs are the early Tweedie-clean mel (§0.5.2b) at σ ∈
   {0.9, 0.8, 0.7} only.** No final-audio mel, no final-derived feature,
   enters EVPD's input. The `final_vocal_presence` label is the target
   only, never an input.
4. The ablation aux features (`aux_pq_sigma7`, `aux_clap_sigma7`,
   `aux_mert_sigma7`, `uncertainty_sigma7`) are computed on the σ=0.7
   Tweedie reconstruction — NOT on the final audio.
5. The train/val/test split is applied at the PROMPT level (`prompt_id`,
   never `candidate_id`) before any feature/mel is computed; no candidate's
   features depend on another candidate's `r_final` or label.
6. Within-prompt rank features (`rank_sigma9/8/7`) are computed only from
   the same-σ scores of candidates within the same prompt — never from
   cross-σ or final scores.
7. The 5-fold EVPD / threshold calibration uses non-overlapping prompt
   folds drawn from train + val only; test prompts never appear in any
   calibration.
8. The lyric subset used for any lyric metric is **EN-vocal only (n=282)**;
   the instrumental `1.0` sentinel is excluded by construction (verify the
   filter).

Output: `runs/adsr_audit_leakage_<YYYYMMDD>/leakage_audit_report.md` with
PASS / FAIL per check. Any FAIL → STOP the corresponding model fit.

### 5.2 Claude Code audit — matched-expected-NFE fairness

Run before E6 reporting. The audit must verify:

1. The expected compute for each method (BoN-k, random restart, raw
   restart, learned-verifier restart, type-match restart, ADSR) is computed
   with the SAME four-term matched-NFE rule (§0.7 / §4.5):
   `partial-to-σ_c (restarted) + full (continued) + deferred-continuation +
   restart new-seed cost`. No method gets credit for cached scoring "for
   free"; **restart new-seed cost is charged, not waived.**
2. The EVPD inference cost and the quality-verifier inference cost are
   reported separately and included in the accounting; the headline
   `expected_compute_fraction` is the BoN denoising cost (EVPD/verifier
   inference is < 0.1 % of one full denoise; reported as an overhead line,
   excluded from the headline fraction). This decision is PRE-REGISTERED.
3. The BoN-4 control uses random keep-4 from the SAME 8 candidates the
   other methods see — NOT a fresh BoN-4 sampling pass.
4. Random restart uses the same RNG seed scheme as raw restart (Track A
   canonical seed) to ensure no luck-of-the-restart confound.
5. All methods are evaluated on the IDENTICAL test prompts and candidates
   (no method-specific subsetting).
6. The offline-simulation "restart = next pool draw" proxy is validated
   against the real-generation confirm on the ≤64-prompt subset; the
   extrapolated-restart estimate and the real-restart result agree within a
   pre-registered tolerance, or the discrepancy is reported.
7. The Pareto x-axis (`expected_compute_fraction`) is consistent across
   methods to ≤ 0.001 absolute deviation.

Output: `runs/adsr_audit_fairness_<YYYYMMDD>/fairness_audit_report.md`. Any
failure → re-run E6 with corrected accounting.

### 5.3 Claude Code audit — EVPD onset / type-match calibration

Run after E3 training, before EVPD/type-match results appear in the paper.
The audit must verify:

1. The vocal-presence decidability onset σ is computed on the **test
   split**, with the AUC-cut threshold pre-registered (e.g. 0.85), never
   tuned post-hoc to make the onset look earlier.
2. The type-match decision threshold (EVPD-predicted-presence cut and the
   "high confidence" margin in the §4.4 priority-1 branch) is calibrated on
   train + val 5-fold, NEVER on test.
3. The off-the-shelf vocal-detector baseline is applied to the IDENTICAL
   early mel inputs, so the EVPD-vs-off-the-shelf gap measures the
   early-σ-domain learning benefit, not an input mismatch.
4. The `lyric_zero_cause` split (type_error vs content_failure) is derived
   from `final_vocal_presence` + ASR, not from EVPD's own prediction
   (no circular use of the detector to validate the detector).
5. The false-restart-on-type rate is reported on the test split, so the
   type-match branch's cost (restarting a correct-type candidate) is
   visible alongside its benefit.

Output: `runs/adsr_audit_evpd_<YYYYMMDD>/evpd_audit_report.md`. Any failure
→ EVPD/type-match results are reported as DIAGNOSTIC only (not a paper
claim) until corrected.

### 5.4 Claude Code audit — quality-verifier risk calibration

Run after E5 calibration, before any safe-restart / late-axis-risk
threshold drives ADSR decisions in the paper. The audit must verify:

1. Safe-restart and late-axis-risk thresholds are computed on the
   calibration split (train + val 5-fold), NEVER on the held-out test
   split.
2. The empirical false-restart-rate of the final top-1 on the test split is
   reported per threshold (the verifier should not restart eventual
   winners more often than its calibrated target + small finite-sample
   slack).
3. Cross-fold variance of each threshold is reported; excess variance
   (CV > 0.20) triggers a flag (the verifier's confidence is unstable).
4. The verifier's restart/defer signals feed only the §4.4 priority-2/3
   branches; the priority-1 type-match branch is owned by EVPD (no
   double-counting of the same signal).

Output: `runs/adsr_audit_verifier_<YYYYMMDD>/verifier_audit_report.md`. Any
failure → verifier-driven ADSR decisions are reported as DIAGNOSTIC until
corrected.

---

## 6. Boundary RL section (cited only)

The paper's boundary RL paragraph (C6) cites:

- `orbit-research/PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md` for the
  COMMON_DEV_NO_CLEAR_WIN verdict.
- `orbit-research/PHASE_C1_TRAINING_DYNAMICS_AUDIT_2026-05-26.md` for the
  training health (adapter updates, KL, ratio).
- `orbit-research/C1_LITE_RL_RESCUE_STOP_DECISION.md` for the explicit stop
  decision.
- `orbit-research/archive/2026-05-doc-hygiene-post-c1/root-md/PHASE_C1_LEARNING_SIGNAL_AUDIT_2026-05-26.md`
  for the engineering-pass / scientific-weak verdict.

Framing: LoRA/GRPO post-training is technically feasible but shows no clear
first-wave common-metric gain, supporting the shift to inference-time
compute **reallocation** (ADSR). **Do NOT claim "RL post-training does not
work"** (§11 anti-overclaim) — only the boundary first-wave result. No new
RL training is scheduled by this plan; new σ-axis RL is future work, not in
the main execution plan.

---

## 7. Baselines (run order reference; full spec in CONTROL_DESIGN)

**Required:** Full BoN-8, BoN-4, random prune/restart, **raw ETP**
(baseline, was the ETV headline), **learned-verifier selection**,
**type-match restart**, **ADSR** (headline).
**Optional:** BoN-16, non-Tweedie early audio proxy, late-only selection,
oracle final selector, **off-the-shelf (non-early-trained) vocal detector
as a baseline for EVPD**.
**Boundary (not main comparison):** M-FixedWin-PRM, M-Section-PRM,
R8a/R8b.

Full control matrix (random restart / raw restart / axis-deferred / EVPD
vs off-the-shelf / two-factor axis-awareness × restart-reallocation /
EVPD-branch on-off): see `orbit-research/CONTROL_DESIGN.md` "2026-06-04
ADSR Pivot Addendum".

---

## 8. Execution staging — Phases 1–7 (ADSR §11) and STOP-B-1 gates

ADSR §11 staging (ample compute → parallel):

- **Phase 1 — Repair lyric measurement, build observability, derive
  vocal-presence labels.** Fix lyric aggregation/sentinel (retained: EN-vocal
  n=282, 0.682); evaluate the lyric-bearing subset; derive
  `final_vocal_presence` (§0.5.6); build the EVPD mel-cache; produce the
  axis×σ heatmap (E1). **Start the second-backbone engineering integration in
  parallel (long-lead).** **Gate:** can lyric be a late-observable headline
  axis, and is vocal-presence-onset ≪ lyric-onset?
- **Phase 2 — Human early→final validation (E2),** including the early
  vocal-presence listening check. **Gate:** do humans support early
  decidability (quality and presence)?
- **Phase 3 — Train EVPD + type-error study (E3) and ADSR offline
  simulation (E6 offline).** **Gate (make-or-break):** is vocal presence
  early-decidable, and does ADSR (with type-match) beat BoN-k/random under
  fair matched-NFE compute?
- **Phase 4 — Learned quality verifier + risk calibration (E5);** raw-ETP
  baselines (E4). **Gate:** does the verifier improve decision quality
  (safe-restart / defer)?
- **Phase 5 — Real-generation ADSR confirm (E6 real-gen) + lyric-focused
  deferred eval (E7).** **Gate:** does true restart match the offline
  proxy, and does ADSR preserve lyric/semantics on the EN-vocal subset?
- **Phase 6 — Human spot-check (E8) + robustness + cross-backbone (E9).**
  **Gate:** does human judgment support ADSR? Can we claim more than one
  narrow setting? (cross-backbone does NOT gate submission).
- **Phase 7 — Paper assembly.** Proposal, figures, method, limitations,
  reviewer-risk response.

**STOP-B-1 (PI sign-off gates) for `/experiment-bridge`:**

- [ ] PI approves FINAL_PROPOSAL v4.0 (ADSR).
- [ ] PI approves METHOD_SPEC ADSR implementation contract (restart/defer/
  continue logic, EVPD, quality verifier, matched-NFE accounting,
  offline-first protocol).
- [ ] PI approves EXPERIMENT_PLAN_EXEC v4.0 (this file).
- [ ] PI confirms reuse of Track A 205/51/256 prompt-level split for the
  verifier + EVPD train/val/test (no resampling).
- [ ] PI authorizes deriving the new `final_vocal_presence` label and
  training the EVPD audio model (the only new learned-model GPU item;
  ≤ ~30 GPU-h).
- [ ] PI authorizes the ≤ ~150 GPU-h small real-generation ADSR confirm
  (≤64 stratified held-out prompts).
- [ ] PI authorizes E2 + E8 human eval (targeted early-presence listening +
  32-pair method spot-check; expand to 64 conditional).
- [ ] PI confirms the boundary RL section (C6) uses only cached evidence
  and does NOT claim "RL does not work".
- [ ] PI confirms cross-backbone (E9) is parallel and does NOT gate
  submission.
- [ ] PI confirms no large-model training beyond the small EVPD audio model
  (the scalar quality verifier stays linear / GBDT / LambdaMART — no MLP;
  EVPD is the only learned neural component).

---

## 9. Failure modes and interpretation (per NULL_RESULT_CONTRACT "2026-06-04 ADSR Pivot Addendum")

- **ADSR does not beat BoN-4** → too weak as a main ICLR claim; fall back to
  an **axis-observability + trajectory-analysis paper** (C1 + E1 + E2 +
  Track B globalness), or a workshop/audio venue.
- **ADSR improves common quality but hurts lyric** → axis-deferred logic
  insufficient; strengthen lyric defer / use later σ for lyric / restrict to
  non-lyric settings.
- **Vocal presence is NOT early-decidable (EVPD onset is late)** → demote
  the type-match branch to a later-σ check; report onset honestly. Even a
  mid-trajectory onset saves the back half of compute, so value likely
  persists; the claim must follow the measured onset.
- **Lyric subset too noisy** → lyric stays first-class but the claim becomes
  "lyric observability is difficult and needs better measurement"; do not
  force a headline lyric result.
- **Offline-proxy ≠ real restart** → report the discrepancy; the offline
  Pareto becomes an estimate and the real-gen confirm becomes the headline
  on its (smaller) subset.
- **Second backbone fails** → submit with a target-regime limitation if
  ACE-Step results are strong (E9 does not gate).
- **Human spot-check disagrees with reward metrics** → weaken the
  automatic-pruning claim; **human result overrides.**

---

## 10. Cross-references

- `ADSR_Research_Plan_FINAL_EN_2026-05-29.md` — PI frozen FINAL plan
  (authoritative; this exec plan implements its §6 / §11).
- `refine-logs/FINAL_PROPOSAL.md` v4.0 (ADSR).
- `refine-logs/FINAL_PROPOSAL_SHORT.md` v4.0 (ADSR short).
- `refine-logs/METHOD_SPEC.md` — ADSR implementation contract.
- `orbit-research/CONTROL_DESIGN.md` "2026-06-04 ADSR Pivot Addendum" —
  baselines/controls (type-match restart, random/raw/axis-deferred,
  EVPD-vs-off-the-shelf, two-factor ablation, EVPD-branch on/off).
- `orbit-research/ASSUMPTION_LEDGER.md` "2026-06-04 ADSR Pivot Addendum" —
  H1–H6 + C1–C6 paper-bearing rows.
- `orbit-research/NULL_RESULT_CONTRACT.md` "2026-06-04 ADSR Pivot Addendum"
  — failure routing (§9).
- `orbit-research/trajectory_candidate_dataset.jsonl` — canonical merged
  reward set (4096 candidates; promoted 2026-06-04).
- `orbit-research/prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md` —
  lyric-fix R2 (EN-vocal n=282, 0.682, sentinel masking).
- `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md` — Track A canonical
  (raw ETP baseline; Schedule-A 0.9864@0.500).
- `orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md` — Track B globalness
  mechanism (0.861).
- `orbit-research/PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md` — C6 boundary RL.
- `PROGRESS_REPORT_2026-05-28.md` — full project snapshot.

---

## 11. ICLR reviewer-risk audit

Likely reviewer concerns for an ICLR submission, each mapped to the
experiment / control / artifact that addresses it. Non-load-bearing for the
science but required before submission. PI memory: do not double project
complexity to pre-empt hypothetical attacks — only the concerns below have
been judged plausible-and-addressable; speculative reviewer attacks stay
speculative and are NOT defended for here.

| Reviewer concern | Plausibility | Where addressed |
|---|---|---|
| "Restart accounting is optimistic — you're not charging for new seeds." | high | §0.7 + §4.5 four-term matched-NFE rule; §5.2 fairness audit charges restart new-seed cost; offline proxy validated by the real-gen confirm. |
| "ADSR is just BoN with a fancier name." | high | §E6 two-factor ablation (axis-awareness × restart-reallocation) + with/without EVPD branch; raw ETP baseline (E4) shows selection is near-tied (delta ≈ 0.0036), so the leverage is reallocation, not selection. |
| "Offline pool-draw 'restart' is not real restart." | high | §0.7 small real-generation confirm (≤64 prompts, true new seeds); §5.2 item 6 validates the proxy against real restart. |
| "Vocal-presence detection is trivial / off-the-shelf solves it." | medium | §E3 (NOT yet run) will test an off-the-shelf baseline on the early mel — *if* the early-σ domain is OOD as hypothesized, the EVPD-vs-off-the-shelf gap quantifies it; §11 anti-overclaim "vocal presence not always trivially detectable at any σ". |
| "Gains are reward-circular (only on the training axis)." | high | §E1 cross-axis observability + §E3 closed loop on prompt-type-match (a non-reward axis) + §E7 lyric intelligibility (EN-vocal n=282, separate metric) + §E8 human override. |
| "Improvements on automatic metrics don't reflect perceptual quality." | high | §E2 human early→final validation + §E8 human spot-check (32–64 pairs × 5 raters); human overrides reward. |
| "How do you know early-σ signal isn't just a proxy for late-σ?" | high | §E1 per-σ Spearman + retention; §E3 onset σ; Track B globalness (between-share, sign consistency 1.000, crossing freq 0.000). |
| "Lyric metric is contaminated by instrumental prompts." | high | §0.5 / §0.6 / §E7 lyric is EN-vocal only (n=282); instrumental `1.0` sentinel excluded by construction; per-stratum reporting; §5.1 item 8 audits the filter. |
| "Are train/val/test splits clean / is this cross-content?" | high | §0.6 prompt-level 3-way split (`prompt_id` not `candidate_id`); explicitly **cross-prompt, not cross-content** (81–94 % shared vocabulary); per-specificity-stratum reporting; §5.1 leakage audit. |
| "EVPD label could leak into its own features." | high | §5.1 item 3 + §5.3 item 4 — EVPD inputs are the early Tweedie mel only; `final_vocal_presence` is target-only; `lyric_zero_cause` split derived from labels + ASR, not from EVPD. |
| "Why a learned audio model for EVPD but only GBDT for quality?" | medium | §E5 framing — scalar ranking is near-saturated (ridge NDCG ~0.995), capacity is not the bottleneck; §E3 — early-σ audio perception under heavy noise IS a genuine learning problem and OOD for off-the-shelf detectors. The size difference is principled, not arbitrary. |
| "ADSR could overfit to specific genres or prompt types." | medium | §E9 cross-regime (vocal/instrumental, genre, length, easy/hard); §E6 false-restart stratification. |
| "Why is M-PRM RL still mentioned at all?" | medium | §6 boundary section, cached evidence only, single paragraph, no new compute; §11 anti-overclaim does NOT claim "RL does not work". |
| "Where is the held-out re-validation against data snooping?" | medium | §0.6 the 256-prompt test split is touched once; §3 optional re-validation pass on a fresh BoN held-out set if reviewer pressure. |
| "Why is the finding only on ACE-Step short-form?" | medium | §E9 cross-backbone (Stable Audio Open, parallel, graceful fallback, does NOT gate); FINAL_PROPOSAL §1 scopes the claim; §11 anti-overclaim "does not universally generalize to all flow models". |

Concerns explicitly NOT defended for (per PI anti-paranoia policy):
- "Are reward models well-calibrated for music?" — out of scope; cited only
  as a limitation in FINAL_PROPOSAL.
- "Why not train on a larger BoN set?" — bounded by Track A compute cap;
  the claim is scoped to the BoN-8 setting and made explicit.
- "Could a long-form generation regime behave differently?" — out of scope
  per the song-length policy (30–60 s pilots; ≤ 120 s if stable; not
  4-minute).

---

## 12. Version history

- **v4.0 — ADSR reframe (2026-06-04): ETV→ADSR pivot per
  `ADSR_Research_Plan_FINAL_EN_2026-05-29.md`.** Reframed the method from
  ETV fixed-pool pruning/selection to **ADSR — axis-deferred speculative
  restart** (RESTART / DEFER / CONTINUE compute reallocation). Changes:
  (a) expanded the six ETV experiments to **nine ADSR experiments E1–E9**
  (E1 axis×σ observability; E2 human early→final; E3 EVPD + type-error
  study [NEW learned audio model]; E4 raw ETP + same-compute baselines
  [former headline → baseline]; E5 learned quality verifier; E6 ADSR main
  method [offline-first + real-gen confirm]; E7 lyric-focused deferred eval
  [EN-vocal n=282]; E8 human spot-check; E9 robustness + cross-backbone
  [parallel, no gate]); (b) added §0.7 offline-first ADSR protocol with the
  matched-expected-NFE four-term accounting; (c) added §0.5.6
  vocal-presence label derivation and the `final_vocal_presence` /
  `type_match` / `lyric_zero_cause` labels (H2b presence-vs-content split);
  (d) added the EVPD mel-cache and EVPD audio-model training; (e) restaged
  to ADSR §11 **Phases 1–7** with make-or-break Phase-3 gate; (f) extended
  the Claude Code audits (§5.1 EVPD-leakage, §5.2 matched-NFE fairness +
  offline-proxy validation, §5.3 EVPD onset/type-match calibration, §5.4
  verifier risk calibration); (g) retained the R2 lyric-fix corrections
  (EN-vocal n=282, **0.682**, cross-prompt-not-cross-content,
  per-specificity-stratum) and updated Track A to **0.9864@0.500**
  (regenerated 2026-06-04 on the lyric-fix dataset; was 0.9858);
  (h) updated §11 reviewer-risk audit for restart-accounting / offline-proxy
  / EVPD-label-leakage. **Evidence honesty stamp:** this is a **plan-stage
  proposal for the ADSR method** — foundation evidence exists (H1/H2
  persistence; Track A raw-ETP 0.9864@0.500; lyric 0.682 EN-vocal n=282;
  Track B globalness 0.861; C1 RL boundary; human listening), but EVPD is
  NOT trained, ADSR/restart is NOT run, and vocal-presence labels are NOT
  yet derived. The pre-ADSR (ETV) v3.0.1 file is archived at
  `orbit-research/archive/etv_pre_adsr_20260604/refine-logs_EXPERIMENT_PLAN_EXEC.md`.
- **v3.0.1 — frozen-PI-plan consistency patch** — 2026-05-28 (ETV era).
  Added §0.5 candidate-level dataset construction; §0.6 prompt-level
  train/val/test 3-way split; §1 E2 step 4 BoN-16 optional subset; expanded
  §5 PLAN_CODE_AUDIT with §5.1 leakage / §5.2 same-compute fairness / §5.3
  risk-control calibration; added §11 ICLR reviewer-risk audit. Additive
  patch only.
- **v3.0** — 2026-05-28 (ETV era). Total rewrite around the ETV pivot. The
  pre-revise v2.2 file is preserved at
  `orbit-research/archive/2026-05-28-proposal-revise-round-1/EXPERIMENT_PLAN_EXEC.md`.
  Trigger: PI-authored `/HOME/.../revise.md` invocation of
  `/proposal-revise both`.
- **v2.x** — 2026-05-15 through 2026-05-24 (M-PRM era). M-PRM ladder
  structure (Phase A → C1 → Phase D). See snapshot for full content.
