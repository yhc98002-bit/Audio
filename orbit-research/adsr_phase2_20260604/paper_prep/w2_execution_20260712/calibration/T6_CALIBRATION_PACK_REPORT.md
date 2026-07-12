# W2 t6 Calibration Package

`CALIBRATION_PACK_STATUS = READY_BLOCKED_ON_SIGNATURE`

## Frozen Design

- Initial presentations: 200 (60 train, 100 held-out, 20 transport, and 20 hidden repeats).
- Unique calibration media: 180.
- Separately excluded appendix presentations: 1 pending adjudication clip.
- Held-out proxy composition: 60 Label-B negatives and 40 Label-B positives.
- Held-out simple-random anchor: 40 rows.
- Transport audit: 7 N2, 7 Stage 3, and 6 Batch-3 keep rows.
- Ordered class-count reserve: 200 rows, frozen keys-side and excluded from the initial bundle.
- Sampling frame: all 192 frozen cross-product cells retained, including 136 empty cells.
- Provenance accepted by the UI: `pi:Richard` only.

## Integrity

- Selection audit: PASS.
- Bundle leak audit: PASS.
- Staged Label-A then request-reveal then Label-B flow: PASS.
- Media checksum matches: 201/201.
- Decodable media longer than one second: 201/201.
- Minimum duration: 29.9073125 seconds.
- Sample rate: 201/201 at 48,000 Hz.
- Raw blinding nonce present in bundle/admin output: no.

## Build Recovery

The first bundle attempt stopped before creating media because the legacy decisive admin schema has `source_path` and `package_media_path`, while the initial resolver expected `packet_path` (`KeyError: 'packet_path'`). The resolver now accepts only an existing source/package path whose SHA256 matches the frozen admin row. The regression test and the second build passed; no media was regenerated.

## Local Handoff

- Bundle directory: `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion/orbit-research/adsr_phase2_20260604/paper_prep/rater_bundles_20260712/t6_calibration/`
- Zip: `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion/orbit-research/adsr_phase2_20260604/paper_prep/rater_bundles_20260712/t6_calibration.zip`
- Zip SHA256: `d033b81c7760e03f0bcec768489dd5faac2ccc2bb07359736c4e77f6a12cbfaf`
- Keys-side admin: `paper_prep/rater_admin_keys_20260712/t6_calibration/T6_CALIBRATION_ADMIN.csv`
- Frozen selection: `paper_prep/w2_execution_20260712/calibration/W2_CALIBRATION_SELECTION_MANIFEST.csv`
- Frozen frame: `paper_prep/w2_execution_20260712/calibration/W2_CALIBRATION_SAMPLING_FRAME.csv`

Do not open the bundle for ratings until `W2_AMENDMENT_20260712.md` records both PI signatures. The promotion scorer remains fail-closed and exposes train/held-out labels only in the frozen order after signature and reliability checks.
