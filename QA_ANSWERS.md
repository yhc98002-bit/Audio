# Answers to QA.md (collaborator questionnaire)

**Date:** 2026-06-10 · All paths relative to the repo root
(`/HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion`, physically
`/XYFS02/HDD_POOL/...`). Every numeric claim cites its source artifact.

---

## A. Data access and schema

### Q1 — Per-candidate table

**No single file carries every column you list; three files join on
`(prompt_id, candidate_index)`.** The first two have 4,096 keys each (verified 0 mismatch);
the EVPD file is a 2,048-key **held_out subset** of those keys (see caveat below):

| Columns | File |
|---|---|
| prompt_id, candidate_index, `candidate_seed`, `candidate_uid`, requested type (`vocal_stratum`), `language`, `split` (dev/held_out), **final scores on all axes** (`final_common_robust_lcb`, `final_aesthetic_{pq,ce,cu,pc}`, `final_semantic_fit`, `final_lyric_intelligibility`, `final_section_coherence`, 4 probes), early σ0.9/0.8/0.7 scores, BoN labels (`label_final_winner/top2/top4`) | `orbit-research/trajectory_candidate_dataset.jsonl` (4,096 rows — the canonical spine; your guess was right) |
| **Raw continuous Demucs `vocal_energy_ratio`**, `input_rms`, `near_silent`, per-stem energy fractions (drums/bass/other/vocals), early-mel `.npy` paths | `orbit-research/adsr_phase2_20260604/vocal_presence_raw.jsonl` (4,096 rows, all `ok=true`) |
| **EVPD score at σ0.8** (`evpd_p`, `evpd_thr=0.728`, `evpd_pred_present`, model `melsumm_logit_s0.8`) | `orbit-research/adsr_phase2_20260604/batch2/evpd_test_pred_s0.8.jsonl` — **held_out only (2,048 rows), out-of-fold** |

Two caveats:
- **EVPD scores exist out-of-fold only for held_out.** The model was trained on dev, so dev
  candidates have no honest predictions on file. In-fold dev scores can be generated in one line
  from the persisted model (`batch2/evpd_sigma08_online.joblib`) + the feature cache
  (`batch2/evpd_feature_cache.npz`), but they must be flagged as in-fold.
- The canonical spine carries early scores at σ0.9/0.8/0.7 only. The **five-σ** early scores
  (incl. 0.5/0.3) live in `runs/adsr_recollect_20260604_full01_merged/shard0*/candidate_records.jsonl`
  (same join key).

**The aggregate you asked for first — per-prompt violation-count histogram**
(violation = `(ratio ≥ 0.1791 ∧ ¬near_silent) XOR (vocal_stratum=='vocal')`; computed
2026-06-10, totals reconcile with the published 942 violating candidates / 0.6367
prompt-affected rate):

| violations per prompt | vocal prompts | instrumental prompts | total |
|---|---|---|---|
| 0/8 | 115 | 71 | 186 |
| 1/8 | 69 | 43 | 112 |
| 2/8 | 44 | 18 | 62 |
| 3/8 | 31 | 14 | 45 |
| 4/8 | 21 | 11 | 32 |
| 5/8 | 24 | 10 | 34 |
| 6/8 | 7 | 15 | 22 |
| 7/8 | 3 | 8 | 11 |
| 8/8 | 2 | 6 | 8 |
| **prompts** | **316** | **196** | **512** |

### Q2 — Early-scored axes; early Whisper transcripts?

**All reward axes were scored on the early-Tweedie decodes at every σ ∈ {0.9, 0.8, 0.7, 0.5,
0.3}** in the Track-B merged records: aesthetic ce/cu/pc/pq, `semantic_fit`,
`section_coherence`, **`lyric_intelligibility`**, the four probes
(silence_fraction / autocorr_repetition / hf_artifact_score / off_prompt_distance), and the
common aggregate (`common_robust_lcb` + mean/std/probe-penalty components), plus per-axis
robust values. (The canonical dataset carries the σ≥0.7 subset of these.)

**Transcripts: only the derived score is persisted, not the text.** `lyric_intelligibility =
max(0, 1−WER)` is computed in `src/mprm/rewards/whisper_wer.py` (Whisper large-v3, EN); the
transcript string is held in-memory in `RewardScore.raw` (line 90) and never written to disk —
for early *or* final audio.

Consequences for your observability-curve figure:
- **Score-level curve: pure analysis, all five σ** (the merged records already have
  `early_{σ}_lyric_intelligibility` etc. at 0.5/0.3 too).
