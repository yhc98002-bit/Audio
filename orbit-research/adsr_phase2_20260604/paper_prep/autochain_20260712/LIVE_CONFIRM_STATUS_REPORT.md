# Corrected EVPD And Live Confirmation Status

`LIVE_CONFIRM_STATUS = BLOCKED_UNSIGNED_W2_AMENDMENT`

The corrected instrument passed its mechanical held-out promotion criteria, but
the W2 amendment remains `DRAFTED_AWAITING_SIGNATURE`. A direction-specific
Label-B EVPD model was fit as explicitly draft-only evidence; the frozen launch
guard was then run against the real amendment, promotion record, and policy
SHA-256 and exited nonzero before live generation.

- Guard exit: `1`.
- Exact cause: `W2 amendment is not signed by both PIs`.
- Prepared EVPD manifest: 4,096 reconstructed-spine rows.
- Draft EVPD validation/test balanced accuracy: 0.831660/0.833385; test AUC 0.915448.
- Prepared live manifest: 64 prompts x 4 policies x 2 repetitions = 512 units.
- Frozen policy SHA-256: `c6de82920857a220ede8d9d0391b445a94af7d721c662480044de7f70acb9134`.
- PLAN/CLAIMS changes: none.

Evidence:

- `paper_prep/autochain_20260712/LIVE_CONFIRM_GUARD_TRACEBACK.txt`
- `paper_prep/autochain_20260712/LIVE_CONFIRM_GUARD_EXIT.txt`
- `paper_prep/w2_execution_20260712/evpd_liveconfirm_torch251_recovery/CORRECTED_EVPD_TRAINING_MANIFEST.csv`
- `paper_prep/w2_execution_20260712/evpd_liveconfirm_torch251_recovery/CORRECTED_EVPD_REPORT.md`
- `paper_prep/w2_execution_20260712/evpd_liveconfirm_torch251_recovery/corrected_evpd_sigma08.joblib`
- `paper_prep/w2_execution_20260712/evpd_liveconfirm_torch251_recovery/LIVE_CONFIRM_MANIFEST.csv`
- `paper_prep/w2_execution_20260712/evpd_liveconfirm_torch251_recovery/LIVE_CONFIRM_POLICY_FREEZE.json`
