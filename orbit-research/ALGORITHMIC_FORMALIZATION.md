# Algorithmic Formalization — Headroom-Gated M-PRM (PI v2.0)

> *Pseudocode-level formalization of every rung and ablation route in the M-PRM ladder. Refer
> `METHOD_SPEC.md` v2.0 for the implementation contract; this file is the runnable shape behind
> each clause.*
>
> **Status note.** Stage 14 (Algorithmic Formalization) is `EXPERIMENT_PLAN_READY`; pseudocode
> here freezes the *intended* update rule for every rung R0–R21. Per-rung Q-PRM-1..8 open
> questions live in `METHOD_SPEC.md` §8 and are closed at `PLAN_CODE_AUDIT.md` time.
>
> **Cross-references.** Symbol table inherits `METHOD_SPEC.md` §0. Each rung in this file maps
> to a rung in `COMPONENT_BUNDLE_LADDER.md` §1 and an ablation row in `CONTROL_DESIGN.md` §3.
> Reward functions are defined in `METHOD_SPEC.md` §2.

---

## 0. Symbols and conventions

- `θ` — policy weights (LoRA-adapted from `θ_init` per `METHOD_SPEC.md` §1.4).
- `θ_init` — frozen reference policy (= base ACE-Step or SAO).
- `c` — conditioning (prompt + lyric + style metadata).
- `x` — latent or audio sample (context-dependent).
- `D` — DCAE / VAE decoder (`METHOD_SPEC.md` §1.2).
- `T_train` / `T_inference` — training-vs-inference denoising step counts (`METHOD_SPEC.md` §4.1).
- `K` — number of Tweedie reward checkpoints per trajectory (default 4).
- `Π` — robust-LCB perturbation set (`METHOD_SPEC.md` §2.2).
- `R_axes` — vector of axis-level reward outputs (`METHOD_SPEC.md` §2.1).
- `R_lcb` — robust lower confidence bound (`METHOD_SPEC.md` §2.2).
- `probe_pen` — anti-hacking probe penalty composite (silence + autocorr + HF artifact).
- `α, β` — CVaR tail fraction and mean weight in §3.4 (default `0.30 / 0` per REVISED 2026-05-20 C2 — was `0.30 / 0.50`).
- `ε_lyric` — lyric Pareto slack in `METHOD_SPEC.md` §5.4 (default 0).
- `λ_KL` — KL anchor coefficient (default 0.05 initial; decays per scheduler).
- `λ_growth` / `λ_decay` — Lagrange multiplier update rates (`METHOD_SPEC.md` §5.4).
- `G` — group size for GRPO-like objectives (default 8).
- `η` — learning rate.

---

## 1. Phase A — Headroom-First Audit

### 1.1 Base sampling

```
def base_sample(θ_init, c, T_inference, cfg=cfg_default):
    z₀ ∼ N(0, I)
    for t in inference_schedule(T_inference):
        ẑ_t = ode_step(θ_init, z_t, c, t, cfg)
    a = D(z_T)
    return a
```

### 1.2 CFG sweep

```
def cfg_sweep_run(θ_init, prompts, cfg_grid):
    return {(c, ω): base_sample(θ_init, c, T_inference, ω) for c in prompts for ω in cfg_grid}
```

### 1.3 BoN-N selection

```
def bon_select(θ_init, c, N, cfg, reward_fn=R_lcb, top_k=1):
    samples = [base_sample(θ_init, c, T_inference, cfg) for _ in range(N)]
    rewards = [reward_fn(s, c) for s in samples]
    return select_topk(samples, rewards, k=top_k)
```

`R_lcb` aggregates per-axis CLAP, Audiobox-aesthetics-4, lyric-WER, MERT, and anti-hacking
probes per `METHOD_SPEC.md` §2.1–§2.3.

### 1.4 SFT-on-best-of-N

```
def sft_on_bon(θ_init, prompts, N, cfg, sft_steps, η, lora_rank=8):
    θ = lora_attach(θ_init, rank=lora_rank)
    dataset = []
    for c in prompts:
        best = bon_select(θ_init, c, N, cfg, R_lcb)
        dataset.append((c, best))
    for step in range(sft_steps):
        c, target = sample(dataset)
        ẑ = forward_flow(θ, target, c)
        loss = flow_matching_loss(θ, ẑ, target, c)
        θ ← θ − η · ∇loss
    return θ
```

This is the "Best-of-N then SFT" baseline (R5 / S2 in tournament terms).

### 1.5 Robust Elite SFT (former S6 Stages 0–3)