- **Transcript-level analysis: needs a (cheap) new Whisper pass**, and it is only possible for
  σ ∈ {0.9, 0.8, 0.7} — early WAVs were saved only for σ ≥ 0.7
  (`scripts/collect_early_tweedie_validation.py:369-377`); σ0.5/0.3 kept scores only to bound
  disk. 4,096 wavs per σ, ~15 MB each.

### Q3 — Raw Demucs ratios; ambiguous-band definition

**Yes** — continuous `vocal_energy_ratio` (5-decimal precision) is stored for all 4,096 in
`vocal_presence_raw.jsonl`, alongside `input_rms`, `near_silent`, and the full per-stem energy
breakdown (so you can re-derive ratios under other stem weightings).

Ambiguous band (verbatim from `orbit-research/adsr_phase2_20260604/VOCAL_TYPE_ERROR_PREVALENCE.json`):

```
|ratio − 0.1791| < 0.05  and  not near_silent   →  557 candidates (13.6%)
```

- Threshold **0.1791** = strata-median-midpoint: median ratio of vocal-requested candidates
  **0.3415** vs instrumental-requested **0.0166** (non-near-silent), midpoint of the two.
- `near_silent` ≜ `input_rms < 1e-3`; **0 candidates** are near-silent in the final data, so
  the `not near_silent` clause is currently vacuous (it matters only as a guard).
- For a threshold-sensitivity sweep you have everything: continuous ratios + the GMM
  bimodality fit (means ≈ 0.0003 / 0.3398, weights 0.84/0.16) in `VOCAL_LABEL_RELIABILITY.md`.
- The 150 nearest-threshold cases + Demucs/Whisper disagreements are pre-packaged in
  `vocal_ambiguous_check_packet.jsonl`.

---

## B. Compute accounting and policy definitions

### Q4 — Exact cost model behind "compute = 0.700"

Project-standard step model (`scripts/analyze_bon16_pruning_subset.py:21-23`, reused verbatim
by the Batch-2 sims): a full generation is **30 sampler steps**; the step index reached at each
decision σ is

```
f(σ):  σ0.9 → 7 steps   σ0.8 → 12 steps   σ0.7 → 16 steps   (FULL = 30)
```

For every σ-decision policy in the frontier the survivor count is **k = 4** (all 8 candidates
run to the decision σ, exactly 4 continue to step 30):

```
compute_fraction(σ, k=4) = (8·f(σ) + 4·(30 − f(σ))) / (8·30)
  σ0.9: (56+92)/240  = 0.6167
  σ0.8: (96+72)/240  = 0.7000
  σ0.7: (128+56)/240 = 0.7667
BoN-4 = 0.5, full BoN-8 = 1.0.
```

**Treated as free** in the offline accounting (documented limitation in
`ADSR_COMPUTE_ACCOUNTING.md`): the Tweedie decode at the decision point, EVPD inference, and
Demucs labeling. Context for how much that hides:
- Measured online (an17 A800, `scripts/online_adsr_smoke.py`): warm decode+mel+EVPD ≈ **0.3 s
  per decision**, vs ≈ 2.8 s for a full 30-step diffusion pass (~0.09 s/step). There is a
  one-off ~27 s torch compile on the first decode. So the decision overhead is real (~10% of
  one trajectory's diffusion) but small vs the full per-candidate pipeline (VAE decode + final
  scoring dominate wall-clock).
- EVPD itself is a logistic on 320-d features — microseconds; the overhead is the DCAE decode + mel.
- Demucs is the evaluation-side ground-truth labeler; it is never part of any policy's compute.
- Batch-3 is required to report **actual GPU-h** and expected-vs-actual compute fraction, with a
  >15% deviation flag.

### Q5 — Precise Batch-2 policy definitions; which split each number lives on

**"EVPD-aware selection" (`adsr_evpd_select`) is a hard veto with fallback — no soft penalty
anywhere.** Two stages (implementation: `scripts/batch2_stage4_adsr_sim.py`):

1. *Continued-set construction (the "restart" stage):* rank the 8 candidates by **early-σ**
   `common_robust_lcb`, but every EVPD-flagged type-mismatch (`evpd_pred_present ≠ requested`,
   hard threshold) is deprioritized below every non-flagged candidate; take the top 4.
2. *Output selection:* among the 4 continued, restrict to EVPD type-**matching** candidates and
   pick the best **final** `common_robust_lcb`; if all 4 are flagged, fall back to plain
   best-final-common.

