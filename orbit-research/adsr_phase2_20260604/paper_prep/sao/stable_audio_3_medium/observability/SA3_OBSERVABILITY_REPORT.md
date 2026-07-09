# SA3 Medium Observability Report

Generated: 2026-07-08

SA3_OBSERVABILITY_STATUS = COMPLETE

SA3_OBSERVABILITY_CONCLUSION = EARLY_OBSERVABILITY_WEAK

## Inputs

- Full 4-step scored ledger: `paper_prep/sao/stable_audio_3_medium/prevalence_full500/SA3_PREVALENCE_DEMUCS_LEDGER.jsonl`
- Low-step scored ledger: `paper_prep/sao/stable_audio_3_medium/observability/lowstep_full500/SA3_PREVALENCE_DEMUCS_LEDGER.jsonl`
- Low-step generation ledger: `paper_prep/sao/stable_audio_3_medium/observability/lowstep_full500/SA3_PREVALENCE_LEDGER.jsonl`
- Generation/scoring scripts: `paper_prep/sao/stable_audio_3_medium/run_sa3_prevalence.py`; `paper_prep/sao/stable_audio_3_medium/score_sa3_prevalence_demucs.py`

## Coverage

- Low-step proxy rows generated: 1000.
- Low-step proxy rows scored: 1000.
- Full-step rows scored: 4000.
- Matched `(prompt_id, seed_idx)` rows: 1000.

## Matched Proxy Results

- Low-step type-correct rows: 548 / 1000 = 0.548000.
- Full 4-step type-correct rows on the same keys: 537 / 1000 = 0.537000.
- Low-step present rows: 180 / 1000 = 0.180000.
- Full 4-step present rows on the same keys: 165 / 1000 = 0.165000.
- Present-label agreement: 943 / 1000 = 0.943000; Wilson CI [0.926863, 0.955747].
- Type-correct agreement: 943 / 1000 = 0.943000; Wilson CI [0.926863, 0.955747].
- Low absent -> full present flips: 21.
- Low present -> full absent flips: 36.

## Interpretation

SA3's current local inference path did not expose true intermediate-latent
decoding during this recovery run, so this is a low-step proxy rather than a
direct early-denoising probe. The proxy has measurable agreement with the
4-step output on matched keys, but it is not enough to claim the same EVPD-style
early observability established for ACE-Step.

Paper wording should be limited to: SA3 early observability is plausible but
weak under the current API/proxy, and needs a true intermediate callback or a
dedicated early probe before it can support a full cross-backbone observability
claim.
