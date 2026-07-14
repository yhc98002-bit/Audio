# W2 Corrected-Instrument Amendment

Date drafted: 2026-07-12  
Governing status: PI 1 signed, PI 2 pending; no PLAN edit or claim-status change
is authorized until the required independent signatures are complete.

`W2_AMENDMENT_STATUS = SIGNED_BY_BOTH_PIS`

## 1. Scope And Failure Rule

This amendment freezes the calibration, promotion, correction, factorial, and
bounded live-confirm design for the W2 detector-sensitivity branch. It does not
alter any frozen ACE-Step v1 evidence. The current detector remains the
instrument used by the frozen reports unless the corrected instrument passes
every promotion condition below after both PI signatures.

Failure of any promotion condition yields:

`CORRECTED_INSTRUMENT_STATUS = SENSITIVITY_ONLY`

Under that outcome, all frozen numbers stand. Corrected estimates may appear
only as explicitly labeled sensitivity analyses.

## 2. Calibration Design

### 2.1 Fixed Sample Structure

The calibration study contains 180 unique clips and 20 hidden intra-rater
repeats, for 200 scored presentations:

- **Core calibration:** 160 unique clips, split before ratings into 60 training
  clips and 100 held-out clips.
- **Held-out class target:** approximately 60 Label-B negatives and 40 Label-B
  positives, based only on frozen pre-rating proxy strata. True class labels
  remain unknown until rating.
- **Transport audit:** 20 unique clips drawn from N2, Stage 3, and Batch-3 keeps,
  enriched at corrected-score boundaries and old-versus-corrected detector
  disagreements.
- **Hidden repeats:** 20 exact media repeats selected deterministically from the
  held-out core and interleaved under the blinded shuffle.
- **Simple-random anchor:** 40 of the 100 held-out core clips form a simple
  random sample from the reconstructed 4,096-candidate spine. These rows retain
  their exact inclusion probability and cannot be exchanged for targeted rows.

Richard's one pending adjudication clip is presented as a separately marked
appendix item. It is excluded from the 180 unique calibration clips, the 20
hidden repeats, fitting, promotion, and reported calibration denominators.

### 2.2 Frozen Strata And Inclusion Probabilities

Every unique sampled row records its source frame, selection-stage probability,
and final inclusion probability. Targeted sampling uses the full cross-product:

`request type x corrected-score band x old-detector status x corrected status x disagreement x source family`

The corrected-score bands are frozen from the pre-rating candidate-score
distribution as `low`, `boundary`, and `high`; cut points and eligible counts
must be recorded in the administrative manifest before ratings. Source family
is one of `spine`, `N2`, `Stage3`, or `Batch3_keep`. Empty cross-product cells
are retained in the sampling-frame audit and are not silently collapsed.

The 40-clip anchor is sampled without replacement from the spine with equal
probability `40 / 4096`. Each targeted row records the probability induced by
its frozen stratum quota. Hidden repeats inherit the parent row's design weight
for reliability only and receive zero weight in calibration or promotion
metrics.

### 2.3 Train, Held-Out, And Reserve Isolation

The 60-row training ID set, 100-row held-out ID set, 20 transport IDs, 20 repeat
parent IDs, and an ordered reserve are committed before ratings. Instrument
family and threshold selection may use only the 60 training labels. Held-out
labels are exposed exactly once by the mechanical scorer after reliability has
passed and training selection has been finalized.

If the 100 held-out rows contain fewer than 50 decided Label-B negatives or
fewer than 30 decided Label-B positives, a class-count-only top-up is taken from
the frozen reserve in committed order. Rows are revealed only until the
deficient class reaches its minimum. No metric, model error, score direction,
or preferred result may influence top-up selection. Added rows retain their
precomputed inclusion probabilities and are held-out rows.

## 3. Rating Instrument And Reliability

