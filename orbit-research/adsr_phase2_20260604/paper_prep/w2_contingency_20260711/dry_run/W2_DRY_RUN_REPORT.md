# W2 Current-Instrument Dry Run

`W2_SCAFFOLD_STATUS = DRY_RUN_PASS`

## Result

- Host/GPU: `an12`, physical GPU 4 (`CUDA_VISIBLE_DEVICES=4`).
- Instrument: `current_demucs_htdemucs_threshold_0p1791`.
- Cohort: frozen Stage 3 intervention FLACs.
- Rows: 50 selected deterministically by manifest record ID.
- Successful/failed: 50/0.
- Every result carries `dry_run_only=true`.
- Frozen/current label agreement: 50/50; this is a plumbing check, not a
  label-fidelity claim.
- Aggregate scoring time including model load: 93.048 seconds.
- Observed ratio range: 0.000001 to 0.999952.

The condition mix was 12 `vocal_hints`, 10 `vocal_both`, 9 `instr_text`, 8
`instr_sampler`, 6 `instr_both`, and 5 `vocal_guidance` rows. The downstream
diff generator emitted six condition rows with no automatic PLAN change.

## Preserved Failed Attempt

The first bounded attempt selected candidate-spine paths and produced 50/50
`LibsndfileError` failures. Investigation showed that 4,095/4,096 spine media
entries are dangling links. That failed ledger is preserved at
`paper_prep/w2_contingency_20260711/dry_run/failed_candidate_spine_20260711/W2_DRY_RUN_LEDGER.jsonl`.
The manifest now requires a real file target before marking media available.

## Evidence

- Inventory: `paper_prep/w2_contingency_20260711/W2_RETAINED_AUDIO_INVENTORY.json`
- Successful ledger: `paper_prep/w2_contingency_20260711/dry_run/W2_DRY_RUN_LEDGER.jsonl`
- Diff CSV: `paper_prep/w2_contingency_20260711/dry_run/W2_DRY_RUN_DIFF.csv`
- Diff report: `paper_prep/w2_contingency_20260711/dry_run/W2_DRY_RUN_DIFF_REPORT.md`

No evidence label was changed and no Section 7 or `PLAN.md` status was edited.