```
def robust_elite_sft(θ_init, prompts, N_BoN, cfg, sft_steps, η, lora_rank=8,
                     reward_fn=R_lcb, probe_filter=True):
    θ = lora_attach(θ_init, rank=lora_rank)
    elite_dataset = []
    for c in prompts:
        samples = [base_sample(θ_init, c, T_inference, cfg) for _ in range(N_BoN)]
        rewards = [reward_fn(s, c) for s in samples]
        if probe_filter:
            rewards = [r if probe_pen(s) < threshold else -∞ for r, s in zip(rewards, samples)]
        elite = select_topk(samples, rewards, k=max(1, int(0.125 * N_BoN)))
        for s in elite:
            elite_dataset.append((c, s))
    for step in range(sft_steps):
        c, target = sample(elite_dataset)
        ẑ = forward_flow(θ, target, c)
        loss = flow_matching_loss(θ, ẑ, target, c)
        θ ← θ − η · ∇loss
    return θ
```

This is the R6 rung (Robust Elite SFT). The robust LCB + anti-hacking probe + top-12.5%
elite selection together implement Codex's calibrated F6 mechanisms preserved from the
Phase 4 calibration audit.

### 1.6 S7 sampler-control-only

```
def s7_sampler_controller(θ_init, c, controller_params, T_inference, reward_fn=R_lcb):
    # Tune per-step controller (sigma schedule, CFG schedule, churn) without weight update.
    best = (None, -∞)
    for params in sample(controller_params, M=controller_budget):
        z₀ ∼ N(0, I)
        for t in inference_schedule(T_inference, params):
            ẑ_t = ode_step(θ_init, z_t, c, t, params)
        a = D(z_T)
        r = reward_fn(a, c)
        if r > best[1]:
            best = (a, r)
    return best[0]
```

`controller_params` includes: `σ_schedule_shape`, `cfg_schedule_shape`, `churn`, `solver_type`.
Search budget per `configs/baselines/r9_s7_sampler_control.yaml`.

### 1.7 Flow-DPO (offline preference)

```
def flow_dpo(θ_init, preference_pairs, dpo_steps, η, β_dpo, lora_rank=8):
    θ = lora_attach(θ_init, rank=lora_rank)
    for step in range(dpo_steps):
        (c, x_w, x_l) = sample(preference_pairs)             # winner, loser
        ẑ_w = forward_flow(θ, x_w, c); ẑ_w_ref = forward_flow(θ_init, x_w, c)
        ẑ_l = forward_flow(θ, x_l, c); ẑ_l_ref = forward_flow(θ_init, x_l, c)
        logp_w = log_density_flow(ẑ_w, x_w, c, θ); logp_w_ref = log_density_flow(ẑ_w_ref, x_w, c, θ_init)
        logp_l = log_density_flow(ẑ_l, x_l, c, θ); logp_l_ref = log_density_flow(ẑ_l_ref, x_l, c, θ_init)
        loss = -log_σ(β_dpo · ((logp_w − logp_w_ref) − (logp_l − logp_l_ref)))
        θ ← θ − η · ∇loss
    return θ
```

Preference pairs constructed from BoN selection on `R_lcb` (winner = top-1, loser = bottom-1 of
N=8).

### 1.8 Vanilla Flow-GRPO (= S1 = baseline; Outcome-GRPO when wrapped with v2.0 reward + lyric guard)

```
def flow_grpo_outcome(θ_init, prompts, G, T_train, η_schedule, rl_steps, reward_fn=R_lcb,
                      cfg, λ_KL=0.05, lora_rank=8):
    θ = lora_attach(θ_init, rank=lora_rank)
    θ_ref = freeze(θ_init)
    for step in range(rl_steps):
        c = sample(prompts)
        group_z₀ = [N(0, I) for _ in range(G)]
        group_traj = [sde_unroll(θ, z₀, c, T_train, η_schedule) for z₀ in group_z₀]
        group_a = [D(traj[-1]) for traj in group_traj]
        group_r = [reward_fn(a, c) for a in group_a]
        # GRPO group baseline
        A = (group_r − mean(group_r)) / (std(group_r) + ε_norm)
        group_logp = [accumulate_logp(θ, traj) for traj in group_traj]
        ratio = [exp(logp − logp_old) for logp, logp_old in zip(group_logp, accumulated_logp_old)]
        pg_loss = -mean([min(r · a, clip(r, 1-ε_clip, 1+ε_clip) · a) for r, a in zip(ratio, A)])
        kl = mean([KL(θ, θ_ref, traj) for traj in group_traj])
        loss = pg_loss + λ_KL · kl
        θ ← θ − η · ∇loss
    return θ
```

`reward_fn` defaults to `R_lcb` and (for ACE-Step) is wrapped with the Lagrangian lyric guard
(`§ 3.5` below). Without the guard this is vanilla Flow-GRPO; with the guard it is Outcome-GRPO.

---

## 2. Phase B — Process-reward reliability and credit-unit falsification

### 2.1 Tweedie-clean intermediate decode