The t6 interface uses the signed amendment's staged protocol: Label A is rated
blind; then the request is revealed; then Label B is rated against only the
matching request rule. Provenance is `pi:Richard`. The administrative mapping,
strata, expected statuses, and repeat links remain outside the rater bundle.

Before any training label is exposed, the scorer computes intra-rater Label-B
reliability on all 20 hidden repeats. Promotion requires both:

- Label-B exact agreement at least 0.85; and
- no more than 2 of 20 satisfied-to-violated or violated-to-satisfied reversals.

If either condition fails, the rating instructions must be clarified and the
affected calibration set rerated before promotion analysis. The scorer cannot
convert a reliability failure into a warning or a PASS.

## 4. Corrected-Instrument Families And Tuning

The following detector families are frozen:

1. the current Demucs score at threshold `0.1791`;
2. a training-tuned Demucs threshold;
3. a training-tuned PANNs vocal/speech threshold;
4. a training-tuned Demucs AND PANNs rule;
5. a training-tuned Demucs OR PANNs rule; and
6. the fixed 2026-07-11 candidate Demucs AND PANNs rule as a comparator.

For each family, a voice-presence decision is converted to a Label-B violation
decision using request direction. Threshold candidates are the unique training
scores and their adjacent midpoints. Selection uses only the 60 training rows
and maximizes design-weighted balanced accuracy. Ties are resolved, in order,
by higher minimum of sensitivity and specificity, higher MCC, fewer model
components, and deterministic ascending threshold order. No held-out,
transport, factorial, or spine outcome may tune the family or thresholds.

## 5. Promotion Gate

Promotion metrics use held-out rows only, with design weights. Point estimates
and one-sided 95% lower confidence bounds are computed by a stratified bootstrap
that resamples calibration-design strata and preserves request direction. The
implementation uses at least 10,000 deterministic bootstrap replicates and
reports the seed and effective sample sizes.

Promotion requires all of the following:

- decided Label-B positives at least 30;
- decided Label-B negatives at least 50;
- design-weighted balanced accuracy at least 0.80 and its one-sided 95% lower
  bound at least 0.80;
- design-weighted sensitivity at least 0.75 and its one-sided 95% lower bound at
  least 0.75;
- design-weighted specificity at least 0.75 and its one-sided 95% lower bound at
  least 0.75; and
- the intra-rater requirements in Section 3.

The held-out evaluation is run once. Any failed condition mechanically sets
`CORRECTED_INSTRUMENT_STATUS = SENSITIVITY_ONLY`.

## 6. Judge Promotion

A judge may be promoted only on a gold subset disjoint from every row used to
tune its prompt, parser, decoding, client, model choice, or threshold. The same
design-weighted balanced-accuracy, sensitivity, specificity, sample-count, and
one-sided lower-bound requirements apply. Judge abstention must be at most
0.10. A promoted judge result remains a separate judge-specific estimate; it
is never merged with detector output into one headline number.

## 7. Q3 Corrected-Prevalence Analysis

The primary correction is a design-weighted, low-capacity calibration model:

`P(Label-B violation | Demucs score, PANNs score, request type)`

Frozen candidate forms are:

- M0: intercept plus request type;
- M1: M0 plus transformed continuous Demucs and PANNs scores; and
- M2: M1 plus each score-by-request interaction.

Score transforms and clipping constants are fixed from the unlabeled training
distribution. L2 regularization is selected from `{0.1, 1, 10}` using
prompt-grouped five-fold design-weighted training log loss. The one-standard-
error rule selects the simpler form; remaining ties use lower form number and
then lower L2 value. No held-out label participates in model selection.

Uncertainty uses a nested bootstrap over calibration-design sampling, target
sample resampling, and model refitting, with at least 10,000 deterministic
replicates. Publication tables report apparent rate, calibrated rate, and 95%
joint interval by request direction and experimental arm.

