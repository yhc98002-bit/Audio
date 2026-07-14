# Judge Negative-Gold Top-Up Escalation

`ESCALATION_STATUS = PI_HUMAN_LABELS_REQUIRED`

The self-hosted judge clears every frozen point and one-sided LCB metric on the
fresh T6 evaluation set, with zero abstentions, but the frozen class-count gate
cannot pass:

- Fresh T6 evaluation: 149 positive, 27 negative, 4 human unsure.
- Frozen minimum: at least 30 positive and 50 negative decided rows.
- Fresh-split shortfall: 23 negative rows.
- All currently available t1+t2+t6 PI gold combined: 43 negatives.
- Absolute available-gold shortfall: 7 negative rows.

No automatic relabeling or model-derived truth can satisfy this gate. A new,
hash-disjoint, conservatively selected instrumental-negative package must be
rated by a PI/human source. The split and inclusion probabilities must be
frozen before ratings. Until then, stratified-500 judge calls and the A-prime
instrument merge remain blocked.

Evidence:

- `paper_prep/autochain_20260712/judge_aprime/JUDGE_LABEL_A_GOLD_BUILD.json`
- `paper_prep/autochain_20260712/judge_aprime/JUDGE_LABEL_A_VALIDATION.json`
- `paper_prep/autochain_20260712/judge_aprime/JUDGE_LABEL_A_VALIDATION_REPORT.md`
