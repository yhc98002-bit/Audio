# W2 Disjoint-Gold Judge Track

`JUDGE_TRACK_STATUS = READY_BLOCKED_ON_GOLD`

The 60 human-rated W2 training rows are the judge prompt/parser tuning set. The
100 human-rated W2 held-out rows are the disjoint judge evaluation set. Media
hashes are checked across roles; any overlap fails closed. No response from a
model, parser, prompt, or client tuned on held-out media is admissible.

Promotion uses held-out design weights and the same one-sided 95% lower-bound
requirements as the corrected detector: balanced accuracy at least 0.80,
sensitivity at least 0.75, specificity at least 0.75, at least 30 decided
positives and 50 decided negatives, plus abstention at most 0.10. Three fixed
calls are majority-aggregated per clip. Raw requests and responses, model ID,
decoding settings, and parser version must be retained.

After a metric PASS, the validated provenance record must be
`judge:<model>:validated:<gold_set_hash>`. The stratified-500 estimate is
reported as an apparent weighted detector estimate and a separate
judge-specific calibrated estimate with uncertainty. It is never merged with
the detector into one number and cannot change A-prime or PLAN automatically.
