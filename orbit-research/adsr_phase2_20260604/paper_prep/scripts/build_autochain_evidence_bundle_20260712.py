#!/usr/bin/env python3
"""Build the checksum-indexed co-PI writing bundle for the T6 autochain."""

from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"repository root not found from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
PAPER = ROOT / "paper_prep"
BUNDLE = PAPER / "paper_evidence_bundle_20260712"
TARBALL = PAPER / "paper_evidence_bundle_20260712.tar.gz"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def required_paths() -> list[Path]:
    explicit = [
        PAPER / "PLAN.md",
        PAPER / "CLAIMS.md",
        PAPER / "W2_AMENDMENT_20260712.md",
        PAPER / "HUMAN_STUDY_CRITERIA_AMENDMENT_20260709.md",
        PAPER / "autochain_20260712/T6_INGEST_AUDIT.json",
        PAPER / "autochain_20260712/T6_RELIABILITY_RESULT.json",
        PAPER / "autochain_20260712/T6_RELIABILITY_REPORT.md",
        PAPER / "autochain_20260712/T6_PROMOTION_RESULT.json",
        PAPER / "autochain_20260712/T6_PROMOTION_REPORT.md",
        PAPER / "autochain_20260712/T6_PROMOTION_ESCALATION.md",
        PAPER / "autochain_20260712/T6_HELDOUT_EXPOSURE_RECORD.json",
        PAPER / "autochain_20260712/LIVE_CONFIRM_STATUS_REPORT.md",
        PAPER / "autochain_20260712/LIVE_CONFIRM_GUARD_TRACEBACK.txt",
        PAPER / "autochain_20260712/recompute/CALIBRATION_MODEL_AUDIT.json",
        PAPER / "autochain_20260712/recompute/CORRECTED_PUBLICATION_RATES.csv",
        PAPER / "autochain_20260712/recompute/CORRECTED_PROMPT_RATES.csv",
        PAPER / "autochain_20260712/recompute/CORRECTED_PROMPT_ECDFS.csv",
        PAPER / "autochain_20260712/recompute/CORRECTED_RECOMPUTE_REPORT.md",
        PAPER / "autochain_20260712/recompute/PLAN_UPDATE_DRAFT.md",
        PAPER / "autochain_20260712/recompute/CLAIMS_UPDATE_DRAFT.md",
        PAPER / "autochain_20260712/recompute/DUAL_PI_ADOPTION_PACKET.md",
        PAPER / "autochain_20260712/recompute/corrected_prevalence_summary.png",
        PAPER / "autochain_20260712/recompute/corrected_prevalence_summary.pdf",
        PAPER / "autochain_20260712/factorial/FACTORIAL_MODEL_AUDIT.json",
        PAPER / "autochain_20260712/factorial/FACTORIAL_CONDITION_RESULTS.csv",
        PAPER / "autochain_20260712/factorial/FACTORIAL_INTERACTION_CONTRASTS.csv",
        PAPER / "autochain_20260712/factorial/FACTORIAL_SCORING_REPORT.md",
        PAPER / "autochain_20260712/judge_aprime/JUDGE_LABEL_A_GOLD_BUILD.json",
        PAPER / "autochain_20260712/judge_aprime/JUDGE_LABEL_A_VALIDATION.json",
        PAPER / "autochain_20260712/judge_aprime/JUDGE_LABEL_A_VALIDATION_REPORT.md",
        PAPER / "autochain_20260712/judge_aprime/JUDGE_NEGATIVE_GOLD_TOPUP_ESCALATION.md",
        PAPER / "validation_A_prime/A_PRIME_GATE_REPORT_20260712.md",
        PAPER / "validation_B_prime/B_PRIME_GATE_REPORT_20260712.md",
        PAPER / "pi_ratings_20260712/DROP2_REPORT.md",
        PAPER / "w2_execution_20260712/spine_reconstruction_torch251_recovery/SPINE_RECONSTRUCTION_AUDIT.md",
        PAPER / "w2_execution_20260712/factorial/FACTORIAL_CANONICAL_READOUT.md",
        PAPER / "w2_execution_20260712/factorial/FACTORIAL_PI_SPOTCHECK_MANIFEST.csv",
        PAPER / "w2_execution_20260712/factorial/FACTORIAL_PI_SPOTCHECK_SHA256SUMS",
        PAPER / "w2_execution_20260712/evpd_liveconfirm_torch251_recovery/EVPD_LIVECONFIRM_PREP_REPORT.md",
        PAPER / "w2_execution_20260712/evpd_liveconfirm_torch251_recovery/CORRECTED_EVPD_REPORT.md",
        PAPER / "w2_execution_20260712/evpd_liveconfirm_torch251_recovery/corrected_evpd_sigma08.joblib",
        PAPER / "w2_execution_20260712/evpd_liveconfirm_torch251_recovery/LIVE_CONFIRM_POLICY_FREEZE.json",
        PAPER / "stage3_intervention_20260707/STAGE3_PUBLICATION_READOUT.md",
        PAPER / "population_retry_20260707/N2_PUBLICATION_READOUT.md",
        PAPER / "analysis/efficiency_claims.md",
        PAPER / "clap_fidelity/CLAP_FIDELITY_EXPANDED_REPORT.md",
        PAPER / "router_replay/ROUTER_REPLAY_CV_REPORT.md",
        PAPER / "sao/stable_audio_3_medium/SA3_DOWNLOAD_REPORT.md",
        PAPER / "sao/stable_audio_3_medium/SA3_ENV_REPORT.md",
        PAPER / "sao/stable_audio_3_medium/smoke/SA3_SMOKE_REPORT.md",
        PAPER / "sao/stable_audio_3_medium/prevalence_full500/SA3_PREVALENCE_REPORT.md",
        PAPER / "sao/stable_audio_3_medium/observability/SA3_OBSERVABILITY_REPORT.md",
        PAPER / "sao/stable_audio_3_medium/intervention/SA3_INTERVENTION_REPORT.md",
    ]
    missing = [path for path in explicit if not path.is_file()]
    if missing:
        raise FileNotFoundError("evidence bundle missing required inputs: " + ", ".join(str(path) for path in missing))
    return explicit