**Thresholds — two models, don't conflate:** the Batch-2 *headline* (0.168→0.121) used the
deployed fused model `melsumm_gbdt_fused` (best-on-val, val AUC 0.9241) with its val-tuned
threshold **0.971**; the σ-frontier σ0.8 row and the persisted *online* model use the per-σ
`melsumm_logit_s0.8` with threshold **0.728** (balanced-accuracy max on val). Both are frozen
from Batch-2 val; neither was ever tuned on test.

**"Common-score restart"** = rank the 8 by **early-σ** `common_robust_lcb`, top-4 continue,
final output = best **final** common among the 4. It is identical to raw-ETP keep-4 and is what
"ADSR-noEVPD" denotes in the fixed-pool sim.

**Split locations — your guess is half right, corrected here:**
- `0.168 → 0.121` (σ0.7, fused model) — **held_out, n=256**, out-of-fold EVPD (trained on dev).
- The σ-frontier table (σ0.9/0.8/0.7 baselines 0.1562 / 0.1914 / 0.168) — **also held_out
  n=256** (not dev), per-σ models, out-of-fold (`ADSR_SIGMA_FRONTIER.json`).
- The **19.9%** survivor-top-1 figure is a *different quantity on a different set*: type-error
  among top-1-by-**final**-common, a label-only analysis over **all 512 prompts** (both splits;
  `scripts/batch2_stage1_typeerror.py` applies no split filter).
- Why the three "baselines" differ (0.1562 vs 0.1914 vs 0.168 vs 0.1992): the frontier rows rank
  by **early** common at different σ (different continued sets → different selected outputs),
  the 0.1992 ranks by **final** common, and the prompt sets differ (256 vs 512). They are not
  inconsistent — they are different selectors.

---

## C. Batch-3 protocol

*(You're right that the status doc deferred this; here is the full current state — what is
pre-registered/frozen vs honestly still open. Batch 3 has **not** launched generation yet.)*

### Q6 — Batch-3 design

