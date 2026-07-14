# Corrected EVPD And Live-Confirm Recovery Preparation

`EVPD_LIVECONFIRM_PREP = READY_BLOCKED_ON_PROMOTION`

- EVPD input rows: 4,096/4,096 exact-runtime reconstructed spine candidates,
  all with current and candidate scores.
- Prompt-disjoint split: 210 train prompts (1,680 rows), 46 validation prompts
  (368 rows), and 256 test prompts (2,048 rows); prompt overlap is zero.
- Live prompts: 48 instrumental-risk plus 16 vocal-sanity.
- Live units: 64 prompts x 4 policies x 2 repetitions = 512.
- Common-random-number seeds: 128 unique values from 2,035,000,000 through
  2,035,006,301, registered before generation.
- Frozen policy SHA256:
  `c6de82920857a220ede8d9d0391b445a94af7d721c662480044de7f70acb9134`.

Corrected EVPD training is complete; live generation is queued. The launch
guard requires the signed W2 amendment, mechanical corrected-instrument
promotion, and an unchanged policy hash. Publication supersession remains
separately gated on dual-PI adoption. The two-day cap and headline-removal rule
remain frozen. This preparation does not apply supersession to `PLAN.md`.
