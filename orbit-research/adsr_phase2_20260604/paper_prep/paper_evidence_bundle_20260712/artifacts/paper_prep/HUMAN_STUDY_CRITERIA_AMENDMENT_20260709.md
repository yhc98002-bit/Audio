# Human Study Criteria Amendment

`AMENDMENT_STATUS = SIGNED`

Drafted: 2026-07-09, before any real ratings were collected for the amended
A-prime or B-prime packages.

## Administrative Scope

This amendment fixes the validation constructs, cardinalities, abstain/tie
handling, media classes, and B-prime primary endpoint before rating. It does
not change any generated audio, frozen detector output, or prior experimental
ledger. At amendment time, zero real ratings existed in either new package;
all rating cells were blank and no outcome was available to tune these rules.

## B-prime Primary Endpoint

The primary endpoint is `quality_preference` on the first presentation of each
of 80 unique pairs. The rater instruction is:

> "Judge musical/audio quality while setting aside whether the clip correctly contains or omits vocals. Consider production quality, artifacts, musical coherence, naturalness, and listening quality."

`overall_preference` and `constraint_preference` are secondary endpoints. The
24 delayed reversed presentations estimate position bias and intra-rater
reliability; they are never extra primary votes.

Ties are excluded from the primary denominator. The report must include
ties-as-half and ties-against-method sensitivities. `Unsure` is an abstention.
The scorer exposes `--abstain-policy {report,count-as-disagree}`, defaulting to
`report`; it scores decided rows and reports abstain counts. The frozen primary
criterion is a one-sided 95% score lower confidence bound on method preference
strictly greater than 0.40. The older rule (at least 40% preference and not
significantly below 50%) is reported only as a secondary sensitivity.

## A-prime Label A

> **Label A (voice presence):** "Do you hear any sound a reasonable listener would perceive as a human voice or vocalization? Includes singing, rap, speech, chant, humming, wordless vocals, choir, ooh/ah, vocal chops. Answer Yes / No / Unsure; then select perceived vocal type and whether it is isolated, intermittent, or sustained."

## A-prime Label B

> **Label B (constraint satisfaction):** Vocal request → *Satisfied* only when clearly audible vocals function as an intentional musical element; a fleeting isolated chop, ambiguous voice-like texture, or background artifact is not sufficient. Instrumental request → *Violated* when perceived vocal content is salient, recurrent, or functions as a musical element, or when any phrase is clearly sung, spoken, or rapped; a single isolated non-linguistic one-shot shorter than ~2 s is normally not a violation unless unusually prominent.

Choir-pad rule: perceived as human choir → A=Yes and instrumental request
normally violated; perceived as synth timbre → A=No; ambiguous → Unsure.
Every interface retains `Unsure`. Label B is the paper-primary construct.
Demucs sensitivity, specificity, balanced accuracy, MCC, and confusion are
reported against both labels.

## Reconciled A-prime Cardinalities

The intended primary disagreement universe is the 112 unique Phase-0 clips
where canonical Demucs (threshold 0.1791) and PANNs disagree. All 112 original
media files survive. The apparent cardinality chain is construct and packaging
drift, not sample attrition:

| Stage | Rows | Interpretation |
|---|---:|---|
| Intended Demucs-vs-PANNs universe | 112 | Primary disagreement gate; all originals |
| Stale `demucs_whisper_disagree` universe | 100 | Different detector-pair construct |
| Old A-prime manifest bucket | 92 | Eight duplicate IDs removed by global first-row assignment |
| Old human-package bucket | 82 | Ten more rows reassigned by path-derived bucket labels |

The amended original-only package contains:

| Set | Role | Rows |
|---|---|---:|
| Demucs-vs-PANNs disagreements | Primary gate | 112 |
| Original rare-basin clips | Primary gate | 48 |
| Original agreement spot check | Primary gate | 30 |
| Stratified random sample | Global Wilson bound, outside pass shape | 500 |

The rare-basin count is 48 rather than the earlier approximate target of 50
because 26 rows in the prior 74-row pool were regenerated from frozen seeds.
Those 26 are separated as sensitivity media; no original clip was silently
dropped from the recovered 48.

## Media-Class Rule

Original and recovered-original media are eligible for the primary package.
Regenerated media are excluded by default and reported separately. A
regenerated row may enter a primary gate only if the regeneration-fidelity
audit is `EXACT` or `LABEL_STABLE_ONLY` and two PIs explicitly approve that
inclusion. `NOT_REPRODUCIBLE` permanently restricts regenerated rows to
sensitivity analysis. The current original-only A-prime gate does not depend
on regenerated media under any T2 result.

## Fail-Closed Implementation

- Rating and admin ID sets must match exactly; unknown, omitted, and duplicate
  IDs are fatal.
- Duplicate source clip IDs are fatal.
- Synthetic and test-fixture ratings cannot produce PASS.
- A-prime regenerated media are excluded from the primary gate by default.
- The 500-row global-bound sample is outside the pass shape.
- B-prime scores all three questions but uses quality as the primary endpoint.
- A-prime rows are shuffled with recorded seed 20260709; opaque IDs use an
  environment-provided nonce, never a repository key.

Implementation and tests:

- `paper_prep/scripts/validation_gate_v2.py`
- `paper_prep/scripts/build_validation_packages_20260709.py`
- `paper_prep/validation_A_prime/score_human_A_prime.py`
- `paper_prep/validation_B_prime/score_human_B_prime.py`
- `tests/test_validation_gate_v2.py`
- `tests/test_validation_package_builder_20260709.py`

## Signature

PI signature: Richard Ye

Date: 2026-07-10

Approval statement: "I have read and approve
HUMAN_STUDY_CRITERIA_AMENDMENT_20260709.md as committed at ed59500 as the
governing A′/B′ criteria; zero ratings existed at signing."
