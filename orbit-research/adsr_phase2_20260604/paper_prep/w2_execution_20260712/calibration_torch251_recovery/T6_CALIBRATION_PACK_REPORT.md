# W2 t6 Calibration Package: Exact-Runtime Recovery

`CALIBRATION_PACK_STATUS = READY_BLOCKED_ON_SIGNATURE`

This package is the rating-eligible replacement for the fail-closed
torch-2.7.1 package. Its spine inputs come only from the recovery root whose
full audit records `SPINE_REGEN_STATUS = COMPLETE_AUDIT_PASS`. Do not start
ratings until `W2_AMENDMENT_20260712.md` records both PI signatures.

## Frozen Design

- 200 calibration presentations: 60 train, 100 held-out, 20 transport, and 20
  hidden repeats.
- 180 unique calibration clips plus one separately excluded pending-
  adjudication appendix presentation.
- Held-out proxy composition: 60 Label-B negatives and 40 positives.
- 40-row simple-random held-out anchor.
- Transport rows: 7 N2, 7 Stage 3, and 6 Batch-3 keeps.
- 200-row ordered reserve.
- All 192 cross-product cells retained, including 136 empty cells.
- Inclusion, selection-stage, and final inclusion probabilities present.

The exact-runtime score changes required a fresh deterministic selection. Of
the unique IDs in the fail-closed first package, overlap is 48/60 train,
85/100 held-out, 20/20 transport, 12/20 repeat presentations, and 171/200
reserve rows. The old package is therefore not interchangeable with this one
and remains preserved only as blocked history.

## Integrity

- Selection audit: PASS.
- Bundle rows: 201 (200 calibration plus one excluded appendix).
- Media checksum matches: 201/201.
- Decodable media longer than one second: 201/201.
- Minimum duration: 29.9073125 seconds.
- Sample rate: 201/201 at 48,000 Hz.
- Admin-field leak test: PASS.
- Staged Label-A, request reveal, then Label-B flow: PASS.
- Rating source restricted to `pi:Richard`: PASS.
- Raw `ADSR_BLINDING_NONCE` exposed in bundle/admin outputs: no.

## Handoff

- Bundle directory: `paper_prep/rater_bundles_20260712/t6_calibration_torch251_recovery/`
- Zip: `paper_prep/rater_bundles_20260712/t6_calibration_torch251_recovery.zip`
- Zip SHA256: `2b8b0990e627075ec7ec438b69049825737a827c456c479bea2b34d11762afb8`
- Keys-side admin: `paper_prep/rater_admin_keys_20260712/t6_calibration_torch251_recovery/T6_CALIBRATION_ADMIN.csv`
- Selection: `paper_prep/w2_execution_20260712/calibration_torch251_recovery/W2_CALIBRATION_SELECTION_MANIFEST.csv`
- Sampling frame: `paper_prep/w2_execution_20260712/calibration_torch251_recovery/W2_CALIBRATION_SAMPLING_FRAME.csv`
- Selection audit: `paper_prep/w2_execution_20260712/calibration_torch251_recovery/W2_CALIBRATION_SELECTION_AUDIT.json`

The scorer remains mechanically ordered: reliability first, then train-only
instrument fitting, then one held-out evaluation. Building this package does
not expose labels, promote an instrument, or change `PLAN.md`.
