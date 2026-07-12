# PI Ratings, Decisive Branch, And Conditional W2 Report

Execution date: 2026-07-12 (Asia/Shanghai)

`PI_RATING_INGEST_STATUS = PASS`

`DECISIVE_BRANCH_VERDICT = demucs_missing`

`A_PRIME_CORE_REGISTRATION_STATUS = REGISTERED_GLOBAL_500_PENDING`

`A_PRIME_GATE_SCORED = NO`

`T1_AMENDED_PRE_REVEAL_STATUS = UNAVAILABLE`

`W2_STATUS = COMPLETE_DIFF_ESCALATED`

`JUDGE_VALIDATION_STATUS = PI_BLOCKED`

`TEST_SUITE_STATUS = PASS`

## 1. Input Custody And Validation

The two raw PI exports were treated as immutable inputs. Derived scorer-ID
files, audits, and gold splits were written under `processed/`.

| Check | T1 decisive | T2 A-prime core |
|---|---:|---:|
| Export bundle | `t1_decisive_v2` | `t2_aprime_core` |
| Rows | 42 | 190 |
| Exact bundle-key ID set | 42/42 | 190/190 |
| Duplicate IDs | 0 | 0 |
| Required blank fields | 0 | 0 |
| Row provenance | 42/42 `pi:Richard` | 190/190 `pi:Richard` |
| Top-level provenance | `pi:Richard` | `pi:Richard` |

Additional T1 checks passed:

- all request modes match the keys-side `requested_vocal` mapping;
- reveal sequence is an exact permutation of 1–42;
- Label A, Label B, confidence, vocal type, and extent values are valid;
- `label_a_amended` is a JSON boolean on every row.

Raw input checksums:

- `t1_decisive.json`: `b5ac337364083534719cf679d3627935f505632fa76b0f56f47140f5dcd50868`
- `t2_aprime_core.json`: `4aeffc990edaf7cbdf235aa1804c4cb44e967a3adffb5e6b5a862deacb6c16c9`

## 2. T1 Amendments And Adjudication

T1 contains 12 rows with `label_a_amended=true`. The submitted directory has
no autosave or backup export, and the v2 JSON schema stores only the final
Label A, the amendment flag, and reveal sequence. It does not store the
pre-reveal value or an event history. Browser-local storage was not transferred
to the cluster. The 12 original pre-reveal Label-A values are therefore
unavailable and were not reconstructed or inferred.

All 12 amended T1 presentations were excluded from primary judge gold unless
the same audio had an independent fully blind T2 rating. This preserves the T2
rating where available without treating post-reveal T1 values as blind truth.

One hard internal inconsistency requires adjudication:

| Bundle ID | Scorer ID | Bucket | Request | Label A | Label B | Amended | Issue |
|---|---|---|---|---|---|---|---|
| `r_a12ef8afc8c096065e2b` | `decisive_04_a5f338f1ce29` | rare basin | vocal | no | satisfied | false | Label B implies audible voice while Label A says no |

That row is listed as `PENDING_PI` and excluded from judge gold. No response was
silently changed.

## 3. Decisive Branch

The keyed T1 scorer completed all 42 rows and returned `demucs_missing`.

- Contested Label-B decisions: 23/24.
- Label B agrees with the Qwen-side branch: 21/23.
- Label B agrees with the frozen Demucs-side branch: 2/23.
- Contested rows with both Label A and Label B decided: 22/24.
- Label-A/Label-B disagreements among those 22: 0.
- Obvious-control matches to Demucs: 5/6.

| Bucket | N | A yes/no/unsure | B voice/no-voice/unsure | Demucs matches B | Qwen matches B |
|---|---:|---:|---:|---:|---:|
| Failed smoke negatives | 4 | 2/1/1 | 2/1/1 | 1 | 2 |
| Qwen-yes/Demucs-no | 20 | 19/0/1 | 19/1/0 | 1 | 19 |
| Agreement controls | 6 | 4/1/1 | 4/2/0 | 5 | 5 |
| Rare basin | 6 | 5/1/0 | 6/0/0 | 1 | 0 |
| Threshold-near | 6 | 5/1/0 | 5/1/0 | 0 | 6 |

