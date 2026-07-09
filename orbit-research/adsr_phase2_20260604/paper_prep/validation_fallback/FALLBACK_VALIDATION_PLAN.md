# Fallback Validation Plan

Generated: 2026-07-07

## Trigger

Qwen Plus and Flash both failed the repaired smoke and smoke v2 at `6/10`.
All v2 failures were expected-negative instrumental clips that both models
described as containing vocals/singing/growling/lyrics. Parser and WAV transport
are not the observed failure source.

## Validation Instruments

1. **Qwen model adjudication as fallback evidence, not a passed primary gate.**
   - Primary fallback model: `qwen3.5-omni-plus`.
   - Deterministic decoding: temperature `0.0`, seed `20260706`.
   - Raw request/response logs under `paper_prep/judge_raw/`.
   - Use only as automatic fallback evidence because the 10-clip project smoke
     did not pass.
2. **Existing frozen human/rater packages.**
   - Label package media extracted from
     `/tmp/adsr_human_eval_pkg_20260620_complete_20260707.tar.gz` into
     `paper_prep/validation_A_prime/tar_extracted/`.
   - Human response sheets are blank; no human result may be fabricated.
3. **Demucs/PANNs metadata.**
   - Used to stratify and compare against fallback model labels, not as ground
     truth where detectors disagree.

## A-prime Sample Sets

`paper_prep/validation_A_prime/A_PRIME_MANIFEST.csv` contains all recoverable
and expected A-prime rows with `exists=true/false`:

- 500 stratified random clips.
- 34 rare-basin human-package source clips.
- 40 rare-clean protected/package clips.
- Phase0 label packet rows from existing/extracted media where available.

As of manifest build, 716/816 rows are directly judgeable; 100 phase0 rows are
still missing direct audio. Those missing rows block full A-prime PASS.

## B-prime Sample Sets

`paper_prep/validation_B_prime/B_PRIME_MANIFEST.csv` selects the pre-registered
80 gate pairs:

- 40 `arm6_vs_arm1`.
- 40 `arm6_vs_arm4`.
- Stratified by tail/lyric/general as 16/13/11 per contrast.
- All 80 pairs have both audio files present.

## Aggregation

- A-prime: 3 model calls per clip, majority vote. Abstain if no yes/no majority.
- B-prime: both A/B and B/A order calls per pair, each with Q1/Q2/Q3. Primary
  quality endpoint is Q1 overall preference.
- Missing audio rows are not silently dropped; they are listed and block full
  PASS.
- Human responses, if later provided, supersede model fallback labels under the
  frozen human-study criteria.

## Pass/Fail Criteria

Primary PASS is not allowed unless:

- A-prime missing audio is resolved or formally removed by PI-approved protocol.
- Human/validated-judge adjudication exists for the required disagreement,
  rare-basin, agreement, and 500-sample sets.
- B-prime has a usable judge or human ratings and satisfies the frozen binomial
  criteria.

Fallback outputs can support reduced wording only:

- Allowed: "automatic fallback adjudication was prepared/scored; full human or
  validated-judge gate remains pending."
- Forbidden: "A-prime passed", "B-prime passed", "human studies confirmed",
  or "no audible quality cost".

## Execution Status

`FALLBACK_STATUS = EXECUTING`