def copy_artifacts(paths: list[Path]) -> list[dict]:
    records = []
    for source in paths:
        relative = source.relative_to(ROOT)
        destination = BUNDLE / "artifacts" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        records.append(
            {
                "source": str(relative),
                "bundle_path": str(destination.relative_to(BUNDLE)),
                "sha256": sha256(destination),
                "bytes": destination.stat().st_size,
            }
        )
    shutil.copy2(PAPER / "PLAN.md", BUNDLE / "PLAN.md")
    shutil.copy2(PAPER / "CLAIMS.md", BUNDLE / "CLAIMS.md")
    return records


def write_context(records: list[dict]) -> None:
    promotion = json.loads((PAPER / "autochain_20260712/T6_PROMOTION_RESULT.json").read_text())
    validation = json.loads((PAPER / "autochain_20260712/judge_aprime/JUDGE_LABEL_A_VALIDATION.json").read_text())
    (BUNDLE / "PROVENANCE.md").write_text(
        "# Provenance\n\n"
        "- Frozen generation backbone: ACE-Step v1.\n"
        "- Spine reconstruction: exact-runtime Torch 2.5.1 recovery; see the bundled reconstruction report.\n"
        "- Corrected instrument: train-selected Demucs/PANNs family "
        f"`{promotion['heldout']['selected_candidate']['family']}`; held-out labels exposed once.\n"
        "- Human source: `pi:Richard`; T6 reliability was 20/20 exact for Label A and Label B.\n"
        f"- Self-hosted judge: `{validation['model']}` served as `{validation['served_model']}` with three deterministic calls per clip.\n"
        "- W2 amendment signature state: `DRAFTED_AWAITING_SIGNATURE`; corrected results are draft supersession evidence only.\n",
        encoding="utf-8",
    )
    (BUNDLE / "LIMITATIONS_AND_WORDING.md").write_text(
        "# Limitations And Wording Register\n\n"
        "## Required limitations\n\n"
        "- Corrected instrument promotion is mechanical but not adopted: both W2 signatures are absent.\n"
        "- A-prime remains blocked because current PI gold has only 43 total Label-A negatives, below the frozen 50-negative judge-validation minimum.\n"
        "- B-prime non-inferiority was not established; single expert rater, 40% ties, pre-W2 pair selection, and the t4 same-session deviation apply.\n"
        "- Stable Audio 3 is a bounded pilot, not full second-backbone equivalence.\n"
        "- Difficult/selected test-set rates are not generic population rates.\n\n"
        "## Banned wording\n\n"
        "- proved no loss\n"
        "- no quality loss\n"
        "- no degradation\n"
        "- quality preserved\n"
        "- impossible to retry\n"
        "- generic population rate from the selected/difficult set\n"
        "- causal vocal-generation bias\n\n"
        "Use `rare / impractical to retry`, instrument-qualified quality wording, and `consistent with a vocal-generation bias`.\n",
        encoding="utf-8",
    )
    (BUNDLE / "UNRESOLVED_ITEMS.md").write_text(
        "# Unresolved Items\n\n"
        "1. Both PIs must sign/adopt W2 before corrected drafts can modify PLAN/CLAIMS or before EVPD/live confirmation can launch.\n"
        "2. At least seven additional unambiguous PI Label-A negatives are needed even if every available t1+t2+t6 negative enters a new disjoint validation design; the fresh T6 split alone is short by 23.\n"
        "3. A-prime stratified-500 calls and the instrument merge remain blocked on a validated judge.\n"
        "4. The existing 20-pair factorial spot check is staged but unrated.\n",
        encoding="utf-8",
    )
    lines = [
        "# Paper Evidence Bundle",
        "",
        "This is the co-PIs' checksum-indexed writing input. `PLAN.md` and `CLAIMS.md` are the current adopted files; files named `*_DRAFT` are not adopted.",
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
    lines.extend(f"| `{row['bundle_path']}` | `{row['sha256']}` | {row['bytes']} |" for row in records)
    (BUNDLE / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_checksums() -> list[tuple[str, str]]:
    rows = []
    for path in sorted(item for item in BUNDLE.rglob("*") if item.is_file() and item.name != "SHA256SUMS"):
        rows.append((sha256(path), str(path.relative_to(BUNDLE))))
    (BUNDLE / "SHA256SUMS").write_text("".join(f"{digest}  {name}\n" for digest, name in rows), encoding="utf-8")
    return rows


def build() -> dict:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    records = copy_artifacts(required_paths())
    write_context(records)
    manifest = {
        "EVIDENCE_BUNDLE_STATUS": "BUILT",
        "bundle": str(BUNDLE.relative_to(ROOT)),
        "tarball": str(TARBALL.relative_to(ROOT)),
        "indexed_artifacts": len(records),
        "tarball_checksum_location": "the invoking stdout/ledger record; SHA256SUMS covers bundle contents",
    }
    (BUNDLE / "BUILD_RESULT.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    checksums = write_checksums()
    with tarfile.open(TARBALL, "w:gz") as archive:
        archive.add(BUNDLE, arcname=BUNDLE.name)
    result = {
        **manifest,
        "tarball_sha256": sha256(TARBALL),
        "checksummed_files": len(checksums),
    }
    return result


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True))