The branch verdict is driven by Label B, which is intentionally answered after
request reveal. Missing pre-reveal Label-A history does not determine that
verdict. This packet remains branch selection, not A-prime validation.

## 4. A-prime Core Registration

T2 is registered as the official amendment-compliant human core:

- 112 detector-disagreement rows;
- 48 original rare-basin rows;
- 30 agreement controls;
- 190/190 carry `pi:Richard` provenance;
- Label A: 177 yes, 12 no, 1 unsure;
- official scorer-ID file SHA-256:
  `ade2fe73b1f0bec90b692f38efa9e322d61a1482b2d7453e401f9b6700530888`.

The merge pipeline now has an explicit scorer-ID namespace and validates the
exact 190 human-only core before accepting a global track. The 500 stratified
rows are pending. The merge was not completed and the A-prime gate was not
scored.

## 5. PI-Gold Judge Validation

After excluding unsure, amended-without-history, and internally inconsistent
presentations, then deduplicating by audio SHA-256, the judge-gold pool has 208
unique original-media clips: 195 yes and 13 no. Every media checksum matches
its admin manifest.

- Calibration split: 103 clips.
- Held-out split: 105 clips.
- Balanced smoke: 10 calibration clips, 5 yes and 5 no.
- Smoke and held-out media-hash overlap: 0.
- Calls per clip: 3, deterministic.
- Raw calls: 30 smoke + 315 held-out = 345.
- Client/parser failures: 0.
- Abstentions: 0.

| Metric | Balanced smoke | Held-out PI gold |
|---|---:|---:|
| Clips | 10 | 105 |
| Positive / negative | 5 / 5 | 98 / 7 |
| Sensitivity | 1.000000 | 1.000000 |
| Specificity | 0.600000 | 0.714286 |
| Balanced accuracy | 0.800000 | 0.857143 |
| MCC | 0.654654 | 0.836660 |
| Abstention rate | 0.000000 | 0.000000 |

The PI-gold run supersedes the earlier CXY-only evidence limitation. It does
not auto-promote the judge: the balanced smoke is 8/10 rather than the earlier
10/10 engineering target, and no signed numeric automatic-judge promotion rule
exists. `JUDGE_VALIDATION_STATUS` remains `PI_BLOCKED`; the stratified-500 track
was not launched.

## 6. Conditional W2

Because the branch is `demucs_missing`, W2 was executed rather than merely
scaffolded. Demucs, PANNs, OR, and AND candidates were tuned on the 103-clip
calibration split, then audited on 105 held-out clips. The calibration-only
winner is:

- family: Demucs AND PANNs;
- Demucs threshold: `0.0386395287`;
- PANNs threshold: `0.0318181422`;
- held-out sensitivity: 0.897959;
- held-out specificity: 0.714286;
- held-out balanced accuracy: 0.806122;
- held-out MCC: 0.436436.

The selected candidate scored every retained file:

| Cohort | Rows |
|---|---:|
| Stage 3 | 6,144 |
| N2 | 16,384 |
| Atlas keeps | 194 |
| Candidate spine retained media | 1 |
| **Total** | **22,723** |

Merge audit: 22,723/22,723 PASS, zero failures, zero missing rows, and zero
mismatches when 22,528 stored Demucs ratios are checked against the canonical
0.1791 labels. The other 4,095 candidate-spine records have no retained media
and were not regenerated.

## 7. W2 Headline Diff

| Metric | Frozen label | Corrected candidate | Delta |
|---|---:|---:|---:|
| N2 overall clean rate | 0.533447 | 0.778870 | +0.245422 |
| Stage 3 instrumental both | 0.377083 | 0.078125 | -0.298958 |
| Stage 3 instrumental sampler | 0.344792 | 0.207292 | -0.137500 |
| Stage 3 instrumental text | 0.326042 | 0.177083 | -0.148958 |
| Stage 3 vocal both | 0.779412 | 0.992647 | +0.213235 |
| Stage 3 vocal guidance | 0.781250 | 0.989890 | +0.208640 |
| Stage 3 vocal hints | 0.093750 | 0.655331 | +0.561581 |
| N2 instrumental clean rate | 0.761137 | 0.606715 | -0.154422 |
| N2 vocal clean rate | 0.401331 | 0.878762 | +0.477431 |

