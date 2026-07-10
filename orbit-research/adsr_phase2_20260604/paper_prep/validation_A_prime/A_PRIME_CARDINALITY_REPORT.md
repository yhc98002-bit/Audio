# A-prime Cardinality Reconciliation

`A_PRIME_CARDINALITY_STATUS = RECONCILED`

`A_PRIME_PROTOCOL_AMENDMENT_REQUIRED = NO`

## Result

The intended 112-case detector-disagreement universe is exactly reproducible
from the frozen phase-0 packet, Demucs ratios, and PANNs scores. All 112 primary
clips are surviving original media; no regenerated clip is needed in the
primary A-prime disagreement gate.

The apparent `112 -> 100 -> 92 -> 82` sequence was not ordinary sample
attrition. It combined a detector-pair substitution, global first-row-wins
deduplication, and path-based bucket reassignment.

## Cardinality Chain

| Stage | Count | Meaning |
|---|---:|---|
| Intended universe | 112 | Unique phase-0 cases where canonical Demucs (`htdemucs`, threshold 0.1791) and PANNs (threshold 0.0654) disagree. This is the primary gate universe. |
| Stale reason-tag universe | 100 | Cases tagged `demucs_whisper_disagree` by the older packet builder. This is a different construct, not a 12-row loss from the intended set. |
| A-prime manifest disagreement set | 92 | The 100 stale-tag IDs after eight cross-reason duplicate IDs were assigned to the first encountered row by global deduplication. |
| Human-package disagreement bucket | 82 | The 92 manifest rows after ten rows were reassigned from their extracted `2c_detector_agreement_spotcheck` path. |

The two detector universes overlap on 45 cases. The intended
set has 67 cases absent from the stale 100, while the
stale set has 55 cases that do not meet the intended
Demucs-versus-PANNs rule.

The original packet contains 250 rows and
242 unique case IDs; its
8 duplicate rows are retained as provenance
but never treated as independent clips.

## Media Classification

Primary 112 media classes: `{"original": 112}`.
All package paths exist and all 112 are classified `original`. The 100 clips
regenerated during the 2026-07-08 recovery remain available, but none is needed
to restore the intended primary disagreement universe. Regenerated rows are
sensitivity-only unless T2 and dual-PI approval later authorize otherwise.

## Analysis Rule

- Primary disagreement gate: the 112 reconstructed Demucs-versus-PANNs cases.
- Sensitivity only: stale Demucs-versus-Whisper cases outside the intended 112,
  regenerated media, and any later construct packet.
- Duplicate packet occurrences are provenance rows, not additional ratings.
- The prior 92- and 82-row packages must not be called the frozen 112-case gate.

## Row-Level Evidence

`orbit-research/adsr_phase2_20260604/paper_prep/validation_A_prime/A_PRIME_CARDINALITY_RECONCILIATION.csv` records membership in all four stages, packet occurrence count,
detector values, media class, primary/sensitivity role, and the exact transition
reason for every ID in the union of the intended and stale universes.

## Audit Status

`RECONCILED`. No cardinality amendment is required because the literal 112-case
universe and all original media have been recovered. The D5 construct wording
still requires the T3 study-criteria amendment because it changes the human
label definition, not the sample cardinality.
