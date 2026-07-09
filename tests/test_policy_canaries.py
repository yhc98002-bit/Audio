"""Reward-harness invariance check via canary prompts (R3 hedge, 2026-05-19).

Tests that the reward harness gives EXPECTED LOW scores on adversarial /
degenerate inputs (silence, noise, single tone, reverse, loop, HF squeal,
speech only) and an ELEVATED score on a positive-control known-song prompt.
Failure mode: if any adversarial canary scores HIGH gate_r_lcb on base
ACE-Step OR scores significantly HIGHER on a trained RL policy vs base, the
reward stack has a "win-with-trash" exploit a future policy could discover.

This driver computes the **same** gate_r_lcb that compute_headroom_gate.py
consumes (via `mprm.rewards.robust_lcb.robust_lcb` under the live `gate_v1`
policy), so canary numbers are commensurable with M1a ledger values.

Usage:
    # Baseline calibration run on base ACE-Step:
    PYTHONPATH=src python tests/test_policy_canaries.py \
        --policy-name base_ace_step \
        --seeds 0,1,2 \
        --out tests/canary_baseline_results.json

    # Post-training run (after Phase C; LoRA loading is a Phase C TODO,
    # not implemented in this driver yet — see HEDGE_STRATEGIES.md R3(b)):
    PYTHONPATH=src python tests/test_policy_canaries.py \
        --policy-name rl_policy_v1 \
        --seeds 0,1,2 \
        --out tests/canary_rl_v1_results.json \
        --compare-against tests/canary_baseline_results.json

Outputs JSON with per-canary per-axis scores + gate_r_lcb + range violations.
If --compare-against is given, also reports delta vs prior + suspect-hack
alerts.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

CANARY_PROMPTS_PATH = Path("tests/canary_prompts.jsonl")
EXPECTED_RANGES_PATH = Path("tests/canary_expected_ranges.yaml")
GATE_POLICY_PATH = Path("configs/eval/gate_v1.yaml")
DEFAULT_OUT_DIR = Path("runs/canaries")

# Codex hedge alert threshold for "did a trained policy hack a canary?"
# Default = max(0.30, M1a r0_base SD ≈ 0.14) = 0.30. Override via --alert-delta.
DEFAULT_ALERT_DELTA = 0.30


def _setup_env() -> None:
    """Mirror launch_phase_a.sh env defaults, BUT only set when the local path
    actually exists. On a fresh box without pre-staged weights this falls back
    to the shim's network behaviour (which itself may fail, but at least it
    isn't silently pointing at a non-existent local dir)."""
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    src_root = Path.home() / "HDD_POOL" / "source"
    for env_var, sub in [
        ("LAION_CLAP_BERT_DIR",    "laion_clap_tokenizers/bert-base-uncased"),
        ("LAION_CLAP_ROBERTA_DIR", "laion_clap_tokenizers/roberta-base"),
        ("LAION_CLAP_BART_DIR",    "laion_clap_tokenizers/facebook--bart-base"),
        ("MERT_LOCAL_PATH",        "mert/MERT-v1-95M"),
    ]:
        p = src_root / sub
        if p.is_dir():
            os.environ.setdefault(env_var, str(p))
    ab = src_root / "audiobox_aesthetics/checkpoint.pt"
    if ab.is_file():
        os.environ.setdefault("AUDIOBOX_AES_CKPT", str(ab))


def _load_expected_ranges():
    import yaml
    if not EXPECTED_RANGES_PATH.exists():
        return {}
    return yaml.safe_load(EXPECTED_RANGES_PATH.read_text(encoding="utf-8")) or {}


def _load_gate_policy():
    """Load gate_v1.yaml exactly the way scripts/compute_headroom_gate.py does,
    so canary gate_r_lcb values are computed under the same policy that M1a
    finals were stamped with. Returns (policy_dict, gate_hash_str)."""
    import hashlib
    import json as _json
    import yaml
    raw = yaml.safe_load(GATE_POLICY_PATH.read_text(encoding="utf-8"))
    policy = raw["eval_policy"]
    canonical = _json.dumps(policy, sort_keys=True, separators=(",", ":"))
    policy_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return policy, policy_hash