The exact parameterization depends on the FM/RF backbone (`Q-PRM-1`). For rectified-flow (used by
both ACE-Step's DCAE-DiT head and SAO's DiT):

```
def tweedie_clean(z_τ, τ, v_pred):
    # Rectified-flow: z₁_hat = z_τ + (1 − τ) · v_pred(z_τ, τ, c)
    return z_τ + (1 − τ) * v_pred
```

Variants verified in `Q-PRM-1` reconstruction sanity check (Phase B.1):

```
def tweedie_decode(model_θ, z_τ, τ, c, decoder D):
    v_pred = model_θ(z_τ, τ, c)
    ẑ₁ = tweedie_clean(z_τ, τ, v_pred)
    return D(ẑ₁)
```

### 2.2 Reliability gate

```
def reliability_gate(model_θ, calibration_prompts, K, ρ_min=0.5):
    # REVISED 2026-05-20 (C3): threshold raised from 0.35 to 0.5 binary gate.
    # Pairs with ρ < ρ_min are excluded from gradient target but reported in analysis.
    checkpoints = pick_checkpoints(K, bias="late_middle")     # e.g. τ ∈ {0.7, 0.5, 0.3, 0.1}
    reliable = {}
    for axis in {"aesthetic", "semantic_fit", "lyric", "coherence", "section_continuity"}:
        for k in checkpoints:
            r_k = []; r_final = []
            for c in calibration_prompts:
                z₀ = N(0, I)
                traj = sde_unroll(model_θ, z₀, c, T_train, η_schedule)
                z_{τ_k} = traj[τ_k]
                â_k = tweedie_decode(model_θ, z_{τ_k}, τ_k, c, D)
                a_final = D(traj[-1])
                r_k.append(r_axis(â_k, c, axis))
                r_final.append(r_axis(a_final, c, axis))
            ρ = spearmanr(r_k, r_final)
            if ρ ≥ ρ_min:
                reliable[(axis, k)] = ρ
    if len(reliable) < 2:
        return "PIVOT_TO_TERMINAL_REWARD_STUDY"
    return reliable
```

### 2.3 Credit-unit comparison

```
def credit_unit_run(model_θ, prompts, reliable_axis_checkpoints, units):
    # units = {timestep, fixed_4s, beat_window, lyric_span, section_window}
    per_unit_correlations = {u: {} for u in units}
    for c in prompts:
        z₀ = N(0, I)
        traj = sde_unroll(model_θ, z₀, c, T_train, η_schedule)
        a_final = D(traj[-1])
        for u in units:
            segments_u = segment(a_final, unit=u)              # MERT/CBM for section, beat-tracker for beat, etc.
            for k in {τ_k for (axis, τ_k) in reliable_axis_checkpoints}:
                â_k = tweedie_decode(model_θ, traj[τ_k], τ_k, c, D)
                segments_â_k = segment(â_k, unit=u)
                Δr_unit = []
                for s in segments_u:
                    Δr = [r_axis(s_â_k, c, axis) − r_axis(prev_â_k_s, c, axis)
                          for axis in reliable_axes_for_k(k)]
                    Δr_unit.append(mean(Δr))
                # correlate with per-section human preference (collected separately)
                ρ_u = spearmanr(Δr_unit, human_per_segment_pref(c, u))
                per_unit_correlations[u][k] = ρ_u
    return per_unit_correlations
```

### 2.4 Credit-unit gate

```
def credit_unit_gate(per_unit_correlations, margin=0.08, axes_required=2):
    section = per_unit_correlations["section_window"]
    non_section = {u: per_unit_correlations[u] for u in units if u != "section_window"}
    n_axes_section_wins = 0
    for axis in {"musicality", "coherence", "prompt_fit"}:
        ρ_section = max(section[k][axis] for k in section)
        ρ_best_non_section = max(max(non_section[u][k][axis] for k in section)
                                  for u in non_section)
        if ρ_section >= ρ_best_non_section + margin:
            n_axes_section_wins += 1
    held_out_replicates = replicate_on_held_out(...)
    if n_axes_section_wins >= axes_required and identifies_broken_sections() and held_out_replicates:
        return "SECTION_CREDIT_PASSES"
    return "PIVOT_TO_CREDIT_UNIT_NEGATIVE_STUDY"
```

### 2.5 Locality probe