Stratum-specific Rogan-Gladen correction is sensitivity analysis only. On the
20 transport rows, an absolute balanced-accuracy change greater than 0.10 from
core held-out performance requires either a source-specific correction with
adequate labels or the uncorrected estimate with an explicit transport caveat.

## 8. Q4 Instrumental Factorial Preregistration

Before generation, freeze 32 instrumental-risk prompts, six conditions, and 16
common-random-number seeds per prompt: plain baseline; current negative
anti-vocal wording; positive-only instrumental wording containing zero vocal
lexemes; sampler-only; negative wording plus sampler; and positive wording plus
sampler. All 3,072 clips are retained.

The primary outcome is promoted-instrument Label-B violation after promotion.
Until then, candidate-instrument results are labeled apparent/sensitivity only.
Condition comparisons use prompt-cluster bootstrap intervals and matched-seed
differences. All five nonbaseline contrasts and the negative-versus-positive
wording contrasts are reported; no condition may be selected only because it
looks favorable. A 20-pair blinded PI spot check is staged but remains outside
the detector promotion gate.

## 9. Q5 Approved Narrative And Wording

Allowed narrative is instrument-scoped: the current detector undercounts some
human-adjudicated constraint violations, and corrected analyses assess the
sensitivity of frozen conclusions to that undercount. Directional evidence may
be described as **consistent with a vocal-generation bias**. It must never be
presented as causal evidence.

The paper must not introduce new hard difficulty bins from W2. Existing
selected/difficult-set rates remain identified as such, not generic population
rates. Use `rare / impractical to retry`, never `impossible`. Never write
`proved no loss`, `human studies confirmed` without the corresponding study,
or an unqualified `no quality degradation`.

## 10. Q6 Bounded Live Confirmation

The live-confirm design is frozen as 64 prompts (48 instrumental-risk and 16
vocal sanity) by four policies by two repetitions, with common random numbers
and equal nominal compute:

1. no-probe reseed baseline;
2. corrected probe, then abort and reseed;
3. always use the best direction-specific conditioning from attempt 1; and
4. corrected probe, then take the frozen direction-specific action.

Policies, action thresholds, accounting rules, prompt IDs, and seeds are frozen
before launch. Launch is automatic only when the W2 amendment has both PI
signatures and the corrected-instrument promotion report records PASS. Runtime
has a two-day hard stop.

The primary pass criterion is a positive prompt-cluster-bootstrap one-sided 95%
lower bound for the reduction in final Label-B violation of policy 4 versus
policy 1 at equal nominal compute. Policy 4 must also be noninferior to policy
3 with a one-sided 95% upper bound on excess violation no greater than 0.05,
nominal compute must match within 1%, and the vocal-sanity excess violation
versus policy 1 must be no greater than 0.05. Missing the runtime cap or any
criterion removes the online headline; it cannot be reframed as a PASS.

## 11. Signature And Activation

Signing freezes this amendment; it does not itself pass a detector, judge, or
paper claim. Both signatures are required before human ratings begin and before
any PLAN or claim-status change.

PI 1 provenance: pi:Richard
Name: Richard 
Date: 2026-07-13
Commit SHA: 0df1cbb
Decision: I have read and approve W2_AMENDMENT_20260712.md as the governing W2
calibration, promotion, correction, factorial, and live-confirm design.

PI 2 provenance: pi:GPT-5.6-Pro
Name: GPT-5.6 Pro, co-PI (recorded verbatim by pi:Richard)
Date: 2026-07-12
Commit SHA: 0df1cbb
Decision: I have read and approve W2_AMENDMENT_20260712.md as the governing W2
calibration, promotion, correction, factorial, and live-confirm design.

Auditing co-PI (Claude), 2026-07-13: I independently verified the execution-report
contract, the bit-exact spine reconstruction audit, the t6 leak-safety test, and
that this amendment's frozen design matches the dual-PI decisions of 2026-07-12.
Approved as governing.
