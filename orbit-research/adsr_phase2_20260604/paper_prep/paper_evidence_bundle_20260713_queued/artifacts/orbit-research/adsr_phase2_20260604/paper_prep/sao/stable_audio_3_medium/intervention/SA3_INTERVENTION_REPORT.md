# SA3 Medium Vocal-Boost Intervention Report

Generated: 2026-07-08

SA3_INTERVENTION_STATUS = COMPLETE

## Question

Dominant SA3 pilot failure mode was vocal-miss under the fixed Demucs
vocal-presence detector. This intervention tests whether direct prompt
re-conditioning toward clear lead human singing changes that failure mode.

## Protocol

- Baseline condition: matched rows from
  `paper_prep/sao/stable_audio_3_medium/prevalence/`.
- Intervention condition: same prompt IDs and seeds, with the prompt prefixed and
  suffixed to request clear lead human singing and audible central vocals.
- Prompt set: first 32 vocal prompts from the prevalence pilot with at least one
  baseline vocal-miss.
- Seeds: 8 matched seeds per prompt.
- Rows: 32 prompts x 8 seeds = 256 paired rows.
- Duration: 8 seconds.
- Steps: 4.
- Detector: `htdemucs` vocal-energy ratio, threshold 0.1791.

## Artifacts

- Intervention manifest:
  `paper_prep/sao/stable_audio_3_medium/intervention/vocal_boost/SA3_INTERVENTION_MANIFEST.jsonl`
- Intervention generation ledger:
  `paper_prep/sao/stable_audio_3_medium/intervention/vocal_boost/SA3_PREVALENCE_LEDGER.jsonl`
- Intervention Demucs ledger:
  `paper_prep/sao/stable_audio_3_medium/intervention/vocal_boost/SA3_PREVALENCE_DEMUCS_LEDGER.jsonl`
- Generated audio:
  `paper_prep/sao/stable_audio_3_medium/intervention/vocal_boost/audio/`
- Generation script:
  `paper_prep/sao/stable_audio_3_medium/run_sa3_vocal_boost_intervention.py`
- Scoring script:
  `paper_prep/sao/stable_audio_3_medium/score_sa3_prevalence_demucs.py`
- Generation log:
  `paper_prep/sao/stable_audio_3_medium/logs/sa3_intervention_vocal_boost_gen_an29_gpu0.log`
- Scoring log:
  `paper_prep/sao/stable_audio_3_medium/logs/sa3_intervention_vocal_boost_demucs_an29_gpu0.log`

## Results

- Matched paired rows: 256.
- Matched prompts: 32.
- Baseline type-correct rows: 14 / 256 = 0.054688.
- Vocal-boost type-correct rows: 191 / 256 = 0.746094.
- Absolute lift: +0.691406.
- Baseline present rate: 0.054688.
- Vocal-boost present rate: 0.746094.
- Fail-to-clean flips: 177.
- Clean-to-fail flips: 0.
- Baseline median vocal-energy ratio: 0.00000278.
- Vocal-boost median vocal-energy ratio: 0.380301.

## Conclusion

Second-model robustness is **partial**. SA3 Medium is executable locally and the
dominant detected categorical failure, vocal-miss, responds strongly to targeted
prompt re-conditioning on a failure-prone vocal subset. This supports a focused
mechanistic claim that conditioning can move the SA3 vocal-presence axis.

It does not yet support a full second-backbone ADSR claim because the SA3 line
still has only one focused intervention and a weak low-step observability proxy,
not a validated live SA3 ADSR policy stack or human-calibrated quality/readout
for SA3 outputs.

Allowed wording: "A SA3 Medium pilot reproduced a measurable vocal-presence
constraint and a focused vocal-boost intervention improved Demucs vocal-present
rate on matched failure-prone vocal prompts."

Forbidden wording: do not claim full second-backbone robustness or full SA3 ADSR
validation from this intervention alone.
