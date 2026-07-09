## 2026-06-04 ADSR Pivot Addendum (Round 3) — ADSR algorithmic formalization

> **Status / supersession.** This addendum **SUPERSEDES** the
> "2026-05-28 ETV Pivot Addendum (Round 3) — Early Trajectory Verifier
> formalization" above for the *active, paper-bearing* algorithmic shape. The
> ETV addendum is **retained as historical / boundary reference** (do not
> delete): the project pivoted ETV → **ADSR (Axis-Deferred Speculative Restart)**
> on 2026-06-04 per the PI-frozen `ADSR_Research_Plan_FINAL_EN_2026-05-29.md` and
> the reframe anchor `refine-logs/ADSR_REFRAME_BRIEF.md`. The full ADSR mechanics
> live in the **v4.0 canonical stack** — this file gives only the
> *pseudocode-level deltas* for ADSR's three new algorithmic objects and points
> back to the contract; it is **not** a re-derivation.
>
> **Where the authoritative ADSR contract lives** (do not duplicate here):
> - `refine-logs/METHOD_SPEC.md` **§13** (RESTART/DEFER/CONTINUE logic),
>   **§14** (two learned components: §14.1 quality verifier, §14.2 EVPD),
>   **§15** (baselines), **§16** (compute accounting §16.3, offline-first §16.4,
>   thresholds §16.2, PLAN_CODE_AUDIT §16.6).
> - `refine-logs/FINAL_PROPOSAL.md` v4.0 (claim chain C1–C6, method §4).
> - `refine-logs/EXPERIMENT_PLAN_EXEC.md` v4.0 (E1–E9, Phases 1–7).
> - `orbit-research/CONTROL_DESIGN.md` "2026-06-04 ADSR Pivot Addendum" (baselines,
>   two-factor ablation axis-awareness × restart-reallocation, EVPD-branch on/off).
> - `orbit-research/ASSUMPTION_LEDGER.md` "2026-06-04 ADSR Pivot Addendum"
>   (hypotheses H1–H6, claims C1–C6).
> - The verbatim ETV §12 / M-PRM stack: ETV archive
>   `orbit-research/archive/etv_pre_adsr_20260604/`.

### What survives, what is demoted, what is new (algorithmic mapping)

| ETV-era object (above) | ADSR status | New shape |
|---|---|---|
| `V_σ(c, i)` learned verifier — tiers **E-R7** (linear/logistic), **E-R8** (GBDT pairwise PRIMARY), **E-R9** (LambdaMART listwise) | **SURVIVES** as ADSR's *lightweight quality verifier* (METHOD_SPEC §14.1). Re-labelled **Q-R7 / Q-R8 / Q-R9**. Features, no-large-model bound, and Track-A-cached-features / no-GPU-forward-pass property all carry over. | §A below (unchanged signature; new targets `safe_restart`, `late_axis_risk`) |
| `E-R10` ETV-MLP (optional appendix) | **DROPPED.** Removed entirely. The quality verifier is near-saturated (ridge within-prompt NDCG ~0.995); capacity is **not** the bottleneck. **EVPD (§B) is the ONLY learned neural component in ADSR.** | — |
| `etv_rc_select` / `etv_adaptive_select` — prune/select over a *frozen* pool | **DEMOTED.** Raw Early-Tweedie pruning (Schedule A/B/C, bottom-prune) becomes the **`raw ETP` same-compute baseline** (METHOD_SPEC §15); conformal `ε∈{1,3,5}%` calibration is retained only as an *optional* risk-controlled restart-threshold calibration (METHOD_SPEC §16.2). | the headline is now §C `adsr_decide` (restart/defer/continue), not pool selection |
| — | **NEW** | §B `evpd_forward` (early mel → final vocal-presence label; small CNN / fine-tuned audio encoder) |
| — | **NEW** | §C `adsr_decide` (RESTART/DEFER/CONTINUE with type-match priority) + §D `adsr_offline_simulate` (matched-expected-NFE accounting) |

**Evidence honesty (binding).** Everything in §B–§D is **PLANNED, not run.** EVPD
is **NOT trained**; the restart/ADSR method is **NOT executed** (only
offline-simulatable on the existing 4096-candidate pool); vocal-presence labels
are **NOT yet derived**; the H2b presence-vs-content split is **unmeasured**. The
only reported numbers remain *foundation* numbers carried forward: lyric **0.682**
ETP@50 on the **EN-vocal n=282** subset (never the pooled 0.8432), Track A
Schedule A **0.9864** reward_fraction @ 0.500 compute. No `r_final`, AUC, onset σ,
or Pareto number below is a result; these are the *update rules* the
implementation must realize.

---

### A. Lightweight quality verifier (survives; ETV E-R7/8/9 → ADSR Q-R7/8/9)

Feature vector and tiers are **unchanged** from the ETV addendum above and from
METHOD_SPEC §14.1; reproduced compactly with the ADSR target set. **No MLP tier.**