```
def locality_probe(model_θ, prompts, perturbation="gaussian", batch_size=32):
    ratios = []
    for c in prompts[:batch_size]:
        z₀ = N(0, I)
        traj = sde_unroll(model_θ, z₀, c, T_train, η_schedule)
        z_{τ_mid} = traj[T_train // 2]
        for u in random_subset(segments(D(traj[-1]))):
            (τ_a, τ_b) = latent_span_of(u)                      # ACE-Step DCAE rate per Q-PRM-5
            z_perturbed = perturb_span(z_{τ_mid}, τ_a, τ_b, method=perturbation)
            traj_perturbed = sde_unroll_from(model_θ, z_perturbed, τ_mid, c)
            a_perturbed = D(traj_perturbed[-1])
            a_base = D(traj[-1])
            Δ_target = energy_or_perceptual_diff(a_perturbed[u], a_base[u])
            Δ_neighbor = energy_or_perceptual_diff(a_perturbed[neighbors_of(u)], a_base[neighbors_of(u)])
            ratios.append(Δ_target / (Δ_neighbor + ε))
    median_ratio = median(ratios)
    if median_ratio >= 2.0:
        return "STRICT_MASKED_GRADIENT"
    if median_ratio >= 1.5:
        return "ACTION_LOCALIZED_ADVANTAGE"
    return "GLOBAL_ADVANTAGE_FALLBACK"
```

**Gradient-locality hot-standby probe** (REVISED 2026-05-20 C4):

```
def gradient_locality_probe(model_θ, prompts, K=4, batch_size=10):
    # HOT-STANDBY: only run on trigger (decoder-locality ambiguous 1.2-1.8, or reviewer demand).
    # Smoke test at Phase B kickoff = 2 prompts only.
    ratios = []
    for c in prompts[:batch_size]:
        traj = sde_unroll(model_θ, N(0,I), c, T_train, η_schedule)
        a_final = D(traj[-1])
        for u in segments(a_final)[:K]:
            (τ_a, τ_b) = latent_span_of(u)
            grad = autograd(log p(a_final | x_τ), x_τ_span_u)   # Jacobian wrt span_u latents
            in_section = norm(grad[span_u])
            cross_section = mean([norm(grad[s]) for s in segments if s != u])
            ratios.append(in_section / (cross_section + ε))
    return median(ratios)
```

---

## 3. Phase C — M-PRM training (Sketch S8)

### 3.1 Section-level process reward

```
def section_process_reward(model_θ, traj, c, reliable_axis_checkpoints):
    a_final = D(traj[-1])
    segments = segment(a_final, unit="section_window")          # MERT/CBM
    Δr = {}
    for u in segments:
        Δr[u] = {}
        for (axis, τ_k) in reliable_axis_checkpoints:
            â_k = tweedie_decode(model_θ, traj[τ_k], τ_k, c, D)
            â_kp = tweedie_decode(model_θ, traj[τ_k − 1], τ_{k−1}, c, D)
            segments_â_k = segment(â_k, unit="section_window")
            Δr[u][axis][τ_k] = r_axis(segments_â_k[u], c, axis) − r_axis(segments_â_kp[u], c, axis)
    return Δr
```

For axes that failed the reliability gate at intermediate `k`, reward applied at final / late
checkpoint only (per `METHOD_SPEC.md` §5.1).

### 3.2 Lagrangian advantage with lyric guard

```
def lagrangian_advantage(Δr_music_u, Δr_lyric, λ_cur, ε):
    # Per-section music advantage, lyric is a song-level constraint
    return Δr_music_u + λ_cur * (Δr_lyric + ε)
```

The lyric guard is **inactive for instrumental prompts** (detected via vocal-stem energy + lyric
metadata flag). `Δr_lyric` uses Whisper-WER on Demucs-extracted vocal stem only at the late /
final checkpoint (per `METHOD_SPEC.md` §5.4). REVISED 2026-05-20 C5: H5 tradeoff check at ε ∈ {0, σ_WER} + no-guard control (NOT "Pareto curve" — 2 points + control).

### 3.3 Lagrange multiplier update

```
def update_lambda(λ_cur, lyric_rolling_window, ε):
    rolling_R_lyric = mean(lyric_rolling_window)
    if rolling_R_lyric < target_lyric_baseline − ε:
        λ_cur = λ_cur * λ_growth                                # default growth = 1.1
    elif rolling_R_lyric > target_lyric_baseline + ε:
        λ_cur = λ_cur * λ_decay                                  # default decay = 0.95
    return clip(λ_cur, λ_min, λ_max)                             # default {0.01, 5.0}
```

### 3.4 CVaR aggregation

```
def cvar_aggregate(A_per_section, α=0.30, β=0):
    # REVISED 2026-05-20 (C2): main M-PRM default β=0 (was β=0.50 — diluted CVaR signal).
    # β=0.5 figure is reported as OFFLINE SCORING SENSITIVITY: re-aggregate trained β=0
    # policy's per-section reward distributions; NO separately trained β=0.5 policy.
    A_values = list(A_per_section.values())
    sorted_A = sorted(A_values)                                  # ascending
    n_tail = max(1, int(ceil(α * len(sorted_A))))
    A_cvar = mean(sorted_A[:n_tail])                             # lower-tail mass
    A_mean = mean(sorted_A)
    return A_cvar + β * A_mean
```

