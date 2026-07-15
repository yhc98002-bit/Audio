# BOLT Cross-Node Environment Parity

`ENVIRONMENT_PARITY_STATUS = PENDING`

No BOLT GPU generation is authorized by this report yet.

The parity audit will compare `an12` and `an29` for Python, torch, CUDA,
ACE-Step source commit/content hash, checkpoint inventory hash, scheduler source
hash, promoted-instrument record/code hashes, quality-policy and model-artifact
hashes, and the committed BOLT implementation SHA. Any material mismatch must
be corrected before Gate-0 generation.

Frozen target evidence:

- ACE-Step v1 checkpoint family: `ACE-Step-v1-3___5B`;
- generation protocol: 30 steps, CFG 5.0, `cfg`, guidance interval 0.5, bf16;
- promoted instrument record: `paper_prep/autochain_20260712/T6_PROMOTION_RESULT.json`;
- promoted family: Demucs/PANNs `or`, thresholds read only from that record;
- quality gate policy: `configs/eval/gate_v2.yaml.draft` remains a draft file and is not renamed or modified.

Detailed per-node commands, package versions, hashes, differences, and the
final PASS/FAIL determination will be appended before generation.
