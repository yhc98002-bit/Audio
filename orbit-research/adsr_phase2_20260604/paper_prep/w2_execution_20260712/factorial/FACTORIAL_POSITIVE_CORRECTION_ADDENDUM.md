# W2 Factorial Positive-Only Correction Addendum

Frozen: 2026-07-12, after generation but before any factorial analysis
Scope: positive-text conditions only; all original files and ledgers retained

`FACTORIAL_CORRECTION_STATUS = FROZEN_BEFORE_CORRECTED_GENERATION`

## Defect

The preregistered positive intervention string itself contains zero vocal
lexemes, but 25 of the 32 canonical instrumental prompts already contain
negative phrases such as `no vocals`, `no vocal stem`, or `treat lyrics field
as empty`. Consequently, the first generated `positive_text` and
`positive_sampler` cohorts do not implement a full-prompt positive-only
contrast. This was detected before detector scoring was interpreted or any
condition comparison was run.

## Frozen Correction

1. Preserve all 1,024 original positive-condition files and ledgers. Label them
   `INVALID_FOR_PRIMARY_POSITIVE_ONLY_CONTRAST_PREEXISTING_VOCAL_LEXEMES`.
2. Do not rerun the four unaffected conditions.
3. For each canonical prompt, deterministically remove only complete negative
   vocal/lyrics instructions or parenthetical clauses containing vocal/lyrics
   lexemes. Preserve all musical content outside those clauses.
4. Append the frozen positive phrase:
   `instrumental arrangement led by synthesizer, drums, bass, and melodic instruments`.
5. Fail closed unless the complete resulting text contains none of:
   `vocal`, `vocals`, `voice`, `voices`, `sing`, `singing`, `singer`, `choir`,
   `chant`, `speech`, `spoken`, `rap`, `lyric`, or `lyrics` as whole words.
6. Reuse the exact registered CRN seed for each prompt/seed and the original
   sampler setting: CFG 5.0 for positive text and CFG 7.5 for positive plus
   sampler. Replays are replacements, not independent observations.
7. Primary factorial analysis uses the corrected positive cohorts plus the four
   original unaffected cohorts. The invalid cohort may appear only in a labeled
   implementation-sensitivity appendix.

No PLAN, gate, or claim status changes. This addendum narrows execution to the
literal preregistered positive-only construct and is committed before corrected
generation begins.