### 3.5 Action-localized GRPO loss

```
def grpo_action_localized_loss(A_per_section, group_logp, latent_spans, locality_decision):
    pg = 0
    for g in range(G):                                            # group sample index
        logp_old = group_logp[g]
        logp_new = recompute_logp(θ, traj_g)
        ratio_steps = exp(logp_new − logp_old)                    # per-step ratio
        for u in segments(D(traj_g[-1])):
            (τ_a, τ_b) = latent_spans[u]
            if locality_decision == "STRICT_MASKED_GRADIENT":
                mask = indicator(step_τ ∈ [τ_a, τ_b])             # strict mask
            elif locality_decision == "ACTION_LOCALIZED_ADVANTAGE":
                mask = smoothed_indicator(step_τ, τ_a, τ_b)       # soft mask
            elif locality_decision == "GLOBAL_ADVANTAGE_FALLBACK":
                mask = ones_like(step_τ)                          # global = no localization
            A_u = A_per_section[u]
            pg += mean(mask · min(ratio_steps · A_u,
                                   clip(ratio_steps, 1 − ε_clip, 1 + ε_clip) · A_u))
    return −pg / G
```

### 3.6 Headroom-weighted prompt curriculum

```
def curriculum_weights(audit_stats, w_min, w_max):
    # REVISED 2026-05-20 (C7): weights derived strictly from DEV split only;
    # held-out uses uniform sampling. Gate thresholds SHA-pinned to gate_v2.yaml ≥24h
    # before any held-out evaluation. Bootstrap CI across 4 prompt-family strata reported.
    raw = {}
    for c in audit_stats:                                         # audit_stats: DEV ONLY
        raw[c] = (audit_stats[c]["bon_spread"] ·
                  audit_stats[c]["base_failure_rate"] ·
                  audit_stats[c]["evaluator_disagreement"] ·
                  audit_stats[c]["section_failure_freq"] ·
                  audit_stats[c]["lyric_failure_freq"])
    weights = {c: clip(raw[c] / mean(raw.values()), w_min, w_max)
               for c in audit_stats}                              # w_min = 1/(2n), w_max = 5/n
    return normalize(weights)
```

### 3.7 Full M-PRM training loop (S8)

```
def m_prm_train(model_θ, audit_prompts, reliable_axis_checkpoints, locality_decision,
                K, α, β, ε_lyric, λ_KL, rl_steps, G, T_train, q_curriculum,
                max_kl_vs_ref=5.0):
    # REVISED 2026-05-20 (C8): max_kl_vs_ref pre-registered abort threshold (5.0 nats).
    # Final KL reported alongside gate_r_lcb in main table; cumulative KL trace per 100 steps.
    θ = copy(θ_init); θ_ref = freeze(θ_init)
    λ_cur = 0.5                                                   # initial Lagrange multiplier
    lyric_rolling = deque(maxlen=window)
    for step in range(rl_steps):
        c = sample(q_curriculum)
        group_z₀ = [N(0, I) for _ in range(G)]
        group_traj = [sde_unroll(θ, z₀, c, T_train, η_schedule) for z₀ in group_z₀]
        group_logp_old = [accumulate_logp_detached(θ, traj) for traj in group_traj]

        # Section-level process reward across reliable axes
        Δr_per_sample = [section_process_reward(θ, traj, c, reliable_axis_checkpoints)
                          for traj in group_traj]

        # Per-section Lagrangian advantage
        A_per_section = []
        for Δr in Δr_per_sample:
            R_music_per_u = aggregate_music_axes(Δr)
            R_lyric_full = whisper_wer(D(group_traj[g][-1]), c)
            A_u = {u: lagrangian_advantage(R_music_per_u[u], R_lyric_full, λ_cur, ε_lyric)
                   for u in R_music_per_u}
            A_per_section.append(A_u)

        # CVaR aggregation gives the song-level signal (used for ratio normalization)
        A_song = [cvar_aggregate(A_u, α, β) for A_u in A_per_section]

        # GRPO group baseline on A_song
        A_song = (A_song − mean(A_song)) / (std(A_song) + ε_norm)

        # Action-localized loss with locality decision
        latent_spans = [{u: latent_span_of(u) for u in A_u} for A_u in A_per_section]
        pg_loss = grpo_action_localized_loss(A_per_section, group_logp_old, latent_spans,
                                              locality_decision)

        kl = mean([KL(θ, θ_ref, traj) for traj in group_traj])
        if kl > max_kl_vs_ref:
            log(f"ABORT: KL budget exceeded at step={step}, kl={kl}")
            break                                                  # C8 abort
        if step % 100 == 0:
            log_kl_trace(step, kl)                                # C8 trace log
        loss = pg_loss + λ_KL · kl
        θ ← θ − η · ∇loss

        lyric_rolling.append(mean([1 − whisper_wer(D(traj[-1]), c) for traj in group_traj]))
        λ_cur = update_lambda(λ_cur, lyric_rolling, ε_lyric)
    return θ
```