N2 regime counts change from 67/33/23/5 to 110/9/9/0 for
easy/seed-recoverable/low/rare.

These differences cross the standing escalation threshold and flip
paper-bearing interpretations. They are not adopted. The calibration pool is
detector-disagreement-enriched, contains only 13 negative clips, and targets
Label A while the signed paper endpoint is Label B. The W2 output is frozen as
sensitivity evidence pending dual-PI review and a representative Label-B
calibration plan. `PLAN.md`, frozen labels, and all claim statuses remain
unchanged.

## 8. Node Use

- `an12`: W2 calibration and the full pass used physical GPUs 0–5 and 7. An
  unrelated BlindGain job occupied GPU 6; it was disclosed, not counted as
  ADSR, and not terminated.
- `an29`: the ADSR judge service remained healthy on GPUs 0, 2, 3, and 4 and
  completed all PI-gold calls. An unrelated BlindGain job occupied GPUs 1, 5,
  6, and 7; it was disclosed, not counted as ADSR, and not terminated.

## 9. Verification

The first attached full-suite attempt exposed two duplicated numeric threshold
constants. That failed output is preserved. Both literals were replaced with
the canonical `THRESHOLD` import; the targeted policy test then passed.

Final attached suite: **256/256 tests passed**, exit code 0, approximately 155
seconds. `git diff --check` is run again before commit.

## 10. Evidence Index

- Raw PI exports: `paper_prep/pi_ratings_20260711/t1_decisive.json`, `paper_prep/pi_ratings_20260711/t2_aprime_core.json`
- Ingestion audit: `paper_prep/pi_ratings_20260711/processed/PI_RATING_INGEST_AUDIT.json`
- Adjudication list: `paper_prep/pi_ratings_20260711/processed/T1_ADJUDICATION_LIST.csv`
- Decisive report: `paper_prep/pi_ratings_20260711/processed/DECISIVE_BRANCH_REPORT.md`
- Core registration: `paper_prep/pi_ratings_20260711/processed/A_PRIME_CORE_REGISTRATION.json`
- Judge report: `paper_prep/pi_ratings_20260711/processed/PI_GOLD_JUDGE_VALIDATION_REPORT.md`
- Judge audit: `paper_prep/pi_ratings_20260711/processed/PI_GOLD_JUDGE_VALIDATION_AUDIT.json`
- W2 report: `paper_prep/w2_contingency_20260711/activated_20260711/W2_ACTIVATION_REPORT.md`
- Dual-PI escalation: `paper_prep/w2_contingency_20260711/activated_20260711/W2_DUAL_PI_ESCALATION.md`
- W2 exact diff: `paper_prep/w2_contingency_20260711/activated_20260711/full_corrected/W2_OLD_VS_CORRECTED_PLAN_DIFF.csv`
- W2 checksums: `paper_prep/w2_contingency_20260711/activated_20260711/full_corrected/W2_OUTPUT_SHA256SUMS.txt`
- Node audit: `paper_prep/NODE_SATURATION_AUDIT_20260711_PI_INGEST.md`
- Final test output: `paper_prep/pi_ratings_20260711/processed/PI_INGEST_FULL_TEST_RESULTS_20260711.txt`
- Execution ledger: `paper_prep/execution_20260709/CODE_REVIEW_RECOVERY_LEDGER.jsonl`

## 11. PI Decisions Required

1. Adjudicate `decisive_04_a5f338f1ce29` (vocal request, Label A no, Label B satisfied).
2. Decide whether to define a prospective self-hosted-judge promotion rule and
   run a new disjoint validation, or keep the stratified-500 track human-only.
3. Both PIs must review the W2 sensitivity and approve its disposition. Current
   corrected headlines must not be adopted without both signatures and a
   representative Label-B calibration strategy.
