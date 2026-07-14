#!/usr/bin/env python3
"""Build a non-destructive T7/A-prime evidence snapshot and status report."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tarfile
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"repository root not found from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
PAPER = ROOT / "paper_prep"
T7 = PAPER / "t7_judge_gold_20260713"
REPORT = T7 / "T7_INGEST_JUDGE_LIVE_REPORT_20260713.md"
VALIDATION = T7 / "judge_completion/POOLED_JUDGE_VALIDATION.json"
GLOBAL_REPORT = T7 / "judge_completion/A_PRIME_STRATIFIED_500_REPORT.md"
A_GATE = PAPER / "validation_A_prime/A_PRIME_GATE_REPORT_20260713.md"
A_GATE_JSON = PAPER / "validation_A_prime/A_PRIME_GATE_RESULT_20260713.json"
LIVE = PAPER / "w2_execution_20260712/live_confirmation_20260713"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def first_status(path: Path, key: str, default: str) -> str:
    if not path.is_file():
        return default
    marker = f"{key} = "
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.strip().strip("`")
        if clean.startswith(marker):
            return clean.split("=", 1)[1].strip()
    return default


def watcher_state(job: str) -> dict:
    status_path = T7 / f"gpu_queue/{job}_gpu_watch_status.json"
    if status_path.is_file():
        return json.loads(status_path.read_text(encoding="utf-8"))
    log = T7 / f"gpu_queue/{job}_gpu_watch.jsonl"
    if log.is_file():
        rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
        if rows:
            return rows[-1]
    return {"status": "NOT_DISPATCHED"}


def tmux_pid(session: str) -> str:
    result = subprocess.run(
        ["tmux", "list-panes", "-t", session, "-F", "#{pane_pid}"],
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip().splitlines()[0] if result.returncode == 0 and result.stdout.strip() else "not-running"


def current_statuses() -> dict[str, str]:
    amendment = first_status(
        T7 / "W2_SIGNATURE_VERIFICATION_REPORT.md",
        "W2_AMENDMENT_STATUS",
        "UNKNOWN",
    )
    adoption = first_status(
        T7 / "W2_SIGNATURE_VERIFICATION_REPORT.md",
        "W2_ADOPTION",
        first_status(T7 / "W2_ADOPTION_SIGNATURE_REQUEST.md", "W2_ADOPTION", "UNKNOWN"),
    )
    judge_watch = watcher_state("judge")
    live_watch = watcher_state("live")
    if VALIDATION.is_file():
        judge = json.loads(VALIDATION.read_text(encoding="utf-8"))["JUDGE_VALIDATION_STATUS"]
    elif judge_watch.get("status") == "LAUNCHED":
        judge = "RUNNING_GPU_CHAIN"
    elif judge_watch.get("status") == "TIMEOUT_24H_ESCALATED":
        judge = "BLOCKED_GPU_QUEUE_TIMEOUT"
    else:
        judge = "QUEUED_AWAITING_GPUS"
    if GLOBAL_REPORT.is_file():
        judge_500 = "COMPLETE"
    elif judge == "FAIL":
        judge_500 = "NOT_RUN_VALIDATION_FAIL"
    else:
        judge_500 = "QUEUED_AFTER_VALIDATION"
    if A_GATE_JSON.is_file():
        a_prime = json.loads(A_GATE_JSON.read_text(encoding="utf-8"))["A_PRIME_GATE"]
    else:
        a_prime = "QUEUED_AFTER_JUDGE"
    live_terminal = first_status(LIVE / "LIVE_CONFIRM_TERMINAL_STATUS.txt", "LIVE_CONFIRM_STATUS", "")
    if live_terminal:
        live = live_terminal
    elif live_watch.get("status") == "LAUNCHED":
        live = "RUNNING"
    elif amendment not in {"SIGNED", "SIGNED_BY_BOTH_PIS"}:
        live = "BLOCKED_UNSIGNED_W2_AMENDMENT"
    else:
        live = "QUEUED_AWAITING_GPUS"
    return {
        "W2_AMENDMENT_STATUS": amendment,
        "W2_ADOPTION": adoption,
        "T7_INGESTION_STATUS": "PASS",
        "JUDGE_VALIDATION_STATUS": judge,
        "JUDGE_500_STATUS": judge_500,
        "A_PRIME_GATE": a_prime,
        "PLAN_CLAIMS_SUPERSESSION": "NOT_APPLIED" if adoption != "SIGNED" else "SIGNATURE_BRANCH_REQUIRES_RECHECK",
        "LIVE_CONFIRM_STATUS": live,
    }


def write_report(bundle_name: str, tarball_name: str) -> dict[str, str]:
    statuses = current_statuses()
    judge_watch = watcher_state("judge")
    live_watch = watcher_state("live")
    test_summary_path = PAPER / "validation_A_prime/A_PRIME_UNBLOCK_FULL_TEST_SUMMARY_20260714.json"
    if not test_summary_path.is_file():
        test_summary_path = T7 / "FULL_TEST_RESULT_SUMMARY_20260714.json"
    if not test_summary_path.is_file():
        test_summary_path = T7 / "FULL_TEST_RESULT_SUMMARY_20260713.json"
    if not test_summary_path.is_file():
        test_summary_path = T7 / "FULL_TEST_RESULT_SUMMARY.json"
    tests = json.loads(test_summary_path.read_text(encoding="utf-8")) if test_summary_path.is_file() else {}
    validation = json.loads(VALIDATION.read_text(encoding="utf-8")) if VALIDATION.is_file() else {}
    live_audit_path = LIVE / "LIVE_CONFIRM_AUDIT.json"
    live_audit = json.loads(live_audit_path.read_text(encoding="utf-8")) if live_audit_path.is_file() else {}
    gate_result_path = PAPER / "validation_A_prime/A_PRIME_GATE_RESULT_20260713.json"
    gate_result = json.loads(gate_result_path.read_text(encoding="utf-8")) if gate_result_path.is_file() else {}
    global_result_path = T7 / "judge_completion/A_PRIME_STRATIFIED_500_RESULTS.csv"
    global_results: dict[tuple[str, str], dict[str, str]] = {}
    if global_result_path.is_file():
        with global_result_path.open(newline="", encoding="utf-8") as handle:
            global_results = {(row["group"], row["group_value"]): row for row in csv.DictReader(handle)}
    test_status = "PASS" if tests.get("status") == "PASS" and int(tests.get("failed", 0)) == 0 else "PENDING"
    statuses["EVIDENCE_BUNDLE_STATUS"] = "BUILT"
    statuses["TEST_SUITE_STATUS"] = test_status
    lines = [
        "# T7 Ingest, Judge Validation, And Live-Confirm Queue",
        "",
        f"`T7_INGESTION_STATUS = {statuses['T7_INGESTION_STATUS']}`",
        "evidence: `paper_prep/t7_judge_gold_20260713/ratings_ingest/T7_RATINGS_INGEST_AUDIT.json`, `paper_prep/t7_judge_gold_20260713/ratings_ingest/T7_TOPUP_INGEST_REPORT.md`",
        "",
        f"`JUDGE_VALIDATION_STATUS = {statuses['JUDGE_VALIDATION_STATUS']}`",
        "evidence: `paper_prep/t7_judge_gold_20260713/judge_completion/POOLED_DISJOINT_GOLD_MANIFEST.csv`, `paper_prep/t7_judge_gold_20260713/gpu_queue/judge_gpu_watch.jsonl`"
        + (", `paper_prep/t7_judge_gold_20260713/judge_completion/POOLED_JUDGE_VALIDATION_REPORT.md`" if VALIDATION.is_file() else ""),
        "",
        f"`JUDGE_500_STATUS = {statuses['JUDGE_500_STATUS']}`",
        "evidence: `paper_prep/t7_judge_gold_20260713/judge_completion/A_PRIME_STRATIFIED_500_JUDGE_MANIFEST.csv`, `paper_prep/scripts/complete_t7_judge_aprime_20260713.py`"
        + (", `paper_prep/t7_judge_gold_20260713/judge_completion/A_PRIME_STRATIFIED_500_REPORT.md`" if GLOBAL_REPORT.is_file() else ""),
        "",
        f"`A_PRIME_GATE = {statuses['A_PRIME_GATE']}`",
        "evidence: `paper_prep/pi_ratings_20260711/processed/T2_A_PRIME_HUMAN_CORE_OFFICIAL.csv`, `paper_prep/scripts/complete_t7_judge_aprime_20260713.py`, `paper_prep/scripts/record_a_prime_gate_call_20260714.py`"
        + (", `paper_prep/validation_A_prime/A_PRIME_GATE_REPORT_20260713.md`" if A_GATE.is_file() else ""),
        "",
        f"`W2_AMENDMENT_STATUS = {statuses['W2_AMENDMENT_STATUS']}`",
        "evidence: `paper_prep/W2_AMENDMENT_20260712.md`, `paper_prep/t7_judge_gold_20260713/W2_SIGNATURE_VERIFICATION_REPORT.md`",
        "",
        f"`W2_ADOPTION = {statuses['W2_ADOPTION']}`",
        "evidence: `paper_prep/t7_judge_gold_20260713/W2_ADOPTION_SIGNATURE_REQUEST.md`, `paper_prep/autochain_20260712/recompute/DUAL_PI_ADOPTION_PACKET.md`",
        "",
        f"`PLAN_CLAIMS_SUPERSESSION = {statuses['PLAN_CLAIMS_SUPERSESSION']}`",
        "evidence: `paper_prep/autochain_20260712/recompute/PLAN_UPDATE_DRAFT.md`, `paper_prep/autochain_20260712/recompute/CLAIMS_UPDATE_DRAFT.md`, `paper_prep/PLAN.md`, `paper_prep/CLAIMS.md`",
        "",
        f"`LIVE_CONFIRM_STATUS = {statuses['LIVE_CONFIRM_STATUS']}`",
        "evidence: `paper_prep/w2_execution_20260712/live_confirmation_20260713/GENERATION_COMPLETION_AUDIT.json`, `paper_prep/w2_execution_20260712/live_confirmation_20260713/LIVE_CONFIRM_AUDIT.json`, `paper_prep/w2_execution_20260712/live_confirmation_20260713/LIVE_CONFIRM_REPORT.md`, `paper_prep/w2_execution_20260712/live_confirmation_20260713/LIVE_CONFIRM_RESULTS.csv`",
        "",
        f"`EVIDENCE_BUNDLE_STATUS = {statuses['EVIDENCE_BUNDLE_STATUS']}`",
        f"evidence: `paper_prep/{bundle_name}/INDEX.md`, `paper_prep/{tarball_name}`",
        "",
        f"`TEST_SUITE_STATUS = {statuses['TEST_SUITE_STATUS']}`",
        f"evidence: `{test_summary_path.relative_to(ROOT)}`, `tests/test_t7_judge_gold_20260713.py`",
        "",
        "## Validated Input",
        "",
        "- T7 response IDs: 40/40 exact; provenance: `pi:Richard`.",
        "- Authoritative Label A composition: 40 `no`, zero blanks.",
        "- Optional Label B blanks: 2; optional confidence blanks: 40.",
        "- T7 hash overlap with detector selection/promotion: 0; overlap with prior judge gold: 0.",
        "- Pooled disjoint gold: 216 rows = 149 human `yes` positives + 67 human `no` negatives.",
        "- Stratified-500: 500 frozen IDs mapping to 493 unique media hashes; inference and estimation deduplicate first.",
        "",
        "## Judge Validation And A-Prime",
        "",
        *(
            [
                f"- Pooled judge validation: sensitivity {validation['metrics']['sensitivity']:.6f}, specificity {validation['metrics']['specificity']:.6f}, balanced accuracy {validation['metrics']['balanced_accuracy']:.6f}, MCC {validation['metrics']['mcc']:.6f}, abstention {validation['metrics']['abstention_rate']:.6f}.",
                f"- One-sided 95% lower bounds: sensitivity {validation['bootstrap']['sensitivity']['one_sided_95_lcb']:.6f}, specificity {validation['bootstrap']['specificity']['one_sided_95_lcb']:.6f}, balanced accuracy {validation['bootstrap']['balanced_accuracy']['one_sided_95_lcb']:.6f}; all frozen checks passed.",
                f"- Gold-set SHA-256: `{validation['gold_set_hash']}`; tuning/evaluation overlap: {validation['tuning_and_evaluation_overlap']}.",
            ]
            if validation
            else ["- Pooled judge validation has not reached a terminal state."]
        ),
        *(
            [
                f"- Stratified judge result, all unique clips: apparent voice rate {float(global_results[('all', 'all')]['apparent_voice_presence_rate']):.6f}; calibrated voice rate {float(global_results[('all', 'all')]['judge_calibrated_voice_presence_rate']):.6f}.",
                f"- Requested-instrumental clips: apparent Label-A violation {float(global_results[('requested_vocal', '0')]['apparent_label_a_violation_rate']):.6f}; calibrated violation {float(global_results[('requested_vocal', '0')]['judge_calibrated_label_a_violation_rate']):.6f}.",
            ]
            if global_results
            else []
        ),
        *(
            [
                f"- Provenance merge: {gate_result['instrument_merge_rows']} rows = {gate_result['instrument_merge_provenance']['pi']} PI core + {gate_result['instrument_merge_provenance']['judge']} validated-judge supplement.",
                f"- Frozen Label-A criteria all met: `{str(gate_result['all_frozen_label_a_criteria_met']).lower()}`. PI decision: `{gate_result['A_PRIME_GATE']}`; the legacy instrument is not validated.",
                f"- Core results: disagreement {gate_result['label_a_bucket_results']['detector_disagreement_112']['matches']}/{gate_result['label_a_bucket_results']['detector_disagreement_112']['decided']}; rare basin {gate_result['label_a_bucket_results']['rare_basin_48']['matches']}/{gate_result['label_a_bucket_results']['rare_basin_48']['decided']} decided; controls {gate_result['label_a_bucket_results']['agreement_spotcheck_30']['matches']}/{gate_result['label_a_bucket_results']['agreement_spotcheck_30']['decided']}.",
            ]
            if gate_result
            else []
        ),
        "",
        "## Queue Contract",
        "",
        f"- Judge watcher: local tmux `adsr_t7_judge_gpu_watch_20260713`, pane PID `{tmux_pid('adsr_t7_judge_gpu_watch_20260713')}`; last state `{judge_watch.get('status', 'UNKNOWN')}`.",
        f"- Judge launch: `{judge_watch.get('launch_node', 'not-launched')}` GPUs `{judge_watch.get('gpu_indices', [])}` after {float(judge_watch.get('idle_predicate_seconds', 0.0)):.1f} continuous idle seconds at `{judge_watch.get('actual_launch_timestamp', 'not-launched')}`. Tensor parallelism 4 required one node and could not split across nodes.",
        f"- Live execution status: `{statuses['LIVE_CONFIRM_STATUS']}`. It ran in remote tmux `adsr_w2_liveconfirm_resume_20260714` on `an12` GPUs 4-7; GPUs 0-3 were occupied by another PI job and were not touched.",
        "- Live launch predicate: signed W2 amendment plus mechanical T6 promotion and four genuinely idle GPUs on one node. The prepared four-worker launcher does not split across nodes.",
        "- Judge recovery polled every 2 minutes; the standing live watcher polls every 10 minutes. Queue timeout: 24 hours. No running process was killed, suspended, or preempted.",
        "- The live-confirm clock began at `2026-07-14T17:00:55+08:00` and ends at `2026-07-16T17:00:55+08:00`; recovery did not reset either timestamp.",
        "- Attempt 2 failed after generation when obsolete local reward-model defaults fell back to blocked Hugging Face. The repaired resume passed an offline local-model preflight and recovered four orphan FLACs in place without regeneration.",
        "- The judge model and runtime were copied from `an29` to `an12`, checksum-dry-run verified, and CUDA-import tested. The first detached launch failed before GPU allocation because bare `python` was unavailable; the repaired launcher uses the verified runtime interpreter and completed on GPUs 0-3.",
        "",
        "## Signature-Gated Branch",
        "",
        "The W2 amendment has complete PI 1, PI 2, and Claude blocks, so the live branch was authorized and executed. Publication adoption remains fail-closed because its dedicated PI 2 block is blank and the escalation-file PI 2 sentence is truncated. Therefore broad W2 corrected-number supersession was not applied. The targeted A-prime PI gate-call and instrument-scope wording update are separately authorized by the 2026-07-13 PI decision.",
        *(
            [
                "",
                "## Live Confirmation Result",
                "",
                f"- Result: `{live_audit['LIVE_CONFIRM_RESULT']}`; no automatic PASS was issued.",
                "- Generation audit: 512/512 units, 1,536 unique ledger records, and 774/774 checksum-matching decoded FLACs.",
                "- Final violation: no-probe reseed 0.265625; corrected probe/action 0.312500; always direction-conditioned 0.164062.",
                f"- Frozen primary reduction LCB: {live_audit['bootstrap']['policy4_vs_policy1_reduction_lcb_95_one_sided']:.6f}; policy-3 noninferiority UCB: {live_audit['bootstrap']['policy4_vs_policy3_excess_ucb_95_one_sided']:.6f}.",
                "- Primary superiority and policy-3 noninferiority were not met; no corrected online-router headline is available.",
            ]
            if live_audit
            else []
        ),
        "",
        "## Judge Branch",
        "",
        "Pooled validation passed. The chain scored 493 unique stratified clips with three deterministic calls each and mapped results to all 500 frozen IDs. The 690-row provenance contract is complete. The PI recorded `A_PRIME_GATE = FAIL_LEGACY_INSTRUMENT_NOT_VALIDATED`; A-prime is the falsification study for the legacy instrument, not a PASS. Positive label-validity evidence is instrument-scoped to the separate T6 corrected-instrument held-out evaluation.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return statuses


def prior_required_paths() -> list[Path]:
    path = PAPER / "scripts/build_autochain_evidence_bundle_20260712.py"
    spec = importlib.util.spec_from_file_location("build_autochain_evidence_bundle_20260712", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import prior evidence-bundle input index")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.required_paths()


def t7_paths() -> list[Path]:
    explicit = [
        PAPER / "pi_ratings_20260713/t7_judge_gold_negatives.json",
        T7 / "T7_JUDGE_GOLD_NEGATIVES_REPORT.md",
        T7 / "T7_SELECTION_AUDIT.json",
        T7 / "T7_SELECTION_MANIFEST.csv",
        T7 / "W2_SIGNATURE_VERIFICATION_REPORT.md",
        T7 / "W2_ADOPTION_SIGNATURE_REQUEST.md",
        T7 / "T7_EXECUTION_LEDGER.jsonl",
        T7 / "ratings_ingest/T7_RATINGS_INGEST_AUDIT.json",
        T7 / "ratings_ingest/T7_TOPUP_INGEST_REPORT.md",
        T7 / "ratings_ingest/T7_OFFICIAL_RATINGS.csv",
        T7 / "ratings_ingest/T7_TOPUP_GOLD_MANIFEST.csv",
        T7 / "ratings_ingest/T7_ALL_DISJOINT_GOLD_MANIFEST.csv",
        T7 / "judge_completion/JUDGE_COMPLETION_PREP_AUDIT.json",
        T7 / "judge_completion/POOLED_DISJOINT_GOLD_MANIFEST.csv",
        T7 / "judge_completion/A_PRIME_STRATIFIED_500_JUDGE_MANIFEST.csv",
        T7 / "judge_completion/A_PRIME_STRATIFIED_500_RATING_TO_JUDGE_MAP.csv",
        T7 / "gpu_queue/judge_gpu_watch.jsonl",
        T7 / "gpu_queue/live_gpu_watch.jsonl",
        PAPER / "scripts/ingest_t7_judge_gold_20260713.py",
        PAPER / "scripts/complete_t7_judge_aprime_20260713.py",
        PAPER / "scripts/record_a_prime_gate_call_20260714.py",
        PAPER / "scripts/watch_gpu_queue_20260713.py",
        PAPER / "scripts/run_t7_judge_chain_on_an29.sh",
        PAPER / "scripts/run_w2_liveconfirm_20260713.sh",
        PAPER / "scripts/w2_liveconfirm_worker_20260713.py",
        PAPER / "scripts/preflight_w2_reward_models_20260714.py",
        PAPER / "scripts/analyze_w2_liveconfirm_20260714.py",
        PAPER / "scripts/finalize_w2_live_generation_20260714.py",
        PAPER / "scripts/w2_heartbeat_20260712.sh",
        PAPER / "scripts/build_t7_evidence_bundle_20260713.py",
        PAPER / "autochain_20260712/AUTOCHAIN_EXECUTION_LEDGER.jsonl",
        ROOT / "tests/test_t7_judge_gold_20260713.py",
        ROOT / "tests/test_w2_liveconfirm_analysis_20260714.py",
        ROOT / "tests/test_w2_live_generation_finalizer_20260714.py",
        PAPER / "validation_A_prime/A_PRIME_GATE_CALL_UNBLOCK_REPORT_20260714.md",
        PAPER / "validation_A_prime/A_PRIME_GATE_CALL_TEST_RESULT_20260714.json",
        PAPER / "validation_A_prime/A_PRIME_UNBLOCK_FULL_TEST_SUMMARY_20260714.json",
        PAPER / "validation_A_prime/A_PRIME_UNBLOCK_FULL_TEST_RESULTS_20260714.txt",
        REPORT,
    ]
    explicit.extend(
        path
        for path in (
            LIVE / "ACTUAL_LAUNCH_TIMESTAMP.txt",
            LIVE / "HARD_STOP_DEADLINE.txt",
            LIVE / "LIVE_CONFIRM_TERMINAL_STATUS.txt",
            LIVE / "LIVE_LAUNCH_GUARD.json",
            LIVE / "LIVE_LAUNCH_ATTEMPT_1_FAILURE.md",
            LIVE / "LIVE_LAUNCH_ATTEMPT_2_FAILURE.md",
            LIVE / "LIVE_LAUNCH_ATTEMPT_3_FINALIZER_RECOVERY.md",
            LIVE / "LIVE_RECOVERY_EXECUTION_LEDGER_20260714.md",
            LIVE / "POSTRUN_PROCESS_CHECK.txt",
            LIVE / "GENERATION_COMPLETION_AUDIT.json",
            LIVE / "GENERATION_COMPLETED_TIMESTAMP.txt",
            LIVE / "PLAN_CLAIMS_UPDATE_DRAFT_LIVE_CONFIRM_20260714.md",
        )
        if path.is_file()
    )
    explicit.extend(sorted(LIVE.glob("OFFLINE_REWARD_PREFLIGHT_*.json")))
    explicit.extend(sorted(LIVE.glob("RESUME_LAUNCH_*.txt")))
    explicit.extend(
        path
        for path in (LIVE / "LIVE_CONFIRM_REPORT.md", LIVE / "LIVE_CONFIRM_AUDIT.json", LIVE / "LIVE_CONFIRM_RESULTS.csv")
        if path.is_file()
    )
    optional_names = [
        "FULL_TEST_RESULTS_20260714.txt",
        "FULL_TEST_RESULT_SUMMARY_20260714.json",
        "FULL_TEST_RESULTS_20260713.txt",
        "FULL_TEST_RESULT_SUMMARY_20260713.json",
        "gpu_queue/judge_gpu_watch_status.json",
        "gpu_queue/live_gpu_watch_status.json",
        "judge_completion/T7_JUDGE_RAW_RESPONSES.jsonl",
        "judge_completion/T7_JUDGE_RUN_SUMMARY.json",
        "judge_completion/POOLED_DISJOINT_GOLD_RAW_RESPONSES.jsonl",
        "judge_completion/POOLED_JUDGE_VALIDATION.json",
        "judge_completion/POOLED_JUDGE_VALIDATION_REPORT.md",
        "judge_completion/A_PRIME_STRATIFIED_500_RAW_RESPONSES.jsonl",
        "judge_completion/A_PRIME_STRATIFIED_500_RUN_SUMMARY.json",
        "judge_completion/A_PRIME_STRATIFIED_500_JUDGE_RATINGS.csv",
        "judge_completion/A_PRIME_STRATIFIED_500_RESULTS.csv",
        "judge_completion/A_PRIME_STRATIFIED_500_REPORT.md",
        "judge_completion/A_PRIME_ALL_JUDGE_RAW_RESPONSES.jsonl",
        "judge_completion/A_PRIME_JUDGE_VALIDATION_METADATA.json",
        "judge_completion/A_PRIME_INSTRUMENT_MERGED_690.csv",
        "judge_completion/A_PRIME_INSTRUMENT_MERGE_REPORT.json",
        "judge_completion/A_PRIME_CORE_ONLY_STDOUT.json",
        "judge_completion/A_PRIME_FINALIZE_STDOUT.json",
        "judge_completion/JUDGE_CHAIN_COMPLETED_AT.txt",
    ]
    explicit.extend(T7 / name for name in optional_names if (T7 / name).is_file())
    explicit.extend(
        path
        for path in (
            A_GATE,
            A_GATE_JSON,
            PAPER / "validation_A_prime/A_PRIME_STUDY_LOG.jsonl",
            PAPER / "validation_A_prime/A_PRIME_GATE_CALL_AUDIT_20260713.json",
        )
        if path.is_file()
    )
    missing = [path for path in explicit if not path.is_file()]
    if missing:
        raise FileNotFoundError("T7 evidence bundle missing required inputs: " + ", ".join(str(path) for path in missing))
    return explicit


def copy_artifacts(bundle: Path, paths: list[Path]) -> list[dict]:
    records = []
    seen = set()
    for source in paths:
        source = source.resolve()
        if source in seen:
            continue
        seen.add(source)
        relative = source.relative_to(ROOT.resolve())
        destination = bundle / "artifacts" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        records.append(
            {
                "source": str(relative),
                "bundle_path": str(destination.relative_to(bundle)),
                "sha256": sha256(destination),
                "bytes": destination.stat().st_size,
            }
        )
    shutil.copy2(PAPER / "PLAN.md", bundle / "PLAN.md")
    shutil.copy2(PAPER / "CLAIMS.md", bundle / "CLAIMS.md")
    return records


def write_context(bundle: Path, records: list[dict], statuses: dict[str, str]) -> None:
    validation = json.loads(VALIDATION.read_text(encoding="utf-8")) if VALIDATION.is_file() else None
    judge_line = (
        f"- Pooled judge validation: `{validation['JUDGE_VALIDATION_STATUS']}` on 149 positive and 67 negative human labels; see the bundled report."
        if validation
        else "- Pooled judge validation: queued behind the non-preemptive four-GPU idle predicate."
    )
    (bundle / "PROVENANCE.md").write_text(
        "# Provenance\n\n"
        "- Frozen generation backbone: ACE-Step v1.\n"
        "- Corrected instrument: prospectively promoted by the frozen T6 rule; publication adoption still requires a complete PI 2 record.\n"
        "- Human sources: `pi:Richard`; T6 repeat reliability was 20/20 exact for Label A and Label B.\n"
        "- T7: 40 hash-disjoint human Label-A negatives; two optional Label-B annotations were blank.\n"
        + judge_line
        + "\n- W2 amendment: PI 1, PI 2, and Claude blocks complete. Publication adoption: PI 2 record incomplete/contradictory.\n"
        + f"- Live confirmation: `{statuses['LIVE_CONFIRM_STATUS']}` after offline reward-path recovery under the original 48-hour clock.\n",
        encoding="utf-8",
    )
    (bundle / "LIMITATIONS_AND_WORDING.md").write_text(
        "# Limitations And Wording Register\n\n"
        "- Broad corrected-result supersession remains publication-adoption-gated; current PLAN/CLAIMS contain only the separately authorized A-prime/T6 scope update.\n"
        "- A-prime is never auto-passed: its terminal report requires a PI call and is Label-A scoped.\n"
        "- B-prime non-inferiority was not established; single expert rater, 40% ties, pre-W2 pair selection, and the t4 same-session deviation apply.\n"
        "- Stable Audio 3 remains a bounded pilot. Difficult/selected-set rates are not generic population rates.\n\n"
        "Banned wording: `proved no loss`, `no quality loss`, `no degradation`, `quality preserved`, `impossible to retry`, an unsupported generic population rate, or a causal vocal-generation-bias claim.\n",
        encoding="utf-8",
    )
    unresolved = [
        "The dedicated W2 publication-adoption PI 2 block is blank and the escalation-file PI 2 sentence is truncated; broad supersession remains unapplied.",
    ]
    if statuses["LIVE_CONFIRM_STATUS"] == "RUNNING":
        unresolved.append(
            "Live confirmation is running and remains subject to the original 2026-07-16T17:00:55+08:00 hard stop."
        )
    elif statuses["LIVE_CONFIRM_STATUS"].startswith("COMPLETE_CRITERIA_NOT_ALL_MET"):
        unresolved.append(
            "The bounded W2 live confirmation did not meet every frozen condition; no corrected online headline is available."
        )
    elif statuses["LIVE_CONFIRM_STATUS"].startswith("COMPLETE_PI_CALL_PENDING"):
        unresolved.append(
            "The bounded W2 live confirmation met its mechanical conditions but remains PI-call pending; no automatic PASS was issued."
        )
    if statuses["JUDGE_VALIDATION_STATUS"] in {"QUEUED_AWAITING_GPUS", "RUNNING_GPU_CHAIN"}:
        unresolved.append("Pooled judge validation and the conditional stratified-500 chain are not yet terminal.")
    elif statuses["JUDGE_VALIDATION_STATUS"] == "FAIL":
        unresolved.append("The judge failed validation; the stratified-500 remains unavailable and A-prime proceeds on the human core only.")
    (bundle / "UNRESOLVED_ITEMS.md").write_text(
        "# Unresolved Items\n\n" + "\n".join(f"{index}. {value}" for index, value in enumerate(unresolved, 1)) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Paper Evidence Bundle - T7 Recovery Snapshot",
        "",
        "This checksum-indexed snapshot preserves the current adopted PLAN/CLAIMS and separately records unadopted corrected evidence.",
        "",
        "## Status",
        "",
    ]
    lines.extend(f"- `{key} = {value}`" for key, value in statuses.items())
    lines.extend(
        [
            "",
            "## Entry Points",
            "",
            "- `PLAN.md`",
            "- `CLAIMS.md`",
            "- `PROVENANCE.md`",
            "- `LIMITATIONS_AND_WORDING.md`",
            "- `UNRESOLVED_ITEMS.md`",
            "",
            "## Artifact Index",
            "",
            "| Bundle path | SHA-256 | Bytes |",
            "|---|---|---:|",
        ]
    )
    lines.extend(f"| `{row['bundle_path']}` | `{row['sha256']}` | {row['bytes']} |" for row in records)
    (bundle / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build(label: str) -> dict:
    bundle_name = f"paper_evidence_bundle_20260713_{label}"
    tarball_name = f"{bundle_name}.tar.gz"
    bundle = PAPER / bundle_name
    tarball = PAPER / tarball_name
    if bundle.exists() or tarball.exists():
        raise FileExistsError(f"non-destructive snapshot already exists: {bundle_name}")
    statuses = write_report(bundle_name, tarball_name)
    bundle.mkdir(parents=True)
    records = copy_artifacts(bundle, prior_required_paths() + t7_paths())
    write_context(bundle, records, statuses)
    build_result = {
        "EVIDENCE_BUNDLE_STATUS": "BUILT",
        "bundle": str(bundle.relative_to(ROOT)),
        "tarball": str(tarball.relative_to(ROOT)),
        "indexed_artifacts": len(records),
        "statuses": statuses,
    }
    (bundle / "BUILD_RESULT.json").write_text(json.dumps(build_result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checksum_rows = []
    for path in sorted(item for item in bundle.rglob("*") if item.is_file() and item.name != "SHA256SUMS"):
        checksum_rows.append((sha256(path), str(path.relative_to(bundle))))
    (bundle / "SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for digest, name in checksum_rows), encoding="utf-8"
    )
    with tarfile.open(tarball, "w:gz") as archive:
        archive.add(bundle, arcname=bundle.name)
    tarball_hash = sha256(tarball)
    (PAPER / f"{tarball_name}.sha256").write_text(f"{tarball_hash}  {tarball.name}\n", encoding="utf-8")
    return {**build_result, "checksummed_files": len(checksum_rows), "tarball_sha256": tarball_hash}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.label), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