---

## 4. Phase C alternative — Section-conditioned global advantage (H4 false fallback)

If `locality_decision == "GLOBAL_ADVANTAGE_FALLBACK"`, the action-localized loss reduces to:

```
def grpo_section_conditioned_global_loss(A_song, group_logp):
    # A_song is the CVaR-aggregated section reward;
    # advantage is global (not span-routed) but the *signal* still encodes
    # section-level information via the aggregation.
    pg = 0
    for g in range(G):
        ratio_g = exp(group_logp[g] − group_logp_old[g])
        pg += mean(min(ratio_g · A_song[g], clip(ratio_g, 1 − ε_clip, 1 + ε_clip) · A_song[g]))
    return −pg / G
```

This is the safe degradation route per H4. M-PRM is still defensible as an aggregation /
selection signal even without localized credit.

---

## 5. Phase D ablation variants (formal definition)

Each ablation removes exactly one M-PRM component while keeping all others fixed.

| Ablation | Removal | Formal substitution |
|---|---|---|
| **No action localization** | force `locality_decision = "GLOBAL_ADVANTAGE_FALLBACK"` even if probe passes | `mask := ones_like(step_τ)` in `grpo_action_localized_loss` |
| **No lyric guard** | drop the Lagrangian term | `lagrangian_advantage(R_music_per_u[u], _, _, _) := R_music_per_u[u]` |
| **Mean instead of CVaR** | replace `cvar_aggregate` with `mean` | `A_song := mean(list(A_u.values()))` |
| **β=0.5 offline scoring sensitivity** (added C2) | re-aggregate trained β=0 policy's saved per-section rewards | `A_song_β=0.5 := cvar_aggregate(saved_A_u, α=0.30, β=0.5)` — 0 GPU-h, post-hoc only |
| **Fixed-window instead of section** | replace `segment(·, unit="section")` with `segment(·, unit="fixed_4s")` | substitute segmenter |
| **Raw reward (no robust LCB)** | use `mean(R_axes)` instead of `R_lcb` | `R := mean(R_axes(x, c, identity))` |
| **No curriculum** | uniform `q(c)` instead of `q_curriculum` | `q(c) := uniform(audit_prompts)` |
| **No process reward (= Outcome-GRPO)** | use only `r_axis(a_final, c, axis)` | replace `section_process_reward` with terminal reward |

Each substitution is a **single-line change** in the M-PRM training driver. This makes the
ablations cheap to audit and unambiguous in interpretation.

---

## 6. Baselines (formal definitions for Phase D.1)

| # | Method | Formal definition (cite from above) |
|---|---|---|
| 1 | Base ACE-Step | `base_sample(θ_init, c, T_inference, cfg_default)` |
| 2 | CFG / BoN / BoN+CFG | `cfg_sweep_run` ∪ `bon_select` ∪ both combined |
| 3 | S7 sampler-control-only | `s7_sampler_controller(θ_init, ...)` |
| 4 | Robust elite SFT (= former S6) | `robust_elite_sft(θ_init, ...)` |
| 5 | Flow-DPO | `flow_dpo(θ_init, preference_pairs, ...)` |
| 6 | Outcome-GRPO-plain (R8a, canonical) | `flow_grpo_outcome(θ_init, ..., reward_fn = R_lcb_NO_lyric_guard)` |
| 6b | Outcome-GRPO-guarded (R8b, stronger) | `flow_grpo_outcome(θ_init, ..., reward_fn = R_lcb_with_lyric_guard)` |
| 7 | Stepwise-Tweedie | `m_prm_train` with `unit = "timestep"`, `cvar = mean`, `locality = global` |
| 8 | FixedWin-Tweedie | as 7 but `unit = "fixed_4s"` |
| 9 | BeatWin-Tweedie | as 7 but `unit = "beat_window"` |
| 10 | LyricSpan-Tweedie | as 7 but `unit = "lyric_span"` |
| 11 | **M-PRM full (S8)** | `m_prm_train(θ_init, ..., unit = "section_window", α = 0.30, β = 0, ε_lyric = 0)` |

Note: rows 7–10 are *Tweedie process-reward baselines* that differ from M-PRM (row 11) **only**
in the segmentation unit; everything else (Tweedie decode, reliability gate, CVaR, lyric guard,
curriculum, action localization if applicable) is identical. This is the cleanest possible
isolation of the credit-unit hypothesis H3.

---

## 7. Cross-reference: where each `METHOD_SPEC.md` clause lands here

