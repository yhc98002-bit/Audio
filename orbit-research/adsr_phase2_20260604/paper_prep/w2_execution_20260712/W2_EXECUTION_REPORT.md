# W2 Execution Report

Date: 2026-07-12
Scope: frozen dual-PI W2 execution package, exact-runtime spine recovery,
instrumental factorial, calibration preparation, and gated downstream tooling.

## Status Contract

W2_AMENDMENT_STATUS = DRAFTED_AWAITING_SIGNATURE
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/W2_AMENDMENT_20260712.md`

SPINE_REGEN_STATUS = COMPLETE_AUDIT_PASS
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/spine_reconstruction_torch251_recovery/SPINE_RECONSTRUCTION_AUDIT.md`, `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/spine_reconstruction_torch251_recovery/SPINE_RECONSTRUCTION_AUDIT.json`

CALIBRATION_PACK_STATUS = READY_BLOCKED_ON_SIGNATURE
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/calibration_torch251_recovery/T6_CALIBRATION_PACK_REPORT.md`, `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/calibration_torch251_recovery/W2_CALIBRATION_SELECTION_AUDIT.json`

FACTORIAL_STATUS = PREREGISTERED_GENERATED
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/factorial/FACTORIAL_PREREGISTRATION.md`, `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/factorial/FACTORIAL_GENERATION_AUDIT.json`, `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/factorial/FACTORIAL_CANONICAL_READOUT.md`

PROMOTION_PIPELINE_STATUS = READY_BLOCKED_ON_RATINGS
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/analysis/W2_PROMOTION_PIPELINE_REPORT.md`, `orbit-research/adsr_phase2_20260604/paper_prep/scripts/w2_promotion_pipeline_20260712.py`, `tests/test_w2_promotion_pipeline_20260712.py`

RECOMPUTE_PIPELINE_STATUS = READY
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/analysis_torch251_recovery/W2_RECOMPUTE_REPORT.md`, `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/analysis_torch251_recovery/W2_PUBLICATION_RATES.csv`, `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/analysis_torch251_recovery/W2_PROMPT_LEVEL_ECDF.csv`

EVPD_LIVECONFIRM_PREP = READY_BLOCKED_ON_PROMOTION
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/evpd_liveconfirm_torch251_recovery/EVPD_LIVECONFIRM_PREP_REPORT.md`, `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/evpd_liveconfirm_torch251_recovery/CORRECTED_EVPD_TRAINING_MANIFEST.csv`, `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/evpd_liveconfirm_torch251_recovery/LIVE_CONFIRM_POLICY_FREEZE.json`

JUDGE_TRACK_STATUS = READY_BLOCKED_ON_GOLD
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/judge_track/JUDGE_TRACK_PLAN.md`, `orbit-research/adsr_phase2_20260604/paper_prep/scripts/w2_judge_track_20260712.py`

HOUSEKEEPING_STATUS = DONE
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/housekeeping/W2_HOUSEKEEPING_REPORT.md`, `orbit-research/adsr_phase2_20260604/paper_prep/LIGHT_PLAN_ADDENDUM_UNUSED_NOTE_20260712.md`, `orbit-research/adsr_phase2_20260604/paper_prep/rater_bundles_20260711/SHA256SUMS`

TEST_SUITE_STATUS = PASS
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/W2_TEST_RESULTS_FINAL_COMPLETE.txt`, `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/W2_TEST_RESULTS_FINAL_COMPLETE.exit`, `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/W2_TEST_RESULTS_FINAL_COMPLETE_METADATA.json`

## Spine Recovery

The first 4,096-row reconstruction was generated under torch 2.7.1+cu126 and
failed exact fidelity: 0/50 controls, 0/1 survivor, and 85 historical label
flips. That cohort and its audit remain preserved and blocked.

The recovery used an isolated torch/torchaudio 2.5.1+cu121 environment. A
preregistered probe matched 50/50 controls and 1/1 survivor exactly before the
full replay was authorized. The full audit then found:

- 4,096/4,096 unique successful generation rows;
- 4,096/4,096 unique successful current/candidate score rows;
- 4,095 reconstructed missing candidates plus one survivor replay;
- 50/50 independent controls exact by decoded-audio hash;
- 1/1 surviving original exact by decoded-audio hash;
- zero missing, checksum-invalid, near-silent, short, or undecodable media;
- zero duplicate or conflicting score rows; and
- 15/4,096 historical-versus-recomputed current-detector label flips,
  disclosed as a scoring comparison rather than hidden as a fidelity failure.

The candidate Demucs-and-PANNs instrument remains sensitivity-only. No
instrument was promoted and `PLAN.md` was not changed.

## Calibration Package

The replacement t6 package contains 200 calibration presentations plus one
excluded adjudication appendix. Its selection retains all inclusion
probabilities, the 60/100 train/held-out split, 20 transport rows, 20 hidden
repeats, 40-row simple-random anchor, and 200-row reserve. All 201 media files
match checksums, decode above one second, and pass the leak and staged-reveal
audits. Provenance is restricted to `pi:Richard`.

