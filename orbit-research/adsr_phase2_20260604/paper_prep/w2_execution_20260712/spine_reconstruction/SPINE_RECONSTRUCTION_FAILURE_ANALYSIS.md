# W2 Spine Reconstruction Failure Analysis

`SPINE_RECONSTRUCTION_FAILURE = RUNTIME_FIDELITY_MISMATCH`

## Exact Evidence

- Full generation: 4,096/4,096 PASS; 0 invalid media; 0 near-silent media.
- Full scoring: 4,096 unique PASS rows; four deterministic handoff duplicates; zero score conflicts.
- Frozen control exactness: 0/50 decoded-waveform hashes.
- Surviving-original exactness: 0/1 decoded-waveform hashes.
- Historical-versus-recomputed current-detector flips: 85/4,096.
- Failed run runtime: Python 3.10.20, torch/torchaudio 2.7.1+cu126.
- Exact July 10 control runtime: Python 3.10.20, torch/torchaudio 2.5.1+cu121.

The canonical prompt rows used by the failed run are byte-equivalent to the current `configs/prompts/dev.jsonl` and `held_out.jsonl` rows, including all checked frozen-control prompts. The ACE-Step checkpoint, upstream source commit, seed, 30-step scheduler, CFG 5.0, `cfg_type=cfg`, guidance interval 0.5, bf16 setting, and no-ERG flags match the frozen protocol.

The torch/CUDA runtime change is therefore the concrete remaining implementation difference and the preregistered recovery target. It is not declared causal until the 51-item torch-2.5.1 probe passes. The shared `audio-prm` runtime was upgraded after the July 10 control run; recovery uses a new isolated environment and does not downgrade or mutate the shared environment.

## Consequence

The generated audio and all ledgers remain preserved, but this cohort is invalid for reconstructing the original 4,096-candidate spine. The current recompute, EVPD manifest, and t6 package are implementation-plumbing artifacts only. They cannot promote a detector, alter `PLAN.md`, or support corrected prevalence until either:

1. the isolated 2.5.1 probe and full replay both pass exact fidelity; or
2. both PIs explicitly approve a scientifically different regenerated-target analysis in a signed supersession.

## Recovery

Follow `SPINE_TORCH251_RECOVERY_ADDENDUM.md`. A full replay is fail-closed on 51/51 exact probe rows.