```
features(c, i) =
  [ r_lcb(â_{c,i,0.9}), r_lcb(â_{c,i,0.8}), r_lcb(â_{c,i,0.7}),
    r_lcb(â_{c,i,0.7}) − r_lcb(â_{c,i,0.9}),                # slope
    rank_0.9(c,i), rank_0.8(c,i), rank_0.7(c,i),
    prompt_type(c),                                          # vocal / instrumental
    # optional ablation features:
    r_pq(â_{c,i,0.7}), r_clap(â_{c,i,0.7}), r_mert(â_{c,i,0.7}),
    std_axes(â_{c,i,0.7}) ]                                  # uncertainty (ablation)
# All read from cached Track A records — NO GPU forward pass at train time.
```

```python
# Q-R7 (floor): ridge / logistic            sklearn.linear_model
# Q-R8 (PRIMARY): GBDT pairwise ranker       lightgbm.LGBMRanker(objective='lambdarank')
# Q-R9 (listwise): LambdaMART                lightgbm.LGBMRanker(objective='lambdarank', ndcg_at=[1,2,4])
# Train = dev256, eval = heldout256, group = within-prompt BoN-8; split by prompt_id; NO candidate leakage.

def quality_verifier_predict(model_Q, c, i):
    # NEW ADSR targets (heads / separately-fit regressors on the same features):
    return {
        "rank_or_reward": model_Q.predict(features(c, i)),  # final rank / robust-reward (ETV target)
        "safe_restart_prob": model_safe.predict(features(c, i)),   # NEW: P(safe to restart this cand)
        "late_axis_risk":    model_risk.predict(features(c, i)),   # NEW: predicted late-axis (semantic/lyric) risk
    }
# Capacity is NOT the bottleneck (ridge NDCG ~0.995). Compute: 0 GPU-h, ≤10 CPU-h.
```

### B. Early Vocal-Presence Detector — EVPD (NEW; the ONLY learned neural net)

Predicts the **final** vocal-presence label from the **early** Tweedie-clean
mel-spectrogram of `x̂₀` at decision σ. **Not yet trained.** Full contract:
METHOD_SPEC §14.2; label derivation: §2.5.

```python
# Architecture: small CNN over the early mel, OR a fine-tuned pretrained audio
# encoder (small AST / PANNs / MERT-frontend head). Output p_vocal ∈ [0,1].
# Per-σ heads so the vocal-presence DECIDABILITY ONSET σ can be reported.

def evpd_make_input(model_θ, z_σ, σ, c, D):
    x̂₀  = tweedie_clean(z_σ, σ, model_θ(z_σ, σ, c))     # = x_σ − σ·v_θ ; reuse §2.1 / §4.1
    mel = log_mel_spectrogram(D(x̂₀))                    # early decoded estimate → mel
    return mel

def evpd_train(train_candidates, σ_set=[0.9, 0.8, 0.7]):
    # Labels: FINAL vocal-presence (source separation Demucs/Spleeter vocal-energy
    # ratio, or an SVD model). Whisper no_speech_prob is a COARSE pre-filter only.
    # Labels NOT yet derived → this is plan-stage. Training data = 4096 relabeled cands.
    for σ in σ_set:                                       # per-σ head
        X = [evpd_make_input(model_θ, cand.z_σ[σ], σ, cand.c, D) for cand in train_candidates]
        y = [cand.final_vocal_presence_label for cand in train_candidates]
        evpd[σ].fit(X, y)                                 # small audio net; GPU training (the one new GPU cost)
    return evpd

def evpd_forward(evpd, σ, mel):
    return evpd[σ].predict(mel)                           # p_vocal ∈ [0,1]

# prompt-type match := compare p_vocal to requested_type(c).
# E3 reports: AUC per σ, vocal-presence-onset σ, type-error prevalence
#   (vocal-prompt→instrumental & instrumental-prompt→vocal), type-match rate
#   after restart, false-restart-on-type rate. Off-the-shelf (clean-audio) SVD
#   detector on the early estimate is the EVPD baseline (expected OOD-weak).
```

### C. ADSR decision logic: RESTART / DEFER / CONTINUE (NEW headline)

`RESTART` = terminate this trajectory and launch a **NEW independent seed**
(compute *reallocation*, **not** a rollback/repair). `DEFER` = carry to a later σ
before deciding. `CONTINUE` = run to completion. **Type-match has priority.**
Contract: METHOD_SPEC §13; thresholds §16.2.

