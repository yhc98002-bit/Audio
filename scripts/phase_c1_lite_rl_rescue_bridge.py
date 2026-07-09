"""CPU-only materializer for Phase C1-lite RL rescue review bundles.

This script deliberately does not launch smoke or train jobs. It only validates
the review config and writes first-wave-compatible YAML bundles plus a derived
32-prompt manifest under an audit/artifact directory.
"""
from __future__ import annotations

import argparse
import copy
import json
import time
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REVIEW_CONFIG = "configs/runs/phase_c1_lite_rl_rescue_triage.review.yaml"
DEFAULT_BASE_CONFIG = "configs/runs/phase_c1_firstwave.yaml"
DEFAULT_ARTIFACTS_DIR = "orbit-research/codex-imports"
METHODS = ("r8a", "r8b", "m_fixedwin", "m_section")
ALLOWED_BACKEND_OVERRIDES = {
    "learning_rate",
    "advantage_gain",
    "log_post_update_diagnostics",
    "track_adapter_norm_delta",
}


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise RuntimeError(f"YAML root is not an object: {path}")
    return data


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path)


def _get_path(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        cur = cur[part]
    return cur


def _set_path(data: dict[str, Any], dotted: str, value: Any) -> None:
    cur: Any = data
    parts = dotted.split(".")
    for part in parts[:-1]:
        cur = cur[part]
    cur[parts[-1]] = value


def _diff_paths(before: dict[str, Any], after: dict[str, Any], prefix: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    keys = sorted(set(before) | set(after))
    for key in keys:
        path = f"{prefix}.{key}" if prefix else key
        if key not in before:
            rows.append({"path": path, "old": None, "new": after[key], "change": "added"})
            continue
        if key not in after:
            rows.append({"path": path, "old": before[key], "new": None, "change": "removed"})
            continue
        bval = before[key]
        aval = after[key]
        if isinstance(bval, dict) and isinstance(aval, dict):
            rows.extend(_diff_paths(bval, aval, path))
        elif bval != aval:
            rows.append({"path": path, "old": bval, "new": aval, "change": "modified"})
    return rows


def _load_formal_prompt_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"prompt manifest root is not an object: {path}")
    if data.get("source_split") != "configs/prompts/dev.jsonl":
        raise RuntimeError("formal prompt manifest source_split must be configs/prompts/dev.jsonl")
    if data.get("pi_approved") is not True:
        raise RuntimeError("formal prompt manifest must be PI-approved")
    prompt_ids = data.get("formal_prompt_ids")
    if not isinstance(prompt_ids, list) or not all(isinstance(x, str) for x in prompt_ids):
        raise RuntimeError("formal_prompt_ids must be a list of strings")
    if int(data.get("n_formal_prompts", -1)) != len(prompt_ids):
        raise RuntimeError("n_formal_prompts mismatch in source prompt manifest")
    return data


def _validate_review_config(review: dict[str, Any], base: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            raise RuntimeError(f"validation failed: {name}: {detail}")

    check(
        "review_schema",
        review.get("schema_version") == "phase_c1_lite_rl_rescue_triage_review_v1",
        str(review.get("schema_version")),
    )
    check(
        "review_non_launchable",
        review.get("status") == "review_only_not_launchable",
        str(review.get("status")),
    )
    scope = review.get("scope", {})
    check("dev_split", scope.get("split") == "dev", str(scope.get("split")))
    check(
        "prompt_source",
        scope.get("prompt_source") == "configs/prompts/dev.jsonl",
        str(scope.get("prompt_source")),
    )
    check("n_prompts_32", int(scope.get("n_prompts", -1)) == 32, str(scope.get("n_prompts")))
    for key in ("held_out_launched", "phase_d_launched", "human_eval_launched"):
        check(f"scope_{key}_false", scope.get(key) is False, str(scope.get(key)))

    safety = review.get("safety", {})
    check("hard_cap_40", float(safety.get("hard_cap_gpu_h", -1.0)) == 40.0, str(safety.get("hard_cap_gpu_h")))
    check(
        "max_steps_lte_250",
        int(safety.get("max_steps_per_setting", 999999)) <= 250,
        str(safety.get("max_steps_per_setting")),
    )
    do_not_modify = set(safety.get("do_not_modify", []))
    for protected in (
        "configs/eval/gate_v1.yaml",
        "configs/eval/gate_v2.yaml.draft",
        "runs/phase_c1_firstwave_20260524_researcher_go_01",
    ):
        check(f"protected_{protected}", protected in do_not_modify, ",".join(sorted(do_not_modify)))
    forbidden_launches = safety.get("forbidden_launches", {})
    for key in ("held_out", "phase_d", "human_eval", "pruning_rl"):
        check(f"forbidden_launch_{key}_false", forbidden_launches.get(key) is False, str(forbidden_launches.get(key)))
    forbidden_changes = safety.get("forbidden_changes", {})
    for key in ("reward_definitions", "sigma_policy", "prompt_splits", "credit_unit_definitions", "gate_v1", "gate_v2_activation"):
        check(f"forbidden_change_{key}_false", forbidden_changes.get(key) is False, str(forbidden_changes.get(key)))

    check(
        "base_schema",
        base.get("schema_version") == "phase_c1_firstwave_bundle_v1",
        str(base.get("schema_version")),
    )
    check("base_methods", set(base.get("methods", {})) == set(METHODS), str(sorted(base.get("methods", {}))))
    check(
        "base_sigma_targets",
        [float(x["target"]) for x in base["sigma_policy"]["downstream_checkpoints"]] == [0.7, 0.6],
        str(base["sigma_policy"]["downstream_checkpoints"]),
    )

    seen_setting_ids: set[str] = set()
    for setting in review.get("settings", []):
        sid = setting.get("setting_id")
        method = setting.get("method")
        check(f"setting_{sid}_unique", isinstance(sid, str) and sid not in seen_setting_ids, str(sid))
        seen_setting_ids.add(str(sid))
        check(f"setting_{sid}_method_known", method in METHODS, str(method))
        base_method = base["methods"][method]
        check(
            f"setting_{sid}_method_id",
            setting.get("method_id") == base_method.get("method_id"),
            f"{setting.get('method_id')} vs {base_method.get('method_id')}",
        )
        check(
            f"setting_{sid}_reward_mode",
            setting.get("reward_mode") == base_method.get("reward_mode"),
            f"{setting.get('reward_mode')} vs {base_method.get('reward_mode')}",
        )
        if "credit_unit" in setting:
            check(
                f"setting_{sid}_credit_unit",
                setting.get("credit_unit") == base_method.get("credit_unit"),
                f"{setting.get('credit_unit')} vs {base_method.get('credit_unit')}",
            )
        steps = int(setting.get("steps", 0))
        check(f"setting_{sid}_steps_positive", steps > 0, str(steps))
        check(f"setting_{sid}_steps_lte_safety", steps <= int(safety["max_steps_per_setting"]), str(steps))
        overrides = setting.get("backend_overrides", {})
        check(
            f"setting_{sid}_backend_override_keys",
            set(overrides) <= ALLOWED_BACKEND_OVERRIDES,
            str(sorted(overrides)),
        )
        check(
            f"setting_{sid}_diagnostics_enabled",
            overrides.get("log_post_update_diagnostics") is True
            and overrides.get("track_adapter_norm_delta") is True,
            str(overrides),
        )
    check("settings_present", bool(seen_setting_ids), "settings count")
    return checks


def _derived_prompt_manifest(
    source: dict[str, Any],
    *,
    source_path: str,
    n_prompts: int,
    tag: str,
) -> dict[str, Any]:
    prompt_ids = list(source["formal_prompt_ids"][:n_prompts])
    if len(prompt_ids) != n_prompts:
        raise RuntimeError(f"source manifest has fewer than {n_prompts} formal prompts")
    return {
        "purpose": "Derived dev-only C1-lite RL rescue triage prompt manifest.",
        "source_split": source["source_split"],
        "selection": f"first {n_prompts} IDs from source formal_prompt_ids",
        "source_seed": source.get("seed"),
        "derived_from": source_path,
        "derived_tag": tag,
        "formal_prompt_ids": prompt_ids,
        "n_formal_prompts": n_prompts,
        "pi_approved": True,
        "pi_approval_inherited_from": source_path,
        "safety": {
            "held_out_launched": False,
            "phase_d_launched": False,
            "human_eval_launched": False,
            "prompt_split_changed": False,
        },
    }


def _runner_compatibility_checks(bundle: dict[str, Any], prompt_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            raise RuntimeError(f"runner compatibility failed: {name}: {detail}")

    check("schema", bundle.get("schema_version") == "phase_c1_firstwave_bundle_v1", str(bundle.get("schema_version")))
    scope = bundle.get("scope", {})
    check("scope_split", scope.get("split") == "dev", str(scope.get("split")))
    check("prompt_source", scope.get("prompt_source") == "configs/prompts/dev.jsonl", str(scope.get("prompt_source")))
    for key in ("held_out_launched", "phase_d_launched", "human_eval_launched"):
        check(f"scope_{key}", scope.get(key) is False, str(scope.get(key)))
    backend = bundle.get("backend", {})
    check("estimator", backend.get("estimator_type") == "flow_matching_surrogate", str(backend.get("estimator_type")))
    check("exact_logprob_false", backend.get("exact_logprob") is False, str(backend.get("exact_logprob")))
    check(
        "sigma_targets",
        [float(x["target"]) for x in bundle["sigma_policy"]["downstream_checkpoints"]] == [0.7, 0.6],
        str(bundle["sigma_policy"]["downstream_checkpoints"]),
    )
    check("methods_exact", set(bundle.get("methods", {})) == set(METHODS), str(sorted(bundle.get("methods", {}))))
    check("manifest_source_split", prompt_manifest.get("source_split") == "configs/prompts/dev.jsonl", str(prompt_manifest.get("source_split")))
    check("manifest_pi_approved", prompt_manifest.get("pi_approved") is True, str(prompt_manifest.get("pi_approved")))
    check(
        "manifest_count",
        int(prompt_manifest.get("n_formal_prompts", -1)) == len(prompt_manifest.get("formal_prompt_ids", [])) == int(scope.get("n_prompts", -2)),
        f"manifest={prompt_manifest.get('n_formal_prompts')} scope={scope.get('n_prompts')}",
    )
    return checks


def _materialize_bundle(
    *,
    base: dict[str, Any],
    review: dict[str, Any],
    setting: dict[str, Any],
    mode: str,
    tag: str,
    manifest_path: str,
    run_root: str,
    smoke_prompt_count: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    if mode not in {"materialize-smoke", "materialize-train"}:
        raise ValueError(mode)
    sid = setting["setting_id"]
    bundle = copy.deepcopy(base)
    bundle["generated"] = _now_utc()
    bundle["run_id"] = f"phase_c1_lite_rl_rescue_{sid}_{tag}"
    bundle["run_ledger_path"] = (
        f"orbit-research/codex-imports/phase_c1_lite_rl_rescue_run_ledger_{sid}_{tag}.jsonl"
    )
    bundle.setdefault("scope", {})["phase"] = "Phase C1-lite rescue triage"
    bundle["scope"]["formal_prompt_ids_json"] = manifest_path
    bundle["scope"]["n_prompts"] = int(review["scope"]["n_prompts"])
    bundle["scope"]["held_out_launched"] = False
    bundle["scope"]["phase_d_launched"] = False
    bundle["scope"]["human_eval_launched"] = False
    bundle["scope"]["allowed_automatic_expansion"] = "none"
    bundle["safety"]["hard_cap_gpu_h"] = float(review["safety"]["hard_cap_gpu_h"])
    bundle["safety"].setdefault("do_not_modify", [])
    for protected in review["safety"]["do_not_modify"]:
        if protected not in bundle["safety"]["do_not_modify"]:
            bundle["safety"]["do_not_modify"].append(protected)
    bundle["safety"].setdefault("forbidden_launches", {})
    bundle["safety"]["forbidden_launches"]["held_out"] = False
    bundle["safety"]["forbidden_launches"]["phase_d"] = False
    bundle["safety"]["forbidden_launches"]["human_eval"] = False
    bundle["safety"]["forbidden_launches"]["pruning_rl"] = False
    bundle["safety"].setdefault("forbidden_changes", {})
    bundle["safety"]["forbidden_changes"]["reward_definitions"] = False
    bundle["safety"]["forbidden_changes"]["sigma_policy"] = False
    bundle["safety"]["forbidden_changes"]["prompt_splits"] = False
    bundle["safety"]["forbidden_changes"]["credit_unit_definitions"] = False
    bundle["safety"]["forbidden_changes"]["gate_v1"] = False
    bundle["safety"]["forbidden_changes"]["gate_v2_activation"] = False
    for key, value in setting["backend_overrides"].items():
        bundle["backend"][key] = value
    bundle["firstwave"]["rl_steps"] = int(setting["steps"])
    bundle["firstwave"]["output_root"] = f"{run_root}/{sid}"
    bundle["firstwave"]["checkpoint_every_steps"] = int(base["firstwave"]["checkpoint_every_steps"])
    bundle["smoke"]["output_root"] = f"{run_root}/{sid}_smoke"
    bundle["smoke"]["max_prompts_allowed"] = int(base["smoke"]["max_prompts_allowed"])
    if smoke_prompt_count < 1 or smoke_prompt_count > int(bundle["smoke"]["max_prompts_allowed"]):
        raise RuntimeError("smoke_prompt_count must be between 1 and smoke.max_prompts_allowed")
    bundle["smoke"]["prompt_ids"] = review["_derived_prompt_ids"][:smoke_prompt_count]
    bundle["launch_policy"]["require_claude_audit"] = True
    bundle["launch_policy"]["require_expected_total_gpu_h_lte"] = float(review["safety"]["hard_cap_gpu_h"])
    bundle["launch_policy"]["parallelism_policy"] = (
        "C1-lite generated bundle: use --method for one setting/method per process; "
        "do not prompt-shard one method because that would train separate adapters."
    )

    diff = _diff_paths(base, bundle)
    allowed = {
        "generated",
        "run_id",
        "run_ledger_path",
        "scope.phase",
        "scope.formal_prompt_ids_json",
        "scope.n_prompts",
        "scope.held_out_launched",
        "scope.phase_d_launched",
        "scope.human_eval_launched",
        "scope.allowed_automatic_expansion",
        "safety.hard_cap_gpu_h",
        "safety.do_not_modify",
        "safety.forbidden_launches.pruning_rl",
        "safety.forbidden_changes.gate_v1",
        "safety.forbidden_changes.gate_v2_activation",
        "backend.learning_rate",
        "backend.advantage_gain",
        "backend.log_post_update_diagnostics",
        "backend.track_adapter_norm_delta",
        "firstwave.rl_steps",
        "firstwave.output_root",
        "smoke.output_root",
        "smoke.prompt_ids",
        "launch_policy.require_expected_total_gpu_h_lte",
        "launch_policy.parallelism_policy",
    }
    disallowed = [row for row in diff if row["path"] not in allowed]
    if disallowed:
        raise RuntimeError(f"generated bundle has disallowed diffs: {disallowed[:8]}")
    return bundle, diff, disallowed


def _select_settings(review: dict[str, Any], setting_arg: str) -> list[dict[str, Any]]:
    settings = list(review.get("settings", []))
    if setting_arg == "all":
        return settings
    selected = [s for s in settings if s.get("setting_id") == setting_arg]
    if not selected:
        raise RuntimeError(f"unknown setting: {setting_arg}")
    return selected


def _build_plan(
    *,
    review_path: Path,
    base_path: Path,
    artifacts_dir: Path,
    tag: str,
    output_plan: Path | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    review = _load_yaml(review_path)
    base = _load_yaml(base_path)
    checks = _validate_review_config(review, base)
    prompt_source_path = REPO_ROOT / review["scope"]["formal_prompt_ids_json"]
    prompt_source = _load_formal_prompt_manifest(prompt_source_path)
    derived = _derived_prompt_manifest(
        prompt_source,
        source_path=review["scope"]["formal_prompt_ids_json"],
        n_prompts=int(review["scope"]["n_prompts"]),
        tag=tag,
    )
    review["_derived_prompt_ids"] = list(derived["formal_prompt_ids"])
    plan = {
        "schema_version": "phase_c1_lite_rl_rescue_bridge_validate_v1",
        "timestamp": _now_utc(),
        "status": "PASS",
        "review_config": _rel(review_path),
        "base_config": _rel(base_path),
        "artifacts_dir": _rel(artifacts_dir),
        "tag": tag,
        "cpu_only": True,
        "gpu_jobs_launched": 0,
        "track_a_run_dir_touched": False,
        "raw_c1_outputs_modified": False,
        "review_status": review["status"],
        "settings": [
            {
                "setting_id": s["setting_id"],
                "method": s["method"],
                "steps": int(s["steps"]),
                "backend_overrides": dict(s["backend_overrides"]),
            }
            for s in review["settings"]
        ],
        "derived_prompt_manifest_preview": {
            "n_formal_prompts": derived["n_formal_prompts"],
            "source_split": derived["source_split"],
            "first_prompt_ids": derived["formal_prompt_ids"][:5],
            "last_prompt_ids": derived["formal_prompt_ids"][-5:],
        },
        "validation_checks": checks,
    }
    if output_plan is not None:
        _write_json(output_plan, plan)
        plan["output_plan"] = _rel(output_plan)
    return review, base, derived, plan


def run_validate(args: argparse.Namespace) -> dict[str, Any]:
    review_path = REPO_ROOT / args.review_config
    base_path = REPO_ROOT / args.base_config
    artifacts_dir = REPO_ROOT / args.artifacts_dir
    output_plan = REPO_ROOT / args.output_plan if args.output_plan else None
    _review, _base, _derived, plan = _build_plan(
        review_path=review_path,
        base_path=base_path,
        artifacts_dir=artifacts_dir,
        tag=args.tag,
        output_plan=output_plan,
    )
    return plan


def run_materialize(args: argparse.Namespace) -> dict[str, Any]:
    if args.run_root is None:
        raise RuntimeError("--run-root is required for materialize modes")
    run_root = Path(args.run_root)
    if run_root.is_absolute():
        raise RuntimeError("--run-root must be repo-relative and must not be absolute")
    if (REPO_ROOT / run_root).exists():
        raise RuntimeError(f"refusing existing future run root: {run_root}")
    if "phase_c1_firstwave_20260524_researcher_go_01" in str(run_root):
        raise RuntimeError("run root must not target the completed formal C1 first-wave directory")

    review_path = REPO_ROOT / args.review_config
    base_path = REPO_ROOT / args.base_config
    artifacts_dir = REPO_ROOT / args.artifacts_dir
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    review, base, derived, plan = _build_plan(
        review_path=review_path,
        base_path=base_path,
        artifacts_dir=artifacts_dir,
        tag=args.tag,
        output_plan=None,
    )
    manifest_path = artifacts_dir / f"phase_c1_lite_rl_rescue_prompts_32_{args.tag}.json"
    _write_json(manifest_path, derived)
    prompt_manifest_rel = _rel(manifest_path)

    materialized: list[dict[str, Any]] = []
    all_diffs: list[dict[str, Any]] = []
    for setting in _select_settings(review, args.setting):
        bundle, diff, disallowed = _materialize_bundle(
            base=base,
            review=review,
            setting=setting,
            mode=args.mode,
            tag=args.tag,
            manifest_path=prompt_manifest_rel,
            run_root=str(run_root),
            smoke_prompt_count=int(args.smoke_prompt_count),
        )
        compat = _runner_compatibility_checks(bundle, derived)
        sid = setting["setting_id"]
        bundle_path = artifacts_dir / f"generated_phase_c1_lite_{sid}_{args.mode}_{args.tag}.yaml"
        _write_yaml(bundle_path, bundle)
        future_mode_root = (
            str(run_root / f"{sid}_smoke")
            if args.mode == "materialize-smoke"
            else str(run_root / sid)
        )
        materialized.append(
            {
                "setting_id": sid,
                "method": setting["method"],
                "mode": args.mode,
                "bundle_path": _rel(bundle_path),
                "future_run_root": future_mode_root,
                "future_runner_command": [
                    "python",
                    "scripts/phase_c1_grpo.py",
                    "--config",
                    _rel(bundle_path),
                    "--mode",
                    "smoke" if args.mode == "materialize-smoke" else "train",
                    "--method",
                    setting["method"],
                    "--output-root",
                    future_mode_root,
                    "--pi-approved-launch",
                ],
                "diff_count": len(diff),
                "disallowed_diff_count": len(disallowed),
                "runner_compatibility_checks": compat,
            }
        )
        for row in diff:
            all_diffs.append({"setting_id": sid, **row})

    diff_path = artifacts_dir / f"phase_c1_lite_rl_rescue_{args.mode}_bundle_diffs_{args.tag}.json"
    _write_json(
        diff_path,
        {
            "schema_version": "phase_c1_lite_rl_rescue_bundle_diff_v1",
            "timestamp": _now_utc(),
            "mode": args.mode,
            "tag": args.tag,
            "base_config": _rel(base_path),
            "allowed_only": True,
            "diffs": all_diffs,
        },
    )
    summary_path = artifacts_dir / f"phase_c1_lite_rl_rescue_{args.mode}_summary_{args.tag}.json"
    summary = {
        "schema_version": "phase_c1_lite_rl_rescue_materialization_v1",
        "timestamp": _now_utc(),
        "status": "PASS",
        "mode": args.mode,
        "tag": args.tag,
        "cpu_only": True,
        "gpu_jobs_launched": 0,
        "track_a_run_dir_touched": False,
        "raw_c1_outputs_modified": False,
        "review_config": _rel(review_path),
        "base_config": _rel(base_path),
        "run_root_not_created": str(run_root),
        "prompt_manifest_path": prompt_manifest_rel,
        "diff_path": _rel(diff_path),
        "validation_plan": plan,
        "materialized": materialized,
    }
    _write_json(summary_path, summary)
    summary["summary_path"] = _rel(summary_path)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-config", default=DEFAULT_REVIEW_CONFIG)
    parser.add_argument("--base-config", default=DEFAULT_BASE_CONFIG)
    parser.add_argument("--mode", choices=["validate", "materialize-smoke", "materialize-train"], required=True)
    parser.add_argument("--artifacts-dir", default=DEFAULT_ARTIFACTS_DIR)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--setting", default="all")
    parser.add_argument("--run-root", default=None)
    parser.add_argument("--smoke-prompt-count", type=int, default=2)
    parser.add_argument("--output-plan", default=None)
    args = parser.parse_args()

    if args.mode == "validate":
        result = run_validate(args)
    else:
        result = run_materialize(args)
    print(json.dumps({"status": result["status"], "mode": args.mode, "gpu_jobs_launched": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
