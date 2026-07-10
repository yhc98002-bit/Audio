from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "orbit-research/adsr_phase2_20260604/paper_prep/scripts/reconcile_a_prime_cardinality.py"
)
SPEC = importlib.util.spec_from_file_location("reconcile_a_prime_cardinality", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_transition_labels_distinguish_construct_drift_and_packaging_drift() -> None:
    assert MODULE.transition_labels(
        intended=True,
        stale=False,
        in_manifest_92=False,
        in_bucket_82=False,
        occurrence_count=1,
    ) == (
        "intended_case_omitted_by_wrong_detector_pair",
        "not_in_stale_100",
        "not_in_manifest_92",
    )
    assert MODULE.transition_labels(
        intended=False,
        stale=True,
        in_manifest_92=False,
        in_bucket_82=False,
        occurrence_count=2,
    ) == (
        "non_intended_case_added_by_wrong_detector_pair",
        "cross_reason_duplicate_removed_by_first_row_wins_dedup",
        "already_removed_or_reclassified_before_92",
    )
    assert MODULE.transition_labels(
        intended=True,
        stale=True,
        in_manifest_92=True,
        in_bucket_82=False,
        occurrence_count=1,
    ) == (
        "overlap_retained_but_construct_changed",
        "retained_after_dedup",
        "reclassified_by_extracted_agreement_spotcheck_path",
    )


def test_media_classification_fails_closed() -> None:
    assert MODULE.classify_media(None) == "unrecoverable"
    assert MODULE.classify_media({"original_media_available": "true"}) == "original"
    assert MODULE.classify_media(
        {
            "original_media_available": "false",
            "media_available": "true",
            "media_recovery_method": "copied_from_archive",
        }
    ) == "recovered-original"
    assert MODULE.classify_media(
        {
            "original_media_available": "false",
            "media_available": "true",
            "media_recovery_method": "regenerated_from_prompt_seed_ace_step_v1",
        }
    ) == "regenerated"
