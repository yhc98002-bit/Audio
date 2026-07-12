# W2 Spine Reconstruction Protocol

Frozen before full launch: 2026-07-12

## Identity

- Historical dataset spine: `orbit-research/trajectory_candidate_dataset.jsonl`
  (4,096 unique `(prompt_id, candidate_index, candidate_seed)` rows).
- Reconstruction manifest SHA256:
  `327001b2f31cc3e73765a80377b6a2b57655afaabee52910ce6c1c99eae95466`.
- Canonical prompt snapshot SHA256:
  `a616137db58e2e639c2c2665688b72fb0d3c06253cc0266763e52107b79558a6`.
- Frozen worker commit:
  `72f5fc9b48bedf2ec7cd62d447af3f47e3c28afc`.
- Upstream ACE-Step commit:
  `1bee4c9f5b43e30995f8d4d33b3919197ce1bd68`.
- Model: `ACE-Step/ACE-Step-v1-3.5B` at
  `/HOME/paratera_xy/pxy1289/.cache/modelscope/hub/models/ACE-Step/ACE-Step-v1-3___5B`.

## Frozen Sampling Contract

- exact historical candidate seed from each manifest row;
- canonical prompt JSON serialized from `configs/prompts/dev.jsonl` or
  `configs/prompts/held_out.jsonl`, with per-prompt SHA256 in every row;
- prompt-specific canonical duration target;
- 30 inference steps;
- CFG scale 5.0;
- CFG type `cfg`;
- guidance interval 0.5;
- Euler flow-matching scheduler with shift 3.0, inherited from the frozen
  ACE-Step v1 adapter/model configuration;
- bfloat16 inference;
- ERG tag, lyric, and diffusion controls disabled; and
- final waveform only for the 4,095 missing candidates.

Each append-only generation row records host, GPU, CUDA visibility, Python,
torch/CUDA, repository/upstream commits, prompt hash, parameters, output path,
container SHA256, decoded-audio SHA256, duration, sample rate, RMS, near-silence,
elapsed time, and status.

## Fidelity Gates

The independent 50-control manifest SHA256 is
`0beda08bae2c4173821e1808616d677840cb958eabe0c9ea3a0a5e86c33ebbea`.
All 50 controls must match reconstructed outputs by decoded-audio hash. The one
June survivor is audited separately. Its unresolved first-candidate mismatch is
a hard failure even if all 50 controls pass; it cannot be converted to a warning.

## Scoring Contract

After generation, every row is scored with:

- the current Demucs vocal-energy score and threshold 0.1791;
- continuous Demucs and PANNs scores;
- the candidate Demucs-and-PANNs rule at thresholds
  0.038639528676867485 and 0.03181814216077328; and
- direction-aware Label-B violation for vocal versus instrumental request.

Candidate scores remain sensitivity-only until the signed W2 promotion gate.