| `METHOD_SPEC.md` §  | This formalization §  |
|---|---|
| §1 Targets and interfaces | §0 + §3.7 (`θ_init` references) |
| §2 Reward functions | `R_axes`, `R_lcb`, `probe_pen` in §0 + §1.3 |
| §3 Phase A | §1.1–§1.8 |
| §4 Phase B | §2.1–§2.5 |
| §5 Phase C | §3.1–§3.7 |
| §6 Phase D | §5 + §6 |
| §7 PLAN_CODE_AUDIT 15-item checklist | every row of the audit checklist maps to a § here |
| §8 Open implementation questions Q-PRM-1..8 | annotated in §2.1, §3.5, §3.7 (need plan-code audit to close them) |
| §9 Method alternates / pivot routes | §4 (H4-fallback) + § 5 ablation variants encode H3-H6 falsifiers |
| §10 Compute envelope | unchanged |

---

## 8. Document history

- **v1.0** — 2026-05-15. Phase 1 of `/experiment-bridge`. Authored against `METHOD_SPEC.md` v2.0 §§1–9 + `COMPONENT_BUNDLE_LADDER.md` rungs R0–R21.
- **v1.1** — 2026-05-15 STOP-B-1 consistency patch. R8 split into R8a (Outcome-GRPO-plain canonical) + R8b (Outcome-GRPO-guarded stronger). §6 baselines table updated.
- **v1.2** — 2026-05-20 (C2/C3/C4/C5/C7/C8). Mid-Phase-A method revision per `/proposal-revise` Round 1 (`refine-logs/REVISION_REPORT.md`): CVaR β=0 main + β=0.5 offline scoring sensitivity (C2); Tweedie ρ≥0.5 binary gate (C3); gradient-locality hot-standby probe added in §2.5 (C4); H5 tradeoff check ε ∈ {0, σ_WER} not "Pareto curve" (C5); curriculum DEV-only (C7); KL pre-registered abort threshold 5.0 nats (C8).
- **v1.2-restoration-note** — 2026-05-20T08:00Z. §2–§6 had been incorrectly stub-shrunk during agent-driven doc-cleanup; full pseudocode restored from conversation context per PI rollback: *"22 个 rung 的 pseudocode 提前 serialize 出来，是因为执行 agent 拿到的 context 可能不包含 ideation agent 的推理过程，必须把 final decision 落到磁盘"*. Lesson: AI-context doc durability ≠ git history; markdown body IS the audit trail.

---

## 2026-05-28 ETV Pivot Addendum (Round 3) — Early Trajectory Verifier formalization

### ETV symbols and conventions

- `c` — prompt (conditioning).
- `i ∈ {1, ..., N}` — candidate index within a BoN group for prompt `c` (default `N = 8`).
- `σ ∈ {0.9, 0.8, 0.7}` — early-σ checkpoint set (the σ at which intermediate Tweedie reconstructions are scored before final generation).
- `r_axis(â_{c,i,σ})` — axis-level reward of candidate `i`'s Tweedie-clean reconstruction at checkpoint σ. The "common robust-LCB" axis is the primary; auxiliary axes (`aesthetic_pq`, `CLAP semantic`, `lyric WER`, `MERT coherence`) are used only for ETV-c6 cross-metric validation.
- `r_final(a_{c,i})` — final reward of candidate `i` after full generation.
- `rank_σ(c, i)` — within-prompt rank of candidate `i` at checkpoint σ (1 = best).
- `T(c) ∈ {vocal, instrumental}` — prompt type.
- `V_σ(c, i)` — ETV score for candidate `i` at checkpoint σ; downstream pruning operates on these scores.

### ETV feature vector

For candidate `i` of prompt `c`:

```
features(c, i) =
  [ r_lcb(â_{c,i,0.9}),    r_lcb(â_{c,i,0.8}),    r_lcb(â_{c,i,0.7}),
    r_lcb(â_{c,i,0.7}) − r_lcb(â_{c,i,0.9}),                            # slope
    rank_0.9(c, i),         rank_0.8(c, i),         rank_0.7(c, i),
    T(c),                                                                # categorical
    # Optional auxiliary axes (drop in ablation):
    r_pq(â_{c,i,0.7}),      r_clap(â_{c,i,0.7}),    r_mert(â_{c,i,0.7}),
    # Optional uncertainty features (ablation):
    std_axes(â_{c,i,0.7}) over reward ensemble
  ]
```

All features are read from cached Track A candidate records — no GPU forward
pass is invoked at ETV training time.

### ETV model tiers

**E-R7 ETV-linear (logistic / linear regression baseline)**

```python
# Pointwise per-candidate regressor.
X = stack([features(c, i) for (c, i) in train_candidates])
y = stack([r_final(c, i)    for (c, i) in train_candidates])
model = Linear().fit(X, y)
V_sigma(c, i) = model.predict(features(c, i))
```