def _check_range_violations(scores: dict, expected_entry: dict) -> list:
    """Compare actual scores against the expected ranges for one canary.
    Returns a list of (axis, kind, expected, actual) violation tuples."""
    if not expected_entry:
        return []
    exp = expected_entry.get("expected") or {}
    out = []
    for key, bound in exp.items():
        if key.endswith("_max"):
            axis = key[: -len("_max")]
            actual = scores.get(axis)
            if isinstance(actual, (int, float)) and actual > bound:
                out.append({"axis": axis, "kind": "exceeds_max",
                             "expected_max": bound, "actual": actual})
        elif key.endswith("_min"):
            axis = key[: -len("_min")]
            actual = scores.get(axis)
            if isinstance(actual, (int, float)) and actual < bound:
                out.append({"axis": axis, "kind": "below_min",
                             "expected_min": bound, "actual": actual})
        elif key.endswith("_range"):
            axis = key[: -len("_range")]
            actual = scores.get(axis)
            if isinstance(actual, (int, float)) and isinstance(bound, list) and len(bound) == 2:
                lo, hi = bound
                if actual < lo or actual > hi:
                    out.append({"axis": axis, "kind": "outside_range",
                                 "expected_range": [lo, hi], "actual": actual})
    return out


def _compare_canaries(current: list, prior: list, alert_delta: float) -> dict:
    """Delta + alert against a prior baseline run. gate_r_lcb axis is the
    primary alert dimension."""
    prior_by_id = {r["prompt_id"]: r for r in prior if "prompt_id" in r}
    summary = {"per_prompt": {}, "alerts": []}
    for cur in current:
        pid = cur.get("prompt_id")
        if pid not in prior_by_id:
            continue
        pri = prior_by_id[pid]
        delta = {}
        for axis, cur_val in (cur.get("scores_mean") or cur.get("scores") or {}).items():
            if not isinstance(cur_val, (int, float)):
                continue
            pri_val = (pri.get("scores_mean") or pri.get("scores") or {}).get(axis)
            if not isinstance(pri_val, (int, float)):
                continue
            d = cur_val - pri_val
            delta[axis] = {"current": cur_val, "prior": pri_val, "delta": d}
            if axis == "gate_r_lcb" and d > alert_delta:
                summary["alerts"].append(
                    f"  ALERT: {pid} gate_r_lcb rose by {d:+.3f} ({pri_val:.3f}→{cur_val:.3f}), "
                    f"exceeds alert_delta={alert_delta}. Suspect reward hack on canary input."
                )
        summary["per_prompt"][pid] = delta
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                       formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--policy-name", default="base_ace_step",
                          help="Label for this run.")
    parser.add_argument("--seeds", default="0,1,2",
                          help="Comma-separated seeds (default '0,1,2'; canary baseline must be ≥3 to estimate variance).")
    parser.add_argument("--out", default="tests/canary_results.json")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--compare-against", default=None,
                          help="Optional prior canary JSON for delta + hack alerting.")
    parser.add_argument("--alert-delta", type=float, default=DEFAULT_ALERT_DELTA,
                          help=f"Min Δgate_r_lcb on a canary to alert. Default {DEFAULT_ALERT_DELTA}.")
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()
    # NOTE: --lora-checkpoint removed per Codex review #7. Phase C will re-add
    # once LoRA-load is implemented in mprm.inference.ace_step.

    _setup_env()
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    if not seeds:
        print("ERROR: --seeds is empty", file=sys.stderr); return 2

    # Heavy imports after env vars set.
    from mprm.common.seeding import seed_everything
    from mprm.data.audio_io import save_audio
    from mprm.data.prompts import load_prompts
    from mprm.inference.ace_step import AceStepModel
    from mprm.rewards.audiobox import AudioboxReward
    from mprm.rewards.clap import ClapReward
    from mprm.rewards.mert import MertReward
    from mprm.rewards.perturbations import perturbation_set
    from mprm.rewards.probes import anti_hacking_probes, probe_floors
    from mprm.rewards.robust_lcb import robust_lcb
    from mprm.rewards.whisper_wer import WhisperWerReward

    if not CANARY_PROMPTS_PATH.exists():
        print(f"ERROR: canary prompts file missing: {CANARY_PROMPTS_PATH}", file=sys.stderr); return 2
    canaries = load_prompts(CANARY_PROMPTS_PATH)
    expected_ranges = _load_expected_ranges()
    gate_policy, gate_hash = _load_gate_policy()
    print(f"[canary] loaded {len(canaries)} canaries; gate_v1 hash={gate_hash[:12]}…; seeds={seeds}")

    out_dir = Path(args.out_dir) / args.policy_name
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[canary] loading model (device={args.device})...", flush=True)
    t0 = time.time()
    model = AceStepModel(checkpoint=None, device=args.device)
    print(f"[canary] model loaded in {time.time() - t0:.0f}s", flush=True)

    print(f"[canary] loading reward stack (axes: clap, audiobox×4, mert, whisper-wer)...", flush=True)
    t0 = time.time()
    rewards = [
        ClapReward(device=args.device),
        AudioboxReward(target_axis="PQ", device=args.device),
        AudioboxReward(target_axis="PC", device=args.device),
        AudioboxReward(target_axis="CE", device=args.device),
        AudioboxReward(target_axis="CU", device=args.device),
        MertReward(device=args.device),
        WhisperWerReward(device=args.device),
    ]
    clap_for_probes = rewards[0]
    perts = perturbation_set(list(gate_policy["perturbations"]))
    floors = probe_floors()
    lambda_probe = dict(gate_policy["lambda_probe"])
    beta_robust = float(gate_policy["beta_robust"])
    print(f"[canary] reward stack ready in {time.time() - t0:.0f}s", flush=True)

    results = []
    for c_idx, prompt in enumerate(canaries):
        canary_type = (prompt.metadata or {}).get("canary_type", "")
        is_reverse = canary_type == "reverse"
        print(f"\n[canary {c_idx + 1}/{len(canaries)}] {prompt.prompt_id} (type={canary_type})", flush=True)

        per_seed_scores = []
        for s_idx, seed in enumerate(seeds):
            seed_everything(seed)
            t_seed = time.time()
            try:
                sampled = model.sample(prompt, seed=seed)
            except Exception as e:  # noqa: BLE001
                print(f"  seed={seed} GEN_FAIL: {type(e).__name__}: {e}", flush=True)
                continue

            waveform = sampled.waveform
            if is_reverse:
                # Codex review #3: ACE-Step won't produce time-reversed audio
                # from a "play backwards" prompt — it just generates normal
                # music. Manually flip the time axis to actually test
                # reverse-invariance of the reward stack.
                waveform = waveform.flip(-1)
                print(f"  seed={seed} applied waveform.flip(-1) post-generation", flush=True)

            audio_path = out_dir / f"{prompt.prompt_id}_seed{seed}.wav"
            save_audio(audio_path, waveform, sampled.sample_rate)

            scores: dict = {}
            for rm in rewards:
                try:
                    s = rm.score(waveform, sampled.sample_rate, prompt)
                    scores[s.axis] = float(s.value)
                    if getattr(s, "raw", None):
                        for k, v in s.raw.items():
                            if isinstance(v, (int, float)):
                                scores[f"{s.axis}_raw_{k}"] = float(v)
                except Exception as e:  # noqa: BLE001
                    scores[f"{rm.__class__.__name__}_error"] = f"{type(e).__name__}: {e}"

            try:
                probe = anti_hacking_probes(waveform, sampled.sample_rate, prompt,
                                              clap=clap_for_probes)
                for k, v in (probe or {}).items():
                    if isinstance(v, (int, float)):
                        scores[f"probe_{k}"] = float(v)
            except Exception as e:  # noqa: BLE001
                scores["probe_error"] = f"{type(e).__name__}: {e}"

            # Codex review #1 BLOCKER fix: compute gate_r_lcb under live gate_v1
            # policy so canary numbers are commensurable with M1a ledger values.
            try:
                lcb = robust_lcb(waveform, sampled.sample_rate, prompt,
                                  reward_models=rewards,
                                  perturbations=perts,
                                  probe_scores=probe if isinstance(probe, dict) else {},
                                  lambda_probe=lambda_probe,
                                  probe_floors=floors,
                                  beta_robust=beta_robust)
                scores["gate_r_lcb"] = float(lcb.value)
                scores["gate_mean_cells"] = float(lcb.mean_cells)
                scores["gate_std_cells"] = float(lcb.std_cells)
                scores["gate_probe_penalty"] = float(lcb.probe_penalty)
            except Exception as e:  # noqa: BLE001
                scores["gate_r_lcb_error"] = f"{type(e).__name__}: {e}"

            per_seed_scores.append({"seed": seed, "audio_path": str(audio_path),
                                     "scores": scores, "elapsed_s": round(time.time() - t_seed, 1)})
            print(f"  seed={seed} gate_r_lcb={scores.get('gate_r_lcb', 'NA')!r} ({time.time()-t_seed:.0f}s)",
                  flush=True)

        if not per_seed_scores:
            results.append({"prompt_id": prompt.prompt_id, "canary_type": canary_type,
                            "error": "all seeds failed to generate"})
            continue

        # Aggregate across seeds: mean per axis (or single value if 1 seed).
        all_axes = set()
        for entry in per_seed_scores:
            all_axes.update(k for k, v in entry["scores"].items()
                             if isinstance(v, (int, float)))
        scores_mean = {}
        scores_sd = {}
        for axis in all_axes:
            vals = [entry["scores"][axis] for entry in per_seed_scores
                     if isinstance(entry["scores"].get(axis), (int, float))]
            if not vals:
                continue
            scores_mean[axis] = sum(vals) / len(vals)
            if len(vals) > 1:
                m = scores_mean[axis]
                scores_sd[axis] = (sum((v - m) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5

        expected_entry = expected_ranges.get(prompt.prompt_id, {}) or {}
        violations = _check_range_violations(scores_mean, expected_entry)

        results.append({
            "prompt_id": prompt.prompt_id,
            "text": prompt.text,
            "canary_type": canary_type,
            "is_positive_control": expected_entry.get("type") == "positive_control",
            "n_seeds": len(per_seed_scores),
            "scores_mean": scores_mean,
            "scores_sd": scores_sd,
            "per_seed": per_seed_scores,
            "range_violations": violations,
        })
        if violations:
            print(f"  RANGE_VIOLATIONS ({len(violations)}): " +
                    ", ".join(f"{v['axis']}={v['actual']:.3f}" for v in violations),
                    flush=True)
        else:
            print(f"  ranges OK", flush=True)

    payload = {
        "policy_name": args.policy_name,
        "seeds": seeds,
        "device": args.device,
        "gate_policy_hash": gate_hash,
        "n_canaries": len(canaries),
        "n_completed": sum(1 for r in results if "error" not in r),
        "n_with_violations": sum(1 for r in results if r.get("range_violations")),
        "alert_delta": args.alert_delta,
        "results": results,
        "ranges_status": "PROVISIONAL — tighten after baseline run; see tests/canary_expected_ranges.yaml header",
    }
    if args.compare_against:
        prior_path = Path(args.compare_against)
        if prior_path.exists():
            prior = json.loads(prior_path.read_text(encoding="utf-8"))
            payload["compare_against"] = str(prior_path)
            payload["compare_summary"] = _compare_canaries(
                results, prior.get("results", []), args.alert_delta
            )
        else:
            print(f"WARN: --compare-against {prior_path} missing", file=sys.stderr)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"\n[canary] wrote {out_path}", flush=True)
    print(f"[canary] completed={payload['n_completed']}/{len(canaries)} ; "
          f"with_violations={payload['n_with_violations']}", flush=True)
    return 0 if payload["n_completed"] == len(canaries) else 1


if __name__ == "__main__":
    sys.exit(main())
