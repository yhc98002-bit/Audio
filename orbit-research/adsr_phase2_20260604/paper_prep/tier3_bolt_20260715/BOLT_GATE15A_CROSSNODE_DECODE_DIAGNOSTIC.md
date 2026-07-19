# BOLT Gate 1.5A Cross-Node Decode Diagnostic

DIAGNOSTIC_STATUS = PASS_NO_CROSSNODE_DIFFERENCE

## Trigger

The first canonical worker on `an12:1` encountered the existing `an29:6`
smoke preview for state `dev_0026__seed2060000000__step06`. The legacy
recovery check compared the new unquantized decoder tensor directly with the
24-bit decoded FLAC at waveform NRMSE `1e-6` and rejected it. Neither artifact
was overwritten.

## Independent comparison

The same persisted state was decoded and scored into a separate path on
`an12:1`. Comparison with the `an29:6` smoke result found:

- sample rate equal: yes;
- waveform shape equal: yes;
- decoded-waveform NRMSE: `0.0`;
- FLAC SHA-256 equal: yes;
- FLAC SHA-256: `c75530292aeaa85ac7a009efeb29d1b7d28c1b41933e2d392acaba6126757e07`;
- Demucs-score delta: `0.0`;
- PANNs-score delta: `0.0`;
- calibrated-violation-probability delta: `0.0`;
- CLAP-to-prompt delta: `0.0`;
- promoted-decision delta: `0`.

Evidence is preserved in `gate15a_feature_smoke/smoke.jsonl`,
`gate15a_crossnode_diagnostic/an12.jsonl`, their referenced FLACs, and
`gate15a_logs/feature_worker_0_of_8_an12_gpu1.log`.

## Recovery correction

`save_audio_once` now encodes the candidate tensor to a temporary 24-bit FLAC
and compares the candidate and existing encoded audio, including exact file
SHA-256 and decoded NRMSE. It never overwrites the existing artifact. A focused
regression test covers low-amplitude valid audio whose unquantized-versus-FLAC
relative error can exceed the old threshold.

This was an idempotent-recovery validation defect, not a latent-decoding,
environment-parity, or scientific-feature discrepancy. Worker 0 was rerouted
to `an29:6`; completed shard rows from other workers were retained.