**Frozen (pre-registered in the PI's Batch-3 spec + built artifacts):**
- **Arms (matched expected compute):** (1) BoN-4 same-compute baseline; (2) random restart;
  (3) common-score restart @σ0.8; (4) ADSR+EVPD @σ0.8; (5) ADSR+EVPD+lyric-defer (if the
  implementation is ready); (6) full BoN-8 reference; optional σ0.7 diagnostic arm if it doesn't
  delay the main run. ADSR-noEVPD is *not* re-run online (offline result stands).
- **Prompts:** 192, all held_out — strata A_type_risk 80 / C_lyric_bearing_EN_vocal 40 /
  B_balanced_vocal 24 / B_balanced_instrumental 24 / D_general_sanity 24
  (`orbit-research/adsr_phase2_20260604/batch3/BATCH3_PROMPT_STRATA.json` + `batch3_selected_prompts.jsonl`).
- **Primary decision σ = 0.8**; EVPD = the frozen σ0.8 model+threshold
  (`batch2/evpd_sigma08_online.joblib`, thr 0.728, held-out AUC 0.917) — **not retuned on
  Batch-3 outputs**.
- **Online protocol shape:** generate to σ0.8 → extract early features → EVPD → high-confidence
  type-mismatch ⇒ terminate + restart with a new seed (partial compute counted); lyric/semantic
  uncertainty ⇒ defer (never an early-restart reason); else continue; stop when the matched
  budget is consumed; final output by the declared selection policy. The restart *primitive* is
  already validated end-to-end (in-loop decode+EVPD at σ≈0.79, abort saves 53% of steps —
  `scripts/online_adsr_smoke.py` result).
- **Required accounting:** cost-to-σ0.8, #early terminations, #restarted seeds, #full
  completions, actual GPU-h, expected vs actual compute fraction, offline-predicted vs online
  cost, >15% deviation flag.

**Honestly not yet frozen** (the harness was in build when the batch was last paused; these get
fixed in the pre-launch protocol doc and pass a Codex pre-launch audit *before* any GPU run):
the per-prompt **max-restart cap**, the exact step-budget arithmetic (planned: a per-prompt
budget in step-units, e.g. 0.700 × 240 for the σ0.8 arms, debited 12 steps per σ0.8 probe and
30 per completion, restart while budget allows), the **pre-committed seed-list policy** (see
Q8), and the final-selection tie-breaking details. If you need these pinned before your
analysis design, say so — they are one document away, not one experiment away.

### Q7 — Sourcing of the 192; type-risk assignment; leakage

Built by `scripts/batch3_prompt_strata.py`:
- **Source:** all 192 from **held_out** (the canonical 256-prompt eval split). EVPD was trained
  on dev only ⇒ **no detector leakage** into stratification or evaluation.
- **Type-risk assignment:** a label heuristic, *not* a model — a prompt is type-risk iff
  **≥2 of its 8 Batch-1 candidates were ground-truth type errors** (final Demucs labels,
  threshold 0.1791). No predictor was fit; EVPD predictions were not used.
- **Leakage/validity caveats we'd flag ourselves:**
  1. Stratification conditions on *observed Batch-1 outcomes of the same prompts*. Batch-3
     generates fresh seeds, so expect regression-to-the-mean in per-stratum error rates; treat
     strata as fixed groups, don't expect the 23% prevalence to reproduce per group.
  2. The selection is deliberately **risk- and EN-vocal-enriched, not distribution-matched** to
     the 512: vocal 136 / instrumental 56 (vs 316/196 overall). `D_general_sanity` (n=24) is the
     unenriched read; headline claims will be reported per stratum, not pooled.
  3. Non-EN vocal prompts can land in A_type_risk (e.g. `held_out_0193`, zh). Lyric metrics stay
     scoped to EN-vocal regardless (128 of the 192 are EN-vocal, so the lyric-first analysis is
     well powered).

### Q8 — Common random numbers

**Feasible today, no code changes.** Generation is already fully seed-parameterized:
`seed_everything(seed)` + `model.sample(prompt, seed=…)` per candidate, with the deterministic
formula `seed = seed_base + manifest_index·1000 + cand_idx` (the resume machinery exercised
this at scale); upstream `ACEStepPipeline.__call__` accepts `manual_seeds`. So:
- all arms can share **identical pre-committed initial noises** per prompt-slot by using the
  same seed list across arms, and
- a **pre-committed restart-seed list** per prompt is a trivial second formula (planned for the
  Batch-3 harness).

One caveat from hard experience: same-seed determinism is solid **within a node/process**, but
bitwise reproducibility across heterogeneous nodes is *not* guaranteed (this is exactly why the
Track-B resume merge used original-wins dedup). For CRN-style variance reduction, schedule
paired arms of the same prompt on the same node.

---

## E. Model capabilities

### Q13 — Conditioning controls; can a respawn change conditioning?

**Prompt object** (`src/mprm/data/prompts.py`): `text` (tags/description), `lyrics`
(None ⇒ instrumental; routed upstream as a zero lyric-token placeholder), `structure_hint`,
`duration_target`, `metadata`, `strata`. There is **no explicit vocal/instrumental flag**
anywhere — lyric presence *is* the signal.

**Sampler knobs routable per-call today** via `extras` (whitelist
`UPSTREAM_PASSTHROUGH_KEYS`, `src/mprm/inference/ace_step.py:46-58`): `omega_scale`,
`guidance_interval`, `guidance_interval_decay`, `min_guidance_scale`, `scheduler_type`
(euler/heun/pingpong), `cfg_type` (apg/cfg/cfg_zero_star), `use_erg_tag/lyric/diffusion`, and —
relevant to your conditioned-respawn idea — **separate `guidance_scale_text` and
`guidance_scale_lyric`** (upstream activates dual-condition guidance when both > 1.0). Primary
`cfg_scale` and `steps` are explicit `sample()` kwargs.

**Not available:** negative prompts/tags — no upstream surface at all; the adapter hard-rejects
`negative_prompt_strength` (`UNSUPPORTED_EXTRAS_KEYS`, lines 68-74), as well as per-step SDE/eta
control. **Upstream-but-not-wired:** ACE-Step v1.5's pipeline does support `task ∈ {retake,
repaint, edit, extend, audio2audio}` with `retake_variance` and `src_audio_path`, but our
adapter (`sample()`) routes only `text2music`; exposing retake/repaint would be a small,
contained adapter extension.

**Respawn semantics:** the validated online-restart primitive treats every restart as a fresh
`model.sample(prompt, seed, extras)` call. Therefore **changing conditioning at respawn is
supported today with zero code changes** — a restart may change the seed *and/or* any Prompt
field (text, lyrics — e.g. inject an explicit instrumental/vocal cue) *and/or* any whitelisted
extra (e.g. raise `guidance_scale_lyric` after a vocal-presence miss). What it cannot do without
adapter work: retake/repaint-style partial-noise respawn from the aborted trajectory, or
negative-tag steering. (Note: Batch-3 as pre-registered uses **seed-only** restarts; conditioned
respawn would be a protocol change needing PI sign-off.)

---

*Prepared 2026-06-10. Sources verified against the artifacts cited inline; the Q1 histogram was
recomputed from raw files and reconciles with published aggregates (942 violating candidates;
prompt-affected 0.6367).*
