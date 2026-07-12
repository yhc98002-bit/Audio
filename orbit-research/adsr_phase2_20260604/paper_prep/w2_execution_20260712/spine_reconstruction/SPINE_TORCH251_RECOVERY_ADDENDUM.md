# W2 Spine torch-2.5.1 Recovery Addendum

Date: 2026-07-12

`SPINE_TORCH251_RECOVERY_STATUS = PREREGISTERED_BEFORE_REPLAY`

## Trigger

The first complete W2 reconstruction generated and scored all 4,096 rows, but its frozen audit failed exact fidelity:

- surviving original replay: 0/1 exact decoded hashes;
- regeneration controls: 0/50 exact decoded hashes;
- generation environment: torch/torchaudio 2.7.1+cu126.

The frozen controls were generated under torch/torchaudio 2.5.1+cu121. Prompt serialization, ACE-Step checkpoint, ACE-Step source commit, scheduler, seed, CFG, step count, and guidance interval match. The shared `audio-prm` environment was upgraded after the control run, so the torch/CUDA runtime is the concrete unresolved difference.

The first 32 GiB reconstruction, its append-only ledgers, scores, and failed audit remain preserved under `spine_reconstruction/`. They are invalid for fidelity-backed W2 promotion and may not be silently substituted into the original spine.

## Isolated Runtime

- Environment: `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion_envs/w2-torch251`
- Base: system-site-packages view of `audio-prm`, overridden only by torch 2.5.1+cu121, torchaudio 2.5.1+cu121, and torchvision 0.20.1+cu121.
- Shared `audio-prm` is not mutated.
- Install log: `spine_reconstruction/logs/torch251_env_install_an29.log`.

## Fail-Closed Probe

Before a full replay, regenerate exactly:

1. all 50 rows in `REGENERATION_CONTROL_MANIFEST.csv`; and
2. the lone surviving-original task `dev_0000__cand00`.

Use the frozen source seeds, canonical prompt serialization, ACE-Step v1 checkpoint, 30 steps, CFG 5.0, `cfg_type=cfg`, guidance interval 0.5, bf16, and no ERG. These are historical exact replays, not a new seed base.

The probe passes only at 51/51 exact decoded-audio hashes, with no failed, missing, near-silent, short, or undecodable output. Any miss stops recovery and preserves `SPINE_REGEN_STATUS = FAILED_ESCALATED`.

## Conditional Full Replay

Only after the probe passes may the 4,096-task manifest be replayed into a new root:

`paper_prep/w2_execution_20260712/spine_reconstruction_torch251_recovery/`

The prior output root must not be overwritten. The full replay must repeat all waveform/container hashes, decode metadata, old/current scoring, candidate Demucs-and-PANNs scoring, 50-control exact checks, and surviving-original exact check. The reconstructed spine, recompute tables, EVPD manifest, and t6 package remain noncanonical until that complete recovery audit passes. `PLAN.md` and all claim statuses remain unchanged.