Exact-runtime scores changed the deterministic selection: overlap with the
blocked first package is 48/60 train, 85/100 held-out, 20/20 transport, 12/20
repeat presentations, and 171/200 reserve rows. Only the recovery package may
be rated, and only after both amendment signatures.

## Factorial And Analysis

The canonical factorial contains 3,072 clips: 32 prompts x 6 conditions x 16
common-random-number seeds. A lexical audit invalidated the first 1,024
positive-condition clips; those remain preserved as sensitivity data and were
replaced by a preregistered 1,024-row corrected cohort. The canonical candidate
violation rate is 0.568359 for plain baseline and 0.332031 for
`positive_sampler`; these are candidate-instrument sensitivity rates, not
promoted results. The blinded 20-pair PI spot-check package is staged.

The exact-runtime recompute contains 27,966 target rows, 28 publication rows,
and 876 prompt-ECDF rows. A first versioned assemble attempt failed closed
because the output root also redirected the frozen Batch-3 input. The failed
attempt is preserved; input/output roots were separated, four tests passed,
and the complete rerun used all 1,342 Batch-3 scores. No incomplete override
was used.

The EVPD manifest contains all 4,096 scored candidates with zero prompt overlap
across 210/46/256 train/validation/test prompts. The 512-unit live-confirm
manifest and policy hash are frozen, but training and generation remain gated
on signatures and corrected-instrument promotion. The judge track remains
blocked on disjoint gold.

## Node Utilization

`an29` ran the factorial, exact-runtime environment recovery, probe, replay,
and score shards. `an12` ran spine/probe work and dedicated score-shard
rotations on free GPUs 5-7. Five pre-existing BlindGain jobs on an12 GPUs 0-4
were not counted as ADSR progress and were not interrupted. Replay workers were
relocated whenever observed free memory approached the safety floor; no
existing process overflowed. The detailed timeline and the corrected heartbeat
telemetry limitation are in `paper_prep/NODE_SATURATION_AUDIT_20260712.md`.

## Bundle Checksums

| artifact | use | SHA256 |
|---|---|---|
| `paper_prep/rater_bundles_20260712/t6_calibration_torch251_recovery.zip` | only rating-eligible t6 package after both signatures | `2b8b0990e627075ec7ec438b69049825737a827c456c479bea2b34d11762afb8` |
| `paper_prep/w2_execution_20260712/factorial/FACTORIAL_PI_SPOTCHECK_BUNDLE.zip` | delayed 20-pair PI factorial spot check | `58ac37bb8c5abb344efd2fcf002ef5c7e21ac8fee63cca5db31e8366a326e270` |
| `paper_prep/rater_bundles_20260712/t6_calibration.zip` | blocked first package; do not rate | `0123169f060d7535dea9fb6d4300a76d23f8e17bba38d1922e8b948847c94b3f` |
| `paper_prep/rater_bundles_20260712/t6_calibration_pre_spine_fidelity_block.zip` | preserved pre-block historical package | `d033b81c7760e03f0bcec768489dd5faac2ccc2bb07359736c4e77f6a12cbfaf` |

## Key Artifact Checksums

| artifact | SHA256 |
|---|---|
| recovery spine audit JSON | `e747bacdcded48383ec37425541d1b9b17804f6f471eab63be93f0123cf91196` |
| recovery spine audit Markdown | `d6609794031205ecf30c8eda3d2cfd0ada2153319823967db2a853b8dc0f18fd` |
| exact-runtime target score table | `e5d5a27ca9c10c0f9303e18f0c0afccecb5f045bb515f87c07e6f295eff1d4df` |
| exact-runtime calibration selection | `fc0a0aaaaa052af3958e3e5703e120868b0ee930c9042299dd11a41b12292136` |

## Commits And Tests

| commit | purpose |
|---|---|
| `25a4853` | instrumental factorial package |
| `79acbb0` | fail-close invalid spine and freeze recovery probe |
| `99c88de` | exact torch-2.5.1 runtime recovery |
| `7f63ab7` | 51/51 probe pass and full replay freeze |
| `a2655a1` | freeze 4,096-row exact replay generation evidence |
| `a332581` | complete exact-runtime audit, downstream rebuild, and evidence package |

The login-system-Python test attempt failed at collection because that
interpreter lacks torch; its log is preserved. The authoritative rerun used
the project `audio-prm` interpreter and passed 298/298 tests with exit 0.

## Human Action Gate

The next permissible human action is for both PIs to sign
`paper_prep/W2_AMENDMENT_20260712.md`. Only then may Richard open
`paper_prep/rater_bundles_20260712/t6_calibration_torch251_recovery.zip` and
rate it. Ratings still cannot auto-promote an instrument: reliability,
train-only selection, held-out bounds, and dual-PI adoption remain mandatory.
