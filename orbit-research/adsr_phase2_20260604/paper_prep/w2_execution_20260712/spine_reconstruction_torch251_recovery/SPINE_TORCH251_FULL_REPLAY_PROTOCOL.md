# W2 Spine torch-2.5.1 Full Replay Protocol

`SPINE_TORCH251_FULL_REPLAY_PROTOCOL = FROZEN_BEFORE_GENERATION`

## Authorization Gate

- Fidelity probe: `PASS_EXACT_51_OF_51`.
- Frozen controls exact: 50/50.
- Surviving original exact: 1/1.
- Valid, non-near-silent media: 51/51.
- Probe audit SHA256: `7d893d6f522cedcd6e5f7cf63e42e0f820c786b116b8e969daacc720a483e3b4`.

This mechanical gate authorizes the full replay under `SPINE_TORCH251_RECOVERY_ADDENDUM.md`. It does not promote the corrected instrument or change `PLAN.md`.

## Frozen Inputs

- Repository commit before generation: `99c88de3762d05d6c4a1fd8a57254d9c0df38ef9`.
- ACE-Step upstream commit: `1bee4c9f5b43e30995f8d4d33b3919197ce1bd68`.
- ACE-Step checkpoint: `ACE-Step-v1-3___5B` from the existing ModelScope cache.
- Worker SHA256: `238179b8d23123253f16eebc8c0ba324d252b5f3b36682e0d7000b5bd9856c51`.
- Runtime freeze SHA256: `3a9e77416d4e075efe3b480589018dfe8b62fed48d2de4ae657dd476ca6782e2`.
- Manifest SHA256: `b976ea9e3c86cf6345b4c9a8173767bcc89f52d3a5b9d287b872ed5b673639be`.
- Prompt snapshot SHA256: `a616137db58e2e639c2c2665688b72fb0d3c06253cc0266763e52107b79558a6`.
- Tasks: 4,096 unique prompt/candidate identities; 4,095 missing candidates and one surviving-original audit replay.

## Runtime And Generation

- Python 3.10.20; torch/torchaudio 2.5.1+cu121; CUDA build 12.1.
- 16 deterministic workers, workers 0-7 on an12 and 8-15 on an29.
- Each assigned GPU must have at least 10,000 MiB free before launch.
- Historical candidate seeds only; no new seed base.
- 30 steps, CFG 5.0, `cfg_type=cfg`, guidance interval 0.5, bf16, no ERG.
- Output root: `paper_prep/w2_execution_20260712/spine_reconstruction_torch251_recovery/`.
- The failed torch-2.7.1 root is read-only evidence and is not overwritten.

## Completion Gates

1. Generation: 4,096 unique PASS rows, zero failures, zero invalid/checksum-mismatched media, zero short/undecodable/near-silent media.
2. Scoring: 4,096 unique PASS rows under the current detector and candidate Demucs-and-PANNs instrument; all raw duplicates disclosed and no conflicting duplicate score.
3. Fidelity: 50/50 frozen controls exact by decoded hash and 1/1 surviving original exact by decoded hash.
4. Only a complete audit satisfying all three gates may emit `SPINE_REGEN_STATUS = COMPLETE_AUDIT_PASS`.
5. Downstream recompute, EVPD, and t6-v2 artifacts must be generated into new versioned roots after the full audit. Existing blocked artifacts remain preserved.
