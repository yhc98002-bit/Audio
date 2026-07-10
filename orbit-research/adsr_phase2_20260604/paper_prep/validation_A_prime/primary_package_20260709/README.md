# A-prime Original-Only Rating Instructions

`A_PRIME_PRIMARY_PACKAGE_STATUS = ORIGINAL_ONLY_PI_READY`

Rows are shuffled with recorded seed 20260709. Filenames and rater rows
contain no detector output. The package contains 112 original disagreement,
48 original rare-basin, 30 original agreement, and 500 original global-bound
clips. The 26 regenerated rare-clean clips are excluded from the primary gate.

## Label A (voice presence)

"Do you hear any sound a reasonable listener would perceive as a human voice or vocalization? Includes singing, rap, speech, chant, humming, wordless vocals, choir, ooh/ah, vocal chops. Answer Yes / No / Unsure; then select perceived vocal type and whether it is isolated, intermittent, or sustained."

## Label B (constraint satisfaction)

Vocal request → *Satisfied* only when clearly audible vocals function as an
intentional musical element; a fleeting isolated chop, ambiguous voice-like
texture, or background artifact is not sufficient. Instrumental request →
*Violated* when perceived vocal content is salient, recurrent, or functions as
a musical element, or when any phrase is clearly sung, spoken, or rapped; a
single isolated non-linguistic one-shot shorter than ~2 s is normally not a
violation unless unusually prominent.

Choir-pad rule: perceived as human choir → A=Yes and instrumental request
normally violated; perceived as synth timbre → A=No; ambiguous → Unsure.
Keep Unsure rather than forcing a label.
