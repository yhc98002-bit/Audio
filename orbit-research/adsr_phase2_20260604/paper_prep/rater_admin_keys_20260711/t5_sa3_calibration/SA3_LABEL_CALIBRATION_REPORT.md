# SA3 Label Calibration Instructions

`SA3_LABEL_CALIBRATION_STATUS = PACKAGE_READY`

The package has 60 blinded clips: 20 far below, 20 near, and 20 far above
the ACE-Step Demucs threshold, with 10 vocal-request and 10
instrumental-request clips per band. Detector ratio and band are absent from
the rater sheet.

## Label A (voice presence)

"Do you hear any sound a reasonable listener would perceive as a human voice or vocalization? Includes singing, rap, speech, chant, humming, wordless vocals, choir, ooh/ah, vocal chops. Answer Yes / No / Unsure; then select perceived vocal type and whether it is isolated, intermittent, or sustained."

Allowed values: `Yes`, `No`, `Unsure`.

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

Run `score_sa3_label_calibration.py` with the completed ratings file. The
scorer fails on missing, duplicate, or unknown IDs and reports the fixed
0.1791 threshold plus a labeled SA3-specific threshold estimate.
