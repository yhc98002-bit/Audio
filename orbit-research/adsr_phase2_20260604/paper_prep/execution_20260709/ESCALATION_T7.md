# T7 PI-Gold Judge Promotion Blocker

`JUDGE_VALIDATION_STATUS = PI_BLOCKED`

The CXY-only evidence limitation is closed: the self-hosted judge was run
against amendment-compliant `pi:Richard` gold on a balanced 10-clip smoke and a
media-disjoint 105-clip held-out split, with three deterministic calls per
clip. All 345 calls completed and parsed without abstention.

The balanced smoke scored 8/10, below the earlier 10/10 engineering target.
The held-out result is stronger (sensitivity 1.000000, specificity 0.714286,
balanced accuracy 0.857143, MCC 0.836660), but neither the signed amendment nor
the standing brief freezes a numeric automatic-judge promotion threshold.
Gates never auto-pass. The stratified-500 A-prime track was therefore not
launched.

## Evidence

- `paper_prep/pi_ratings_20260711/processed/PI_GOLD_JUDGE_VALIDATION_REPORT.md`
- `paper_prep/pi_ratings_20260711/processed/PI_GOLD_JUDGE_VALIDATION_AUDIT.json`
- `paper_prep/judge_raw/selfhost_qwen3_omni_pi_gold_smoke_20260711.jsonl`
- `paper_prep/judge_raw/selfhost_qwen3_omni_pi_gold_heldout_20260711.jsonl`

## Required Decision

The PI must either approve a prospective judge-promotion criterion and a new
disjoint validation run, or keep the judge non-primary and complete the
stratified-500 track with qualifying human provenance. No A-prime status has
changed.
