# BOLT Gate 0 Report

GATE0_STATUS = PASS
ENVIRONMENT_PARITY_STATUS = PASS
RESUME_EQUIVALENCE_STATUS = PASS
CONDITION_SWITCH_STATUS = PASS
FORK_STATUS = PASS
ACTUAL_NFE_STATUS = PASS
TRUE_ROLLOVER_STATUS = PASS
COMPLETION_RESERVE_STATUS = PASS
ZERO_SCORE_SELECTION_STATUS = PASS

Measured standard-generation NFE: `45`; pilot budget NFE: `90`.

Resume controls: `48/48`; Label-B flips: `0`; quality-floor flips: `0`.

True-rollover trace: `{"after_first_abort": 73, "after_second_abort": 56, "final_remaining": 11, "status": "PASS", "total_nfe": 90, "valid_completed_candidates": 1}`. Scheduler-step equivalent trace is 60 -> 48 -> 36 -> complete 30.

Fork eta: `0.025`. Detailed evidence: `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_FORK_CALIBRATION.csv` and `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_FORK_CALIBRATION_REPORT.md`.