**E-R8 ETV-GBDT (pairwise ranker, PRIMARY)**

```python
# Within-prompt pairwise: for each prompt c, sample candidate pairs (i, j)
# with disagreement on r_final. Target: sign(r_final(c,i) − r_final(c,j)).
pairs = [(c, i, j, sign(r_final(c, i) − r_final(c, j)))
         for c in train_prompts
         for (i, j) in pairs_within_prompt(c)
         if r_final(c, i) != r_final(c, j)]
model = lightgbm.LGBMRanker(objective='lambdarank').fit(
            X_pairs, y_pairs, group=group_sizes)
V_sigma(c, i) = model.predict(features(c, i))
```

**E-R9 ETV-LambdaMART (listwise within-prompt ranker)**

```python
# Within-prompt listwise: each prompt is a query group; the loss is
# LambdaMART NDCG-based listwise ranking.
model = lightgbm.LGBMRanker(objective='lambdarank',
                            ndcg_at=[1, 2, 4]).fit(
            X_listwise, y_listwise, group=group_sizes_per_prompt)
V_sigma(c, i) = model.predict(features(c, i))
```

**E-R10 ETV-MLP (optional appendix)**

```python
# Small MLP on the same features; ablation only.
model = nn.Sequential(nn.Linear(F, 64), nn.ReLU(),
                      nn.Linear(64, 32),  nn.ReLU(),
                      nn.Linear(32, 1)).fit(X, y, epochs=50)
V_sigma(c, i) = model(features(c, i))
```

### Risk-controlled adaptive pruning (E-R11..E-R13)

Calibration step. Given a held-out calibration split:

```python
# For each candidate i in held-out prompt c, compute the conformity score
# = |V_sigma(c, i) − r_final(c, i)| / scale(c).  Sort across all candidates.
# Choose threshold tau_eps so that the empirical false-prune-rate of the
# final top-1 is ≤ eps:
sorted_scores = sorted(conformity_scores_for_held_out_candidates)
tau_eps = empirical_quantile(sorted_scores, 1 − eps_target)
```

Online pruning at inference time:

```python
def etv_rc_select(prompt_c, candidates, eps, sigma_set=[0.9, 0.7]):
    """Risk-controlled adaptive pruning."""
    kept = candidates
    for sigma in sigma_set:
        for cand in kept:
            cand.features = update_features(cand, sigma)
            cand.V_score = V_sigma(prompt_c, cand)
        kept = [cand for cand in kept
                if cand.V_score >= q_lower(kept_scores, eps)]
        if len(kept) <= 1:
            break
    # Final selection
    finalists = [generate_full(cand, prompt_c) for cand in kept]
    return argmax(finalists, key=r_final)
```

`q_lower(kept_scores, eps)` is the calibrated lower-tail quantile that
ensures `P(prune the eventual top-1) ≤ eps` on the held-out distribution.

### Adaptive compute allocation (E-R14, optional extension)

```python
def etv_adaptive_select(prompt_c, candidates, eps_lo=0.01, eps_hi=0.10):
    """
    confident bad  → prune
    uncertain      → continue to next sigma
    confident good → retain
    """
    kept = candidates
    for sigma in [0.9, 0.8, 0.7]:
        scored = [(cand, V_sigma(prompt_c, cand), uncertainty(cand)) for cand in kept]
        kept = []
        for cand, V_score, U in scored:
            if V_score < q_lower(scored_scores, eps_hi):
                continue  # confident bad — prune
            elif V_score > q_upper(scored_scores, 1 - eps_lo):
                kept.append(cand)  # confident good — retain
            else:
                kept.append(cand)  # uncertain — continue
        if len(kept) <= 1:
            break
    finalists = [generate_full(cand, prompt_c) for cand in kept]
    return argmax(finalists, key=r_final)
```

### Compute accounting

- ETV training (E-R7..E-R10) and risk calibration: ≤2 CPU-h total on cached features.
- ETV inference: O(N) per prompt, dominated by GBDT forward; negligible vs sampling cost.
- No GPU forward passes are introduced; the only GPU cost is the full BoN-8 sampling that already exists in Track A, plus the matched-compute reduced samplings for ETV evaluation.

### Linkage

- Feature definitions consume cached scores from `runs/early_tweedie_validation_512_bon8_20260527_full01/shard*/candidate_records.jsonl`.
- Schedule baselines (E-R3..E-R6) are taken verbatim from `EARLY_TWEEDIE_PRUNING_VALIDATION.md`.
- The R0–R21 M-PRM ladder above remains valid for the boundary-section RL evidence (`PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md`).

The full ETV pseudocode collection above is the runnable shape behind
METHOD_SPEC.md "Early Trajectory Verifier (ETV)" section.


---

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
