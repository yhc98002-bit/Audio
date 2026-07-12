# Corrected EVPD And Live-Confirm Preparation

`EVPD_LIVECONFIRM_PREP = READY_BLOCKED_ON_PROMOTION`

- Corrected EVPD manifest: `CORRECTED_EVPD_TRAINING_MANIFEST.csv`
- Live prompts: 48 instrumental-risk plus 16 vocal-sanity.
- Live units: 64 prompts x 4 policies x 2 repetitions = 512.
- Common-random-number seed range is registered in `paper_prep/SEED_REGISTRY.md`.
- Launch guard requires dual W2 signatures, dual-PI instrument adoption, and unchanged policy hash.
- The two-day cap and headline-removal rule are frozen in `LIVE_CONFIRM_POLICY_FREEZE.json`.