```python
def adsr_decide(prompt_c, cand, σ_c, evpd, model_Q,
                τ_type, τ_q, τ_risk):
    â   = decode(cand.z_at[σ_c])                          # early Tweedie-clean estimate
    mel = log_mel_spectrogram(â)

    # (1) HIGH-STAKES, EARLY, COARSE — prompt-type match (EVPD). Judges PRESENCE, not content.
    p_vocal = evpd_forward(evpd, σ_c, mel)
    if type_disagrees(p_vocal, requested_type(prompt_c), confidence ≥ τ_type):
        return "RESTART"                                  # gross type error — categorical, UNUSABLE failure

    # (2) EARLY-OBSERVABLE QUALITY clearly low AND late-axis risk low/irrelevant
    q = quality_verifier_predict(model_Q, prompt_c, cand.i)
    if q["safe_restart_prob"] ≥ τ_q and q["late_axis_risk"] ≤ τ_risk:
        return "RESTART"

    # (3) LATE-OBSERVABLE CONTENT risk high/uncertain — NEVER early-reject
    elif semantic_or_lyric_content_risk(â) is high or uncertain:
        return "DEFER"                                    # judged at later σ; lyric is the canonical defer case

    # (4) otherwise
    else:
        return "CONTINUE"

# H2b load-bearing distinction: vocal PRESENCE + gross production are early-decidable
# (may RESTART); lyric CONTENT + fine semantics are late-decidable (must DEFER).
```

### D. Matched-expected-NFE compute accounting + offline-first simulation (NEW)

ADSR is compared at **matched expected total NFE** with **NO optimistic
accounting**: a RESTART's terminated partial cost is **sunk and counted**, and
the new seed re-pays the full forward cost. Contract: METHOD_SPEC §16.3 / §16.4.

```python
def expected_nfe(decisions, σ_c, nfe_to, nfe_full):
    # decisions: per-candidate {decision, deferred_to_σ?} ; nfe_to(σ) from compute_metadata.
    total = 0
    for d in decisions:
        total += nfe_to(σ_c)                              # (a) partial-to-σ_c — EVERY candidate pays this
        if d.decision == "CONTINUE" or d.accepted_defer:
            total += (nfe_full − nfe_to(σ_c))             # (b) surviving full-completion cost
        if d.decision == "RESTART":
            total += nfe_full                             # (c) restart NEW-SEED cost — re-pays from σ=1 (NOT free)
        if d.decision == "DEFER":
            total += (nfe_to(d.deferred_to_σ) − nfe_to(σ_c))  # (d) deferred-continuation cost
    return total
    # FORBIDDEN: counting only survivors, ignoring sunk partial cost, or ignoring restart re-pay.
    # Baselines (Full BoN-8, BoN-4, random/raw restart, learned-verifier select, type-match restart)
    # are evaluated at the SAME expected NFE (METHOD_SPEC §15).

def adsr_offline_simulate(pool_by_prompt, σ_c, evpd, model_Q, thresholds, nfe_budget):
    # OFFLINE-FIRST (primary; 0 GPU-h beyond label derivation). RESTART := draw the
    # NEXT independent BoN-8 sibling of the same prompt from the 4096-pool (siblings
    # are independent seeds). Replay §C decisions under the matched-NFE budget.
    results = []
    for c, candidates in pool_by_prompt.items():          # split by prompt_id
        kept, spent, queue = [], 0, list(candidates)      # queue = independent siblings
        while queue and spent ≤ nfe_budget:
            cand = queue.pop(0)
            d = adsr_decide(c, cand, σ_c, evpd, model_Q, **thresholds)
            spent += incremental_nfe(d, σ_c)              # per-decision accounting (eq. above)
            if d == "RESTART":   continue                 # terminate; next sibling funds the new draw
            elif d == "DEFER":   queue.insert(?, carry_to_later_σ(cand))
            else:                kept.append(complete(cand))   # CONTINUE
        winner = argmax(kept, key=r_final) if kept else None
        results.append(measure(c, winner, kept))          # final robust reward, semantic & lyric
                                                          #   preservation (EN-vocal n=282 ONLY),
                                                          #   prompt-type-match rate, winner retention,
                                                          #   false-restart rate
    return results
    # Then a SMALL real-generation confirm where RESTART launches a genuinely fresh
    # seed beyond the 8-sibling pool (the only active-method GPU cost besides EVPD training).
```

### Linkage

- Quality-verifier features consume cached scores now promoted to the canonical
  set `orbit-research/trajectory_candidate_dataset.jsonl` (4096 records; merged
  2026-06-04). No GPU forward pass at verifier train time.
- `raw ETP` schedule baselines are taken verbatim from
  `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md` (Schedule A 0.9864 @ 0.500;
  raw-ETP@50 over BoN-4 ≈ +0.0036 — *motivation, not headline*).
- EVPD label derivation and per-σ training data flow from METHOD_SPEC §2.5 (vocal-
  presence label) and §2.4 (early-σ decoded-audio cache).
- The R0–R21 M-PRM ladder (§§1–7 above) and the ETV §12 verifier pseudocode
  remain valid as **boundary** reference (C6 RL paragraph; ETV-as-baseline);
  they are no longer the active method.
- Full ADSR contract + PLAN_CODE_AUDIT checklist: METHOD_SPEC §§13–16.

The §A–§D pseudocode is the runnable shape behind METHOD_SPEC §§13–16 (ADSR
active method). It is plan-stage: no EVPD/restart/ADSR result exists until E3/E6
run.
