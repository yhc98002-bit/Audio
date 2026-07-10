"""CLI entry point for any baseline R0-R9.

Usage:
    python scripts/launch_baseline.py --config configs/baselines/r0_base.yaml --split dev
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

# NOTE (STOP-B-5): heavy `mprm.*` imports are moved INSIDE main() so the M0.5 gate
# check runs BEFORE any torch import. Without this, the script crashes on torch
# import before the gate ever has a chance to fire, which made the gate untestable
# in CPU sandboxes and partially testable in production (the gate would fire only
# after torch loads, but the user-facing UX is the same).


# STOP-B-5: rungs that belong to M1a (R0..R4 + R9) or M1b (R5..R8b). Direct production
# launches of these rungs MUST come downstream of a successful M0.5 (D0–D5 + D3a + R050),
# or be explicitly PI-acknowledged via the M0_5_PI_ACK env var.
M1A_M1B_RUNGS: set[str] = {"R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8a", "R8b", "R9"}
M0_5_GATE_FLAG = Path("runs/M0_5_GATE_PASSED.flag")

# STOP-B-7: gate-critical M1a rungs (R3 is diagnostic-only, R8a/R8b are M1b
# scaffolds). These get gate_r_lcb computed under the uniform gate_v1 policy
# IN ADDITION TO their own per-rung r_lcb. compute_headroom_gate.py reads
# gate_r_lcb, not r_lcb. KEEP THIS IN SYNC with scripts/compute_headroom_gate.py.
GATE_CRITICAL_RUNG_IDS: frozenset[str] = frozenset({"R0", "R1", "R2", "R4", "R9"})
GATE_EVAL_POLICY_PATH = Path("configs/eval/gate_v1.yaml")

# STOP-B-6 peek-status sentinels (returned by _early_peek_rung_id alongside rung_id).
PEEK_OK = "ok"
PEEK_NO_YAML = "no_yaml"
PEEK_MISSING_FILE = "missing_file"
PEEK_MALFORMED = "malformed"
PEEK_NO_RUNG_ID = "no_rung_id"


def _copy_config_for_seed(cfg):
    """Return a fully isolated config for one seed.

    Config contains nested dataclasses and mutable ``baseline.extras``. A
    top-level constructor copy aliases those objects and lets one seed mutate
    the next seed's configuration.
    """
    return deepcopy(cfg)


def _early_peek_rung_id(config_path: Path) -> tuple[str | None, str]:
    """Parse just the rung_id from the YAML config — no mprm / torch imports.

    Used by the M0.5 gate check that must run BEFORE any heavy import.

    STOP-B-6: returns ``(rung_id, status)`` so callers can fail-closed in
    production mode when the peek itself was inconclusive. Previously this
    returned ``None`` for *every* failure mode (yaml missing, config missing,
    malformed yaml, rung_id absent), which falls through `_check_m0_5_gate`
    as "not in M1A_M1B_RUNGS → proceed" — i.e. a broken config could silently
    bypass the M0.5 gate.
    """
    try:
        import yaml
    except ImportError:
        return (None, PEEK_NO_YAML)
    if not config_path.exists():
        return (None, PEEK_MISSING_FILE)
    try:
        with config_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except Exception:  # noqa: BLE001
        return (None, PEEK_MALFORMED)
    if not isinstance(raw, dict):
        return (None, PEEK_MALFORMED)
    baseline = raw.get("baseline") or {}
    rid = baseline.get("rung_id")
    if not isinstance(rid, str) or not rid:
        return (None, PEEK_NO_RUNG_ID)
    return (rid, PEEK_OK)


def _check_m0_5_gate(peek: tuple[str | None, str], mode: str) -> int | None:
    """Return None to proceed, or a non-zero exit code to refuse the launch.

    STOP-B-5 fix #5b. Direct production launches of M1a/M1b rungs must be
    downstream of a successful M0.5 (runs/M0_5_GATE_PASSED.flag exists) or
    explicitly PI-acknowledged via M0_5_PI_ACK=1.

    STOP-B-6 fix #6: if the config peek failed in production mode the gate
    now fails closed by default — an unparseable config can never bypass
    M0.5 silently. M0_5_PI_ACK=1 still overrides (with a WARN), since the
    PI is taking explicit responsibility for the launch in that case.
    """
    rung_id, status = peek

    if mode == "production" and status != PEEK_OK:
        if os.environ.get("M0_5_PI_ACK") == "1":
            print(
                f"WARN (STOP-B-6): production launch with inconclusive config peek"
                f" (status={status}); M0_5_PI_ACK=1 is set, so proceeding under"
                " explicit PI-override. Record this in the decision log."
            )
            # Fall through to the rung_id check below; rung_id is None, which
            # means "no known M1a/M1b rung", so the rest of the gate is a no-op.
        else:
            print(
                f"BLOCK (STOP-B-6): production launch refused — could not determine"
                f" rung_id from config (peek status: {status}).\n"
                "  An unparseable, missing, or rung_id-less config cannot bypass the"
                " M0.5 gate in production. Fix the config, or set M0_5_PI_ACK=1 for"
                " an explicit PI override (recorded in the decision log)."
            )
            return 2

    if rung_id not in M1A_M1B_RUNGS or mode != "production":
        return None
    if not M0_5_GATE_FLAG.exists() and os.environ.get("M0_5_PI_ACK") != "1":
        print(
            f"BLOCK (STOP-B-5): {rung_id} is an M1a/M1b rung in production mode but"
            " the M0.5 gate has not passed.\n"
            f"  Required: {M0_5_GATE_FLAG} must exist (written by"
            " scripts/launch_phase_a.sh after D0-D5 + D3a + R050 complete).\n"
            "  To bypass for an explicit PI-acknowledged direct launch, set"
            " M0_5_PI_ACK=1 in the environment.\n"
            "  See orbit-research/PIPELINE_SUMMARY.md STOP-B-5 section for the"
            " gate contract and bypass discipline."
        )
        return 2
    if os.environ.get("M0_5_PI_ACK") == "1":
        print(
            "WARN (STOP-B-5): M0_5_PI_ACK=1 is set; bypassing the M0.5 gate flag check."
            " This direct launch is explicit PI-override; record it in the decision log."
        )
    return None


def _build_model(model_cfg):
    if model_cfg.backbone == "ace_step":
        from mprm.inference.ace_step import AceStepModel
        return AceStepModel(checkpoint="ace-step/ACE-Step-1.5")
    if model_cfg.backbone == "stable_audio_open":
        from mprm.inference.sao import StableAudioOpenModel
        return StableAudioOpenModel(checkpoint="stabilityai/stable-audio-open-1.0")
    raise ValueError(f"unknown backbone: {model_cfg.backbone}")


def _build_reward_models(reward_cfg):
    models = []
    if reward_cfg.use_clap:
        from mprm.rewards.clap import ClapReward
        models.append(ClapReward(variant=reward_cfg.clap_variant))
    if reward_cfg.use_audiobox:
        from mprm.rewards.audiobox import AudioboxReward
        for axis in ("PQ", "PC", "CE", "CU"):
            models.append(AudioboxReward(target_axis=axis))
    if reward_cfg.use_whisper:
        from mprm.rewards.whisper_wer import WhisperWerReward
        models.append(WhisperWerReward(model_size=reward_cfg.whisper_variant))
    if reward_cfg.use_mert:
        from mprm.rewards.mert import MertReward
        models.append(MertReward(model_name=reward_cfg.mert_variant))
    return models


def _build_baseline(cfg, model, reward_models):
    rid = cfg.baseline.rung_id
    extras = cfg.baseline.extras
    if rid == "R0":
        from mprm.baselines.r0_base import R0BaseSampling
        return R0BaseSampling(model, reward_models, cfg.baseline.output_dir,
                              cfg_scale=cfg.model.cfg_default,
                              inference_steps=cfg.model.inference_steps)
    if rid == "R1":
        from mprm.baselines.r1_cfg_sweep import R1CfgSweep
        return R1CfgSweep(model, reward_models, cfg.baseline.output_dir,
                          cfg_values=cfg.baseline.cfg_values or [],
                          inference_steps=cfg.model.inference_steps)
    if rid == "R2":
        from mprm.baselines.r2_bon import R2BoN
        return R2BoN(model, reward_models, cfg.baseline.output_dir,
                     n=cfg.baseline.bon_n or 8,
                     primary_axis=extras.get("primary_axis", "aesthetic_pq"),
                     cfg_scale=cfg.model.cfg_default,
                     inference_steps=cfg.model.inference_steps,
                     n_sweep=extras.get("n_sweep"))
    if rid == "R3":
        from mprm.baselines.r3_robust_bon import R3RobustBoN
        return R3RobustBoN(model, reward_models, cfg.baseline.output_dir,
                           n=cfg.baseline.bon_n or 8,
                           beta_robust=cfg.reward.beta_robust,
                           lambda_probe=cfg.reward.lambda_probe,
                           perturbation_names=extras.get("perturbations", ["identity"]),
                           cfg_scale=cfg.model.cfg_default,
                           inference_steps=cfg.model.inference_steps)
    if rid == "R4":
        from mprm.baselines.r4_bon_cfg import R4BoNCfg
        return R4BoNCfg(model, reward_models, cfg.baseline.output_dir,
                         n=cfg.baseline.bon_n or 8,
                         cfg_values=cfg.baseline.cfg_values or [],
                         primary_axis=extras.get("primary_axis", "aesthetic_pq"),
                         inference_steps=cfg.model.inference_steps)
    if rid == "R5":
        from mprm.baselines.r5_sft_on_best import R5SftOnBest
        return R5SftOnBest(model, reward_models, cfg.baseline.output_dir,
                           n=cfg.baseline.bon_n or 8,
                           primary_axis=extras.get("primary_axis", "aesthetic_pq"),
                           sft_steps=cfg.baseline.sft_steps or 1000,
                           lora_rank=cfg.baseline.lora_rank,
                           lr=cfg.baseline.learning_rate or 1e-5)
    if rid == "R6":
        from mprm.baselines.r6_robust_elite_sft import R6RobustEliteSft
        return R6RobustEliteSft(model, reward_models, cfg.baseline.output_dir,
                                 n_bon=cfg.baseline.bon_n or 8,
                                 beta_robust=cfg.reward.beta_robust,
                                 lambda_probe=cfg.reward.lambda_probe,
                                 perturbation_names=extras.get("perturbations", ["identity"]),
                                 elite_quantile=extras.get("elite_quantile", 0.25),
                                 sft_steps=cfg.baseline.sft_steps or 1500,
                                 lora_rank=cfg.baseline.lora_rank,
                                 lr=cfg.baseline.learning_rate or 1e-5,
                                 evaluator_disagreement_axis_pair=tuple(
                                     extras.get("evaluator_disagreement_axis_pair") or []
                                 ) or None)
    if rid == "R7":
        from mprm.baselines.r7_flow_dpo import R7FlowDpo
        return R7FlowDpo(model, reward_models, cfg.baseline.output_dir,
                          n_bon=cfg.baseline.bon_n or 8,
                          beta_dpo=extras.get("beta_dpo", 0.1),
                          beta_robust=cfg.reward.beta_robust,
                          lambda_probe=cfg.reward.lambda_probe,
                          perturbation_names=extras.get("perturbations", ["identity"]),
                          sft_steps=cfg.baseline.sft_steps or 1500,
                          lora_rank=cfg.baseline.lora_rank,
                          lr=cfg.baseline.learning_rate or 1e-6,
                          min_margin=extras.get("min_margin", 0.05))
    if rid in ("R8", "R8a", "R8b"):
        from mprm.baselines.r8_outcome_grpo import R8OutcomeGrpo
        # R8a (plain): epsilon_lyric=None and use_curriculum=false → guard + curriculum off.
        # R8b (guarded): epsilon_lyric=0.0 (or numeric) and use_curriculum=true → both on.
        # R8 (deprecated stub): the launch-mode guard above rejects this codepath.
        eps_lyric = extras.get("epsilon_lyric") if rid != "R8a" else None
        return R8OutcomeGrpo(model, reward_models, cfg.baseline.output_dir,
                              group_size=cfg.baseline.group_size or 4,
                              t_train=cfg.baseline.t_train or 5,
                              rl_steps=cfg.baseline.rl_steps or 2000,
                              lr=cfg.baseline.learning_rate or 1e-6,
                              lambda_kl=cfg.baseline.lambda_kl or 0.05,
                              epsilon_clip=cfg.baseline.epsilon_clip or 0.2,
                              eta_schedule=extras.get("eta_schedule"),
                              epsilon_lyric=eps_lyric,
                              lambda_init=extras.get("lambda_init", 0.5),
                              lambda_growth=extras.get("lambda_growth", 1.1),
                              lambda_decay=extras.get("lambda_decay", 0.95),
                              lambda_min=extras.get("lambda_min", 0.01),
                              lambda_max=extras.get("lambda_max", 5.0),
                              lyric_window=extras.get("lyric_window", 32),
                              beta_robust=cfg.reward.beta_robust,
                              lambda_probe=cfg.reward.lambda_probe,
                              perturbation_names=extras.get("perturbations", ["identity"]),
                              lora_rank=cfg.baseline.lora_rank)
    if rid == "R9":
        # STOP-B-8: R9-lite for M1a (upstream v1 public API exposes 3 of 4 original
        # sampler-control axes). Legacy ranges (eta_range / step_alloc_range /
        # neg_prompt_range) are accepted for back-compat but ignored with a WARN
        # by R9SamplerController. New ranges: omega_range, guidance_interval_range.
        from mprm.baselines.r9_s7_sampler_control import R9SamplerController, R9_MODE_LITE
        return R9SamplerController(model, reward_models, cfg.baseline.output_dir,
                                     search_budget=extras.get("search_budget", 100),
                                     cfg_range=tuple(extras.get("cfg_range", [1.5, 10.0])),
                                     omega_range=tuple(extras.get("omega_range", [5.0, 15.0])),
                                     guidance_interval_range=tuple(extras.get(
                                         "guidance_interval_range", [0.3, 0.7])),
                                     eta_range=tuple(extras["eta_range"])
                                         if "eta_range" in extras else None,
                                     step_alloc_range=tuple(extras["step_alloc_range"])
                                         if "step_alloc_range" in extras else None,
                                     neg_prompt_range=tuple(extras["neg_prompt_range"])
                                         if "neg_prompt_range" in extras else None,
                                     inference_steps=cfg.model.inference_steps,
                                     beta_robust=cfg.reward.beta_robust,
                                     lambda_probe=cfg.reward.lambda_probe,
                                     perturbation_names=extras.get("perturbations", ["identity"]),
                                     exploration_eps=extras.get("exploration_eps", 0.2),
                                     mode=extras.get("mode", R9_MODE_LITE))
    raise ValueError(f"unknown rung_id: {rid}")


def _attach_r_lcb(results, reward_models, perturbations_names, lambda_probe, beta_robust,
                    prompts_by_id, *, strict: bool = True):
    """Compute R_lcb per result and attach to metrics. Required so every gate-critical
    Phase A baseline emits `r_lcb` and `compute_headroom_gate.py` can consume them.

    STOP-B-6 fix #2: previously `load_audio` was referenced as a free name, but in
    this module the heavy `mprm.*` imports live inside `main()` (STOP-B-5), so the
    reference triggered NameError inside the surrounding `except Exception` and
    silently dropped `r_lcb` for every result — gate-critical Phase A would have
    produced empty `r_lcb` columns and `compute_headroom_gate.py` would either
    skip rungs or evaluate on nothing. We now import `load_audio` locally, remove
    the broad except that hid the bug, surface per-result errors, and assert in
    `strict=True` mode that every applicable result carries `r_lcb` before
    returning. Phase A is gate-critical, so strict is the default.

    STOP-B-6 fix #5: Phase A rungs are mostly NOT Best-of-N pairs against a shared
    Base (only R2/R3/R4 internally are), so there is no per-result `base_reference`
    waveform to pass to `hf_artifact_score` here. The probe therefore uses absolute
    HF energy (the default when `base_reference=None`). `compute_headroom_gate.py`
    compares R_lcb means ACROSS rungs, so probe consistency *within a rung* is
    what matters; the cross-rung comparison sees the same probe definition for
    each rung, so the comparison is fair. This is intentional — it is NOT the same
    as the R050 mini-probe, which explicitly compares Base-vs-BoN and so needs
    `base_reference=Base.waveform` to keep the metric symmetric.
    TODO (post-M1a): when adding per-rung base-vs-candidate audits (e.g. a Phase A.3
    head-to-head between R0 and R8a/R8b), plumb a per-rung
    `base_reference_by_prompt_id` map into `_attach_r_lcb` so the BoN-style probe
    is the same one R050 uses. Not needed for the M1a headroom gate.
    """
    from mprm.data.audio_io import load_audio
    from mprm.rewards.clap import ClapReward
    from mprm.rewards.perturbations import perturbation_set
    from mprm.rewards.probes import anti_hacking_probes, probe_floors
    from mprm.rewards.robust_lcb import robust_lcb
    clap = next((rm for rm in reward_models if isinstance(rm, ClapReward)), None)
    perts = perturbation_set(perturbations_names or ["identity"])
    floors = probe_floors()
    errors: list[str] = []
    # R9 HEDGE 2026-05-19: progress emit every 10 processed results. Previously
    # this loop was silent for 100+ min during M1a, making operator unable to
    # distinguish progress from stall. Currently-running subprocesses load the
    # old code and aren't affected; M1a held-out + Phase B onwards will see this.
    t_start_attach = time.time()
    total_attach = len(results)
    processed_attach = 0
    skipped_attach = 0
    print(f"[_attach_r_lcb] start: {total_attach} results to process", flush=True)
    for idx, r in enumerate(results):
        if r.waveform_path is None:
            skipped_attach += 1
            continue
        if "r_lcb" in r.metrics:
            skipped_attach += 1
            continue
        try:
            waveform, sr = load_audio(r.waveform_path)
        except Exception as e:  # noqa: BLE001
            msg = (f"_attach_r_lcb: load_audio failed for {r.prompt_id}"
                   f" path={r.waveform_path} ({type(e).__name__}: {e})")
            if strict:
                raise RuntimeError(msg) from e
            print(f"WARN: {msg}")
            errors.append(msg)
            continue
        prompt = prompts_by_id.get(r.prompt_id)
        if prompt is None:
            msg = f"_attach_r_lcb: no prompt object in prompts_by_id for {r.prompt_id}"
            if strict:
                raise RuntimeError(msg)
            print(f"WARN: {msg}")
            errors.append(msg)
            continue
        probe = anti_hacking_probes(waveform, sr, prompt, clap=clap)
        lcb = robust_lcb(waveform, sr, prompt,
                          reward_models=reward_models,
                          perturbations=perts,
                          probe_scores=probe,
                          lambda_probe=lambda_probe,
                          probe_floors=floors,
                          beta_robust=beta_robust)
        r.metrics["r_lcb"] = lcb.value
        r.metrics["mean_cells"] = lcb.mean_cells
        r.metrics["std_cells"] = lcb.std_cells
        r.metrics["probe_penalty"] = lcb.probe_penalty
        processed_attach += 1
        if processed_attach % 10 == 0:
            elapsed = time.time() - t_start_attach
            rate = processed_attach / elapsed if elapsed > 0 else 0.0
            remaining = (total_attach - (idx + 1)) / rate if rate > 0 else 0.0
            print(f"[_attach_r_lcb] {processed_attach} processed (idx {idx + 1}/{total_attach}, "
                  f"{elapsed:.0f}s elapsed, {rate:.2f}/s, ETA {remaining:.0f}s)",
                  flush=True)
    elapsed_final = time.time() - t_start_attach
    print(f"[_attach_r_lcb] done: processed={processed_attach} skipped={skipped_attach} "
          f"errors={len(errors)} in {elapsed_final:.0f}s", flush=True)

    # Gate-critical post-condition: every applicable result must carry `r_lcb`.
    # Without this, compute_headroom_gate would see missing keys and either skip
    # the rung or evaluate on incomplete data — both silent failures.
    missing = [r.prompt_id for r in results
               if r.waveform_path is not None and "r_lcb" not in r.metrics]
    if missing:
        msg = (f"_attach_r_lcb post-condition FAIL: r_lcb missing on {len(missing)}"
               f" of {len(results)} results (first few: {missing[:5]});"
               f" earlier errors: {errors[:5]}")
        if strict:
            raise RuntimeError(msg)
        print(f"WARN: {msg}")
    return results


# ============================================================================
# STOP-B-7: uniform gate_v1 evaluator for the M1a headroom gate.
# ============================================================================


def load_gate_eval_policy(path: Path | str = GATE_EVAL_POLICY_PATH) -> tuple[dict, str]:
    """Load configs/eval/gate_v1.yaml; return (policy_dict, policy_hash).

    The policy hash is sha256 of the canonical-JSON serialization of just the
    `eval_policy` block, so yaml whitespace/comment changes don't change the
    hash. Imported by `compute_headroom_gate.py` for provenance verification.

    STOP-B-7.1 Q1/Q2/Q4: schema validation is stricter — required keys must
    exist; lambda_probe values must be finite floats; perturbations must be a
    non-empty list of strings; beta_robust must be a finite float;
    reward_axes (added in v1.1) must be a list of strings.
    """
    import hashlib
    import json as _json
    import math
    import yaml
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict) or "eval_policy" not in raw:
        raise ValueError(f"{path}: missing top-level `eval_policy` key.")
    policy = raw["eval_policy"]
    # Required keys.
    for key in ("name", "version", "lambda_probe", "perturbations", "beta_robust",
                "reward_axes"):
        if key not in policy:
            raise ValueError(f"{path}: eval_policy missing required key '{key}'.")
    # Type + finite-float validation (STOP-B-7.2: reject bool — `isinstance(True, int)`
    # is True in Python, so we exclude bool explicitly; require non-empty lambda_probe).
    if not isinstance(policy["lambda_probe"], dict) or not policy["lambda_probe"]:
        raise ValueError(f"{path}: eval_policy.lambda_probe must be a non-empty dict.")
    for k, v in policy["lambda_probe"].items():
        if not isinstance(k, str):
            raise ValueError(f"{path}: lambda_probe key {k!r} must be a string.")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
            raise ValueError(f"{path}: lambda_probe[{k!r}] must be a finite real number,"
                             f" got {v!r} of type {type(v).__name__}.")
    if not isinstance(policy["perturbations"], list) or not policy["perturbations"]:
        raise ValueError(f"{path}: eval_policy.perturbations must be a non-empty list.")
    for p in policy["perturbations"]:
        if not isinstance(p, str):
            raise ValueError(f"{path}: perturbation entries must be strings, got {p!r}.")
    if (isinstance(policy["beta_robust"], bool)
            or not isinstance(policy["beta_robust"], (int, float))
            or not math.isfinite(float(policy["beta_robust"]))):
        raise ValueError(f"{path}: eval_policy.beta_robust must be a finite real number,"
                         f" got {policy['beta_robust']!r}.")
    if not isinstance(policy["reward_axes"], list) or not policy["reward_axes"]:
        raise ValueError(f"{path}: eval_policy.reward_axes must be a non-empty list.")
    for ax in policy["reward_axes"]:
        if not isinstance(ax, str):
            raise ValueError(f"{path}: reward_axes entries must be strings, got {ax!r}.")
    canonical = _json.dumps(policy, sort_keys=True, separators=(",", ":"))
    policy_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return policy, policy_hash


def _assert_reward_axes_match_policy(reward_models, policy: dict) -> None:
    """STOP-B-7.1 Q4 + STOP-B-7.2: assert the rung's runtime reward_models
    set matches `gate_v1.reward_axes` EXACTLY (including multiplicities).

    Counter-based comparison catches duplicate model instances (e.g. two
    ClapReward objects with axis="semantic_fit") that a set() would silently
    dedup but `robust_lcb`'s cell_values would still double-count.
    """
    from collections import Counter
    expected_axes = list(policy.get("reward_axes") or [])
    if not expected_axes:
        return
    actual_axes = [getattr(rm, "axis", "<unknown>") for rm in reward_models]
    expected_counter = Counter(expected_axes)
    actual_counter = Counter(actual_axes)
    if expected_counter != actual_counter:
        # Build human-readable diff.
        only_expected = expected_counter - actual_counter
        only_actual = actual_counter - expected_counter
        raise RuntimeError(
            "STOP-B-7.1 gate-policy commensurability check FAILED: rung's"
            " reward_models do not match gate_v1.reward_axes (Counter-equality).\n"
            f"  expected (gate_v1): {sorted(expected_counter.elements())}\n"
            f"  actual   (runtime): {sorted(actual_counter.elements())}\n"
            f"  missing from runtime: {dict(only_expected)}\n"
            f"  extra in runtime:    {dict(only_actual)}\n"
            "  Fix: align the rung's `reward` config with gate_v1.yaml's"
            " `reward_axes` block, or bump to gate_v2.\n"
            "  STOP-B-7.2: duplicate axes (Counter > 1) also fail this check."
        )


def gate_eval_policy_provenance(policy: dict, policy_hash: str) -> dict:
    """The provenance block stamped onto each result's `extras` and onto the
    per-rung sidecar. STOP-B-7.1 Q3: includes the FULL active policy content
    (lambda_probe + perturbations + beta_robust + reward_axes) so the
    sidecar can be verified field-by-field, not just by claimed hash.
    """
    return {
        "name": policy["name"],
        "version": policy["version"],
        "hash": policy_hash,
        "lambda_probe": dict(policy["lambda_probe"]),
        "perturbations": list(policy["perturbations"]),
        "beta_robust": float(policy["beta_robust"]),
        "reward_axes": list(policy.get("reward_axes") or []),
    }


def _attach_gate_r_lcb(results, reward_models, prompts_by_id, policy: dict,
                         policy_hash: str, *, strict: bool = True):
    """Compute `gate_r_lcb` under the uniform gate_v1 policy for every applicable
    result. Distinct from `_attach_r_lcb` — gate_r_lcb does NOT use the per-rung
    cfg.reward.lambda_probe / perturbations; it uses gate_v1's policy, which is
    identical across all gate-critical rungs. This is what makes the cross-rung
    comparison in `compute_headroom_gate.py` legitimate.

    The per-rung `r_lcb` stays in place for its training/selection role. Both
    metrics coexist on the same result.
    """
    # STOP-B-7.1 Q4 + STOP-B-7.2: assert the reward-model set matches
    # gate_v1's locked axes BEFORE any heavy import. STOP-B-7.2 uses Counter
    # rather than set() so DUPLICATE reward instances (e.g. two CLAP models)
    # are caught — `robust_lcb` would still include duplicates in cell_values
    # while per-axis maps overwrite by axis, biasing the gate.
    _assert_reward_axes_match_policy(reward_models, policy)

    from mprm.data.audio_io import load_audio
    from mprm.rewards.clap import ClapReward
    from mprm.rewards.perturbations import perturbation_set
    from mprm.rewards.probes import anti_hacking_probes, probe_floors
    from mprm.rewards.robust_lcb import robust_lcb

    clap = next((rm for rm in reward_models if isinstance(rm, ClapReward)), None)
    perts = perturbation_set(list(policy["perturbations"]))
    floors = probe_floors()
    lambda_probe = dict(policy["lambda_probe"])
    beta_robust = float(policy["beta_robust"])
    provenance = gate_eval_policy_provenance(policy, policy_hash)
    errors: list[str] = []
    # R9 HEDGE 2026-05-19: progress emit every 10 processed results. See
    # _attach_r_lcb docstring above. M1a held-out subprocesses + Phase B+
    # will pick this up; currently-running dev subprocesses won't.
    t_start_gate = time.time()
    total_gate = len(results)
    processed_gate = 0
    skipped_gate = 0
    print(f"[_attach_gate_r_lcb] start: {total_gate} results to process under gate policy"
          f" {policy.get('name','?')} v{policy.get('version','?')} hash={policy_hash[:12]}…",
          flush=True)
    for idx, r in enumerate(results):
        if r.waveform_path is None:
            skipped_gate += 1
            continue
        if "gate_r_lcb" in r.metrics:
            skipped_gate += 1
            continue
        try:
            waveform, sr = load_audio(r.waveform_path)
        except Exception as e:  # noqa: BLE001
            msg = (f"_attach_gate_r_lcb: load_audio failed for {r.prompt_id}"
                   f" path={r.waveform_path} ({type(e).__name__}: {e})")
            if strict:
                raise RuntimeError(msg) from e
            print(f"WARN: {msg}")
            errors.append(msg)
            continue
        prompt = prompts_by_id.get(r.prompt_id)
        if prompt is None:
            msg = f"_attach_gate_r_lcb: no prompt object in prompts_by_id for {r.prompt_id}"
            if strict:
                raise RuntimeError(msg)
            print(f"WARN: {msg}")
            errors.append(msg)
            continue
        probe = anti_hacking_probes(waveform, sr, prompt, clap=clap)
        lcb = robust_lcb(waveform, sr, prompt,
                          reward_models=reward_models,
                          perturbations=perts,
                          probe_scores=probe,
                          lambda_probe=lambda_probe,
                          probe_floors=floors,
                          beta_robust=beta_robust)
        r.metrics["gate_r_lcb"] = lcb.value
        r.metrics["gate_mean_cells"] = lcb.mean_cells
        r.metrics["gate_std_cells"] = lcb.std_cells
        r.metrics["gate_probe_penalty"] = lcb.probe_penalty
        # Stamp provenance on each result so a later auditor reading a single
        # line of results.jsonl can verify the gate policy without consulting
        # the sidecar.
        if not isinstance(getattr(r, "extras", None), dict):
            r.extras = {}
        r.extras["gate_eval_policy"] = provenance
        processed_gate += 1
        if processed_gate % 10 == 0:
            elapsed = time.time() - t_start_gate
            rate = processed_gate / elapsed if elapsed > 0 else 0.0
            remaining = (total_gate - (idx + 1)) / rate if rate > 0 else 0.0
            print(f"[_attach_gate_r_lcb] {processed_gate} processed (idx {idx + 1}/{total_gate}, "
                  f"{elapsed:.0f}s elapsed, {rate:.2f}/s, ETA {remaining:.0f}s)",
                  flush=True)
    elapsed_final_gate = time.time() - t_start_gate
    print(f"[_attach_gate_r_lcb] done: processed={processed_gate} skipped={skipped_gate} "
          f"errors={len(errors)} in {elapsed_final_gate:.0f}s", flush=True)

    missing = [r.prompt_id for r in results
               if r.waveform_path is not None and "gate_r_lcb" not in r.metrics]
    if missing:
        msg = (f"_attach_gate_r_lcb post-condition FAIL: gate_r_lcb missing on"
               f" {len(missing)} of {len(results)} results"
               f" (first few: {missing[:5]}); earlier errors: {errors[:5]}")
        if strict:
            raise RuntimeError(msg)
        print(f"WARN: {msg}")
    return results


def _write_gate_eval_policy_sidecar(out_dir: Path, policy: dict, policy_hash: str) -> Path:
    """Write a per-rung-split sidecar JSON capturing the gate policy provenance.

    Read by `compute_headroom_gate.py` so it can refuse to evaluate if any rung
    used a different gate policy hash. Cheaper than re-parsing every result line
    on every gate invocation.
    """
    import json as _json
    sidecar = out_dir / "gate_eval_policy.json"
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(
        _json.dumps(gate_eval_policy_provenance(policy, policy_hash), indent=2),
        encoding="utf-8",
    )
    return sidecar


def _check_prompt_flag(prompts_path: Path) -> str | None:
    flag = prompts_path.parent / "MISSING_REAL_PROMPTS.flag"
    if flag.exists():
        return (
            f"prompts at {prompts_path} are TEMPLATE STUBS (flag: {flag}). "
            "Populate real lyrics/text and delete the flag before Wave W2."
        )
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--split", default=None, help="override config.split")
    parser.add_argument("--prompts", default=None, help="override config.baseline.prompts_path")
    parser.add_argument("--limit", type=int, default=None, help="limit number of prompts (for smoke)")
    parser.add_argument("--seeds", default=None, help="comma-separated seed list; overrides config")
    parser.add_argument("--mode", choices=["dev", "production"], default="dev",
                        help="dev=allow stubs; production=enforce all blocking checks")
    args = parser.parse_args()

    # STOP-B-5 fix #5b + STOP-B-6 fix #6: M0.5 gate check runs FIRST, before any
    # heavy import. The peek now returns (rung_id, status); production launches
    # fail closed if the peek itself was inconclusive (missing pyyaml, missing
    # config, malformed yaml, no rung_id).
    peek = _early_peek_rung_id(Path(args.config))
    early_exit = _check_m0_5_gate(peek, args.mode)
    if early_exit is not None:
        return early_exit

    # Now the heavy imports (after the early gate has cleared).
    # `load_audio` is imported locally inside _attach_r_lcb (STOP-B-6 fix #2) —
    # do NOT re-import here, the local import is the contract.
    from mprm.common.config import load_config
    from mprm.common.provenance import collect_run_provenance
    from mprm.common.run_ledger import RunLedger
    from mprm.common.seeding import seed_everything
    from mprm.data.prompts import load_prompts
    from mprm.eval.parsers import save_baseline_results, summarize_baseline

    cfg = load_config(args.config)
    run_provenance = collect_run_provenance(args.config, cfg.model, Path(__file__).parents[1])
    split = args.split if args.split is not None else cfg.split
    cfg = cfg.__class__(**{**cfg.__dict__, "split": split})

    prompts_path = Path(args.prompts) if args.prompts else Path(cfg.baseline.prompts_path)
    flag_msg = _check_prompt_flag(prompts_path)
    if flag_msg and args.mode == "production":
        print(f"BLOCK: {flag_msg}")
        return 2
    if flag_msg:
        print(f"WARN (dev mode): {flag_msg}")

    if cfg.baseline.rung_id == "R8":
        print(
            "BLOCK: 'R8' (single Outcome-GRPO) is DEPRECATED by the STOP-B-1 split. Use one of:\n"
            "  configs/baselines/r8a_outcome_grpo_plain.yaml    (canonical terminal control)\n"
            "  configs/baselines/r8b_outcome_grpo_guarded.yaml  (stronger terminal control)"
        )
        return 2

    # STOP-B-7.1 Q5: R3 is diagnostic-only (reward-hackability). Warn loudly
    # if someone manually launches R3 on held-out — its results MUST NOT feed
    # the H1 headroom gate, and gate_r_lcb will not be stamped on this run.
    if cfg.baseline.rung_id == "R3" and split == "held_out":
        print(
            "WARN (STOP-B-7.1): R3 (Robust BoN) is DIAGNOSTIC-ONLY for"
            " reward-hackability and is NOT a gate-critical M1a rung. Running R3"
            " on held_out is unusual — `compute_headroom_gate.py` ignores R3 by"
            " design, and `gate_r_lcb` will not be computed for this run."
            " Continue only if you are running a separate reward-hackability"
            " audit, not the H1 headroom gate."
        )
    if cfg.baseline.rung_id in ("R8a", "R8b") and args.mode == "production":
        print(
            f"BLOCK: {cfg.baseline.rung_id} is registered as a scaffold; the full GRPO loss/ratio"
            " path is DEFERRED to the next /experiment-bridge call. Pass --mode dev to exercise"
            " the sampling-only call path, or wait for the next bridge to enable production"
            " R8a/R8b."
        )
        return 2

    # M0.5 gate (STOP-B-5 fix #5b) was already enforced at the top of main() via
    # `_early_peek_rung_id` + `_check_m0_5_gate`. The early check uses a pyyaml-only
    # peek so it runs before any torch import. By the time we reach this point the
    # rung is allowed.

    seeds = [int(s) for s in args.seeds.split(",")] if args.seeds else (
        cfg.baseline.extras.get("seeds") if isinstance(cfg.baseline.extras, dict) else None
    ) or [cfg.baseline.seed]

    prompts = load_prompts(prompts_path)
    if args.limit:
        prompts = prompts[: args.limit]
    print(f"Loaded {len(prompts)} prompts from {prompts_path}; seeds={seeds}; split={split}")

    ledger = RunLedger(cfg.run_ledger_path)

    prompts_by_id = {p.prompt_id: p for p in prompts}
    extras_cfg = cfg.baseline.extras if isinstance(cfg.baseline.extras, dict) else {}
    perturbation_names = extras_cfg.get("perturbations") or ["identity", "crop"]
    overall_summary: dict[int, dict] = {}
    aggregate_out = Path(cfg.baseline.output_dir) / split / "results.jsonl"
    aggregate_out.parent.mkdir(parents=True, exist_ok=True)
    aggregate_results: list = []

    # STOP-B-7: gate_v1 policy is loaded once per launch. For gate-critical M1a
    # rungs (R0/R1/R2/R4/R9), every result gets `gate_r_lcb` under this uniform
    # policy *in addition to* the per-rung `r_lcb`. `compute_headroom_gate.py`
    # reads `gate_r_lcb`, not `r_lcb`.
    gate_policy: dict | None = None
    gate_policy_hash: str | None = None
    rid = cfg.baseline.rung_id
    compute_gate = (rid in GATE_CRITICAL_RUNG_IDS and args.mode == "production"
                    and os.environ.get("SKIP_GATE_R_LCB") != "1")
    if compute_gate:
        gate_policy, gate_policy_hash = load_gate_eval_policy()
        print(f"STOP-B-7: rung {rid} is gate-critical;"
              f" will compute gate_r_lcb under {gate_policy['name']}"
              f" v{gate_policy['version']} (hash {gate_policy_hash[:12]}…).")
    elif rid in GATE_CRITICAL_RUNG_IDS:
        why = ("--mode=dev" if args.mode != "production" else "SKIP_GATE_R_LCB=1")
        print(f"WARN (STOP-B-7): rung {rid} is gate-critical but gate_r_lcb is"
              f" SKIPPED ({why}). compute_headroom_gate will refuse this run as"
              " gate-critical input.")
    try:
        import torch
        gpu_count = torch.cuda.device_count() if torch.cuda.is_available() else 0
    except Exception:  # noqa: BLE001
        gpu_count = 0

    for seed in seeds:
        seed_everything(seed)
        per_seed_cfg = _copy_config_for_seed(cfg)
        per_seed_cfg.baseline.seed = seed
        per_seed_cfg.baseline.output_dir = str(Path(cfg.baseline.output_dir) / split / f"seed{seed}")
        ledger.start(run_id=f"{cfg.run_id}-seed{seed}", rung_id=cfg.baseline.rung_id,
                     stage="phase_a", split=split, seed=seed, gpu_count=gpu_count,
                     **run_provenance)
        t0 = time.time()
        try:
            model = _build_model(cfg.model)
            reward_models = _build_reward_models(cfg.reward)
            # STOP-B-7.2 Q4: assert the reward set matches gate_v1.reward_axes
            # BEFORE the baseline runs (otherwise we'd waste a full sweep before
            # _attach_gate_r_lcb caught the mismatch).
            if compute_gate:
                assert gate_policy is not None
                _assert_reward_axes_match_policy(reward_models, gate_policy)
            baseline = _build_baseline(per_seed_cfg, model, reward_models)
            rid = cfg.baseline.rung_id
            if rid == "R5":
                baseline.collect_elites(prompts, seed=seed)
                baseline.fit(prompts)
            elif rid == "R6":
                baseline.fit(prompts, seed=seed)
            elif rid == "R7":
                baseline.build_preference_pairs(prompts, seed=seed)
                baseline.fit(prompts)
            elif rid in ("R8a", "R8b"):
                # R8 is hard-blocked above (DEPRECATED stub). R8a / R8b both train.
                baseline.fit(prompts, seed=seed)
            elif rid == "R9":
                baseline.search(prompts, seed=seed)
            results = baseline.run_on_set(prompts, seed=seed)
            # Phase A: every result must carry r_lcb so each rung's training/selection
            # downstream (BoN best-pick, elite SFT, etc.) can consume it.
            results = _attach_r_lcb(results, reward_models, perturbation_names,
                                      cfg.reward.lambda_probe, cfg.reward.beta_robust,
                                      prompts_by_id)
            # STOP-B-7: gate-critical rungs also get gate_r_lcb under the uniform
            # gate_v1 policy. The per-rung r_lcb above is still computed because
            # different rungs use it internally (e.g. R2/R4 for BoN best-pick).
            if compute_gate:
                assert gate_policy is not None and gate_policy_hash is not None
                results = _attach_gate_r_lcb(results, reward_models, prompts_by_id,
                                              gate_policy, gate_policy_hash)
            out_path = Path(per_seed_cfg.baseline.output_dir) / "results.jsonl"
            save_baseline_results(results, out_path)
            aggregate_results.extend(results)
            summary = summarize_baseline(results)
            overall_summary[seed] = summary
            elapsed = time.time() - t0
            ledger.final(run_id=f"{cfg.run_id}-seed{seed}", rung_id=cfg.baseline.rung_id,
                         stage="phase_a", split=split, seed=seed,
                         gpu_count=gpu_count, elapsed_seconds=elapsed,
                         metrics={k: v["mean"] for k, v in summary.items()},
                         notes=f"wrote {len(results)} results to {out_path}")
            print(f"Seed {seed}: wrote {len(results)} results to {out_path}"
                  f" (elapsed {elapsed:.1f}s on {gpu_count} GPU)")
        except Exception as e:  # noqa: BLE001
            ledger.fail(run_id=f"{cfg.run_id}-seed{seed}", rung_id=cfg.baseline.rung_id,
                        stage="phase_a", error=str(e))
            print(f"Seed {seed} FAIL: {type(e).__name__}: {e}")
            return 1

    # Write split-level aggregate that compute_headroom_gate.py consumes.
    save_baseline_results(aggregate_results, aggregate_out)
    print(f"\nAggregated {len(aggregate_results)} results across seeds -> {aggregate_out}")
    print("=== summary across seeds ===")
    print(json.dumps(overall_summary, indent=2))

    # STOP-B-7: write the gate-policy sidecar so compute_headroom_gate.py can
    # verify uniformity across rungs in O(1) without re-parsing every JSONL line.
    if compute_gate:
        assert gate_policy is not None and gate_policy_hash is not None
        sidecar = _write_gate_eval_policy_sidecar(
            aggregate_out.parent, gate_policy, gate_policy_hash
        )
        print(f"STOP-B-7: wrote gate-eval-policy sidecar to {sidecar}"
              f" (hash {gate_policy_hash[:12]}…).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
