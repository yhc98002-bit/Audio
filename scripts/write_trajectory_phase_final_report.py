"""Write the trajectory-aware phase PI report from current artifacts.

This is reporting only. It does not launch training, generation, Phase D, human
evaluation, crowdsourcing, pruning+RL, or alter scientific definitions.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any


OUT = Path("orbit-research/TRAJECTORY_AWARE_FINAL_PI_REPORT_2026-05-28.md")
PRIMARY = "common_robust_lcb"


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _fmt(value: Any, digits: int = 4) -> str:
    try:
        val = float(value)
    except (TypeError, ValueError):
        return "NA"
    return f"{val:.{digits}f}"


def _row(rows: list[dict[str, Any]], schedule: str, *, metric: str = PRIMARY, stratum: str = "all") -> dict[str, Any]:
    for row in rows:
        if row.get("schedule") == schedule and row.get("metric", metric) == metric and row.get("stratum", stratum) == stratum:
            return row
    return {}


def _audit_verdict(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    obj = _read_json(path) or {}
    text = str(obj.get("result") or obj.get("response") or obj)
    match = re.search(r"\b(ACCEPT_WITH_NONBLOCKING_NOTES|ACCEPT|REJECT)\b", text)
    return match.group(1) if match else "UNKNOWN"


def _human_audio_status() -> tuple[str, str]:
    manifest = Path("orbit-research/human_spotcheck_packet_20260528/HUMAN_SPOTCHECK_PACKET_MANIFEST.md")
    if not manifest.exists():
        return "MISSING", str(manifest)
    text = manifest.read_text(encoding="utf-8")
    match = re.search(r"Audio status: `([^`]+)`", text)
    return (match.group(1) if match else "UNKNOWN"), str(manifest)


def _bon16_status(payload: dict[str, Any] | None) -> str:
    if not payload:
        return "PENDING"
    return "COMPLETE" if payload.get("n_prompts") else "UNKNOWN"


def main() -> int:
    main_payload = _read_json(Path("orbit-research/EARLY_TWEEDIE_MAIN_RESULTS.json")) or {}
    etv_payload = _read_json(Path("orbit-research/EARLY_TRAJECTORY_VERIFIER_RESULTS.json")) or {}
    bon16_payload = _read_json(Path("orbit-research/BON16_PRUNING_SUBSET_RESULTS.json"))
    human_status, human_manifest = _human_audio_status()

    main_rows = list(main_payload.get("main_rows") or [])
    learned_rows = list(etv_payload.get("learned_rows") or [])
    risk_rows = list(etv_payload.get("risk_control_rows") or [])
    bootstrap_rows = list(main_payload.get("bon4_bootstrap_rows") or [])
    cross_axis_rows = list(main_payload.get("cross_axis_rows") or [])

    full = _row(main_rows, "full_bon8")
    bon4 = _row(main_rows, "bon4_random_subset")
    etp_a = _row(main_rows, "raw_schedule_a_sigma0.9_top4_sigma0.7_top2")
    etp_c = _row(main_rows, "raw_schedule_c_sigma0.8_top6")
    bottom07 = _row(main_rows, "raw_bottom_prune_sigma0.7_remove_bottom25")
    random_prune = _row(main_rows, "random_prune_keep4_keep2")

    etv_a = _row(learned_rows, "etv_schedule_a_sigma0.9_top4_sigma0.7_top2")
    etv_bottom = _row(learned_rows, "etv_bottom_prune_sigma0.7_remove_bottom25")
    boot = bootstrap_rows[0] if bootstrap_rows else {}

    weak_axes = [
        row for row in cross_axis_rows
        if row.get("schedule") == "raw_schedule_a_sigma0.9_top4_sigma0.7_top2"
        and row.get("evaluation_metric") in {"semantic_fit", "lyric_intelligibility"}
    ]

    audit1 = _audit_verdict(Path("orbit-research/CLAUDE_AUDIT_1_DATASET_LEAKAGE_2026-05-28.json"))
    audit2 = _audit_verdict(Path("orbit-research/CLAUDE_AUDIT_2_BASELINE_FAIRNESS_2026-05-28.json"))
    audit3 = _audit_verdict(Path("orbit-research/CLAUDE_AUDIT_3_LEARNED_ETV_RISK_2026-05-28.json"))

    complete = bool(bon16_payload) and human_status == "present"
    status = "COMPLETE" if complete else "PARTIAL_PENDING_BON16_OR_AUDIO"

    lines = [
        "# Trajectory-Aware Inference-Time Scaling PI Report",
        "",
        f"Generated UTC: `{_now_utc()}`",
        f"Report status: `{status}`",
        "",
        "## Executive Summary",
        "",
        "The project is now best framed as early trajectory verification for flow-matching music generation. C1 RL post-training remains useful boundary evidence because the backend trained cleanly but common downstream evaluation showed no clear winner. The positive evidence is instead concentrated in Early-Tweedie / Early Trajectory Verifier inference-time selection.",
        "",
        "Main current conclusion: raw Early-Tweedie pruning is a credible transparent baseline, while the learned lightweight ETV is the stronger candidate for the main method when the claim is risk-aware pruning rather than simple heuristic pruning.",
        "",
        "## Dataset Card",
        "",
        "- Dataset: `orbit-research/trajectory_candidate_dataset.jsonl`",
        "- Dataset card: `orbit-research/TRAJECTORY_CANDIDATE_DATASET_CARD.md`",
        f"- Candidates: `{main_payload.get('n_candidates', 'NA')}`",
        f"- Prompts: `{main_payload.get('n_prompts', 'NA')}`",
        f"- Analysis splits: `{main_payload.get('splits', {})}`",
        "- Split rule: prompt-level split only; no prompt's candidates cross train/validation/test boundaries.",
        "",
        "## Main BoN-8 Early-Tweedie Result",
        "",
        "| method | compute | reward_fraction | winner_match | false_negative_top1 |",
        "|---|---:|---:|---:|---:|",
        f"| Full BoN-8 | {_fmt(full.get('compute_fraction'), 3)} | {_fmt(full.get('reward_fraction'))} | {_fmt(full.get('winner_match'))} | {_fmt(full.get('false_negative_top1_prompt_rate'))} |",
        f"| BoN-4 random subset | {_fmt(bon4.get('compute_fraction'), 3)} | {_fmt(bon4.get('reward_fraction'))} | {_fmt(bon4.get('winner_match'))} | {_fmt(bon4.get('false_negative_top1_prompt_rate'))} |",
        f"| Raw ETP Schedule A | {_fmt(etp_a.get('compute_fraction'), 3)} | {_fmt(etp_a.get('reward_fraction'))} | {_fmt(etp_a.get('winner_match'))} | {_fmt(etp_a.get('false_negative_top1_prompt_rate'))} |",
        f"| Raw ETP Schedule C | {_fmt(etp_c.get('compute_fraction'), 3)} | {_fmt(etp_c.get('reward_fraction'))} | {_fmt(etp_c.get('winner_match'))} | {_fmt(etp_c.get('false_negative_top1_prompt_rate'))} |",
        f"| Bottom-prune sigma0.7 remove bottom25 | {_fmt(bottom07.get('compute_fraction'), 3)} | {_fmt(bottom07.get('reward_fraction'))} | {_fmt(bottom07.get('winner_match'))} | {_fmt(bottom07.get('false_negative_top1_prompt_rate'))} |",
        f"| Random prune matched to Schedule A | {_fmt(random_prune.get('compute_fraction'), 3)} | {_fmt(random_prune.get('reward_fraction'))} | {_fmt(random_prune.get('winner_match'))} | {_fmt(random_prune.get('false_negative_top1_prompt_rate'))} |",
        "",
        "Same-compute BoN-4 comparison:",
        "",
        f"- ETP@50 reward fraction: `{_fmt(etp_a.get('reward_fraction'))}`.",
        f"- BoN-4 random-subset reward fraction: `{_fmt(bon4.get('reward_fraction'))}`.",
        f"- Paired bootstrap delta reward fraction: `{_fmt(boot.get('delta_reward_fraction'))}` with 95% CI `[{_fmt(boot.get('ci95_low_delta_reward_fraction'))}, {_fmt(boot.get('ci95_high_delta_reward_fraction'))}]`.",
        "- Interpretation: the primary/common-axis advantage is statistically separated but modest; do not overstate the effect size.",
        "",
        "Cross-axis caveat:",
        "",
    ]
    if weak_axes:
        for row in weak_axes:
            lines.append(f"- Common-selected ETP@50 evaluated on `{row.get('evaluation_metric')}` has reward_fraction `{_fmt(row.get('reward_fraction'))}`.")
    else:
        lines.append("- Cross-axis rows missing or not parsed.")
    lines.extend(
        [
            "- The semantic and lyric axes are the main limitation; the paper should not claim uniform all-axis preservation.",
            "",
            "## Learned ETV Result",
            "",
            "| method | compute | reward_fraction | winner_match | false_negative_top1 |",
            "|---|---:|---:|---:|---:|",
            f"| Learned ETV Schedule A | {_fmt(etv_a.get('compute_fraction'), 3)} | {_fmt(etv_a.get('reward_fraction'))} | {_fmt(etv_a.get('winner_match'))} | {_fmt(etv_a.get('false_negative_top1_prompt_rate'))} |",
            f"| Learned ETV bottom-prune sigma0.7 remove bottom25 | {_fmt(etv_bottom.get('compute_fraction'), 3)} | {_fmt(etv_bottom.get('reward_fraction'))} | {_fmt(etv_bottom.get('winner_match'))} | {_fmt(etv_bottom.get('false_negative_top1_prompt_rate'))} |",
            "",
            "Prediction evidence:",
            "",
        ]
    )
    for row in (etv_payload.get("model_summary", {}).get("model_eval_rows") or []):
        if row.get("split") == "test":
            lines.append(f"- `{row.get('model')}`: Spearman `{_fmt(row.get('spearman_final_common'))}`, prompt NDCG `{_fmt(row.get('prompt_ndcg'))}`.")
    lines.extend(
        [
            "",
            "Empirical risk-calibrated pruning:",
            "",
            "| target | epsilon | prune_bottom | test_compute | test_reward_fraction | test_fn_top1 | test_fn_top2_candidate |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in risk_rows:
        lines.append(
            f"| {row.get('target')} | {_fmt(row.get('epsilon'), 2)} | {row.get('calibrated_prune_bottom_candidates')} | "
            f"{_fmt(row.get('test_compute_fraction'), 3)} | {_fmt(row.get('test_reward_fraction'))} | "
            f"{_fmt(row.get('test_false_negative_top1_prompt_rate'))} | {_fmt(row.get('test_false_negative_top2_candidate_rate'))} |"
        )

    lines.extend(
        [
            "",
            "This is empirical validation-calibrated pruning, not a distribution-free risk-control guarantee.",
            "",
            "## BoN-16 Subset",
            "",
            f"- Status: `{_bon16_status(bon16_payload)}`.",
            "- Run root: `runs/early_tweedie_bon16_subset_128_20260528_full01`",
            "- Result files: `orbit-research/BON16_PRUNING_SUBSET_RESULTS.md`, `.json`, `.csv`",
        ]
    )
    if bon16_payload:
        lines.extend(
            [
                f"- Prompts: `{bon16_payload.get('n_prompts')}`",
                f"- Candidates: `{bon16_payload.get('n_candidates')}`",
                f"- GPU-hours summed over shards: `{_fmt(bon16_payload.get('gpu_hours_sum'))}`",
                "",
                "| BoN-16 method | compute | reward_fraction | winner_match | false_negative_top1 |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for row in bon16_payload.get("result_rows") or []:
            lines.append(
                f"| {row.get('schedule')} | {_fmt(row.get('compute_fraction'), 3)} | {_fmt(row.get('reward_fraction'))} | "
                f"{_fmt(row.get('winner_match'))} | {_fmt(row.get('false_negative_top1_prompt_rate'))} |"
            )

    lines.extend(
        [
            "",
            "## Human Spot-Check Packet",
            "",
            f"- Manifest: `{human_manifest}`",
            f"- Audio status: `{human_status}`",
            "- No crowdsourcing or human evaluation was launched.",
            "",
            "## Global Quality Mechanism",
            "",
            "- Mechanism memo: `orbit-research/GLOBAL_QUALITY_MECHANISM_FIGURES.md`",
            "- Mechanism tables: `orbit-research/GLOBAL_QUALITY_MECHANISM_TABLES.csv`",
            "- Interpretation: for ACE-Step short-form outputs, local-window rewards appear to track persistent global trajectory quality more than isolated local failures. This supports trajectory-aware inference-time selection and helps explain the weak RL-local-credit result.",
            "",
            "## ICLR Reviewer-Risk Audit",
            "",
            "- Audit memo: `orbit-research/ICLR_REVIEWER_RISK_AUDIT.md`",
            f"- Claude dataset/leakage audit: `{audit1}`",
            f"- Claude same-compute baseline audit: `{audit2}`",
            f"- Claude learned ETV/risk audit: `{audit3}`",
            "",
            "Main risks to disclose:",
            "",
            "- The ETP@50 improvement over BoN-4 is small on the primary/common metric.",
            "- Common-selected pruning weakens semantic/lyric cross-axis preservation relative to BoN-4.",
            "- Empirical risk calibration is not a formal distribution-free guarantee.",
            "- Human listening packet is prepared for PI review, but crowdsourcing has not been launched.",
            "",
            "## Recommended Paper Framing",
            "",
            "Recommended framing: **learned ETV as the main method candidate, with raw ETP as the transparent mechanistic baseline**.",
            "",
            "Rationale:",
            "",
            "- Raw ETP proves that early Tweedie estimates contain exploitable trajectory information.",
            "- Learned ETV improves held-out rank prediction and conservative pruning, especially bottom-pruning.",
            "- The mechanism analysis gives a coherent story: early local estimates are useful because quality differences are persistent across the short-form trajectory.",
            "- RL post-training should be described as a bounded negative/boundary result rather than the main contribution.",
            "",
            "## Remaining PI Decisions",
            "",
            "- Whether to make learned ETV or raw ETP the headline method.",
            "- Whether to run PI listening on the prepared human spot-check packet.",
            "- Whether cross-axis semantic/lyric weakness requires a mitigation experiment or should be treated as a limitation.",
            "- Whether to pursue a formal Learn-then-Test / conformal risk-control version after the current empirical result.",
            "",
            "## Boundary Confirmation",
            "",
            "- No new RL training launched.",
            "- No pruning+RL launched.",
            "- No Phase D launched.",
            "- No human crowdsourcing launched.",
            "- No `gate_v1.yaml` modification.",
            "- No reward-definition change.",
            "- No prompt-split change.",
            "- No sigma definition change outside declared pruning schedules.",
            "- No canonical proposal rewrite.",
        ]
    )
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "report": str(OUT), "bon16": _bon16_status(bon16_payload), "human_audio": human_status}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
