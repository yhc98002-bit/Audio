# Escalation T0: Frozen Evidence Is ACE-Step v1

## Trigger

The audited backbone identity is not ACE-Step v1.5.

## Exact Evidence

- `src/mprm/inference/ace_step.py` states that the adapter binds upstream v1
  and sets `UPSTREAM_REPO_ID = "ACE-Step/ACE-Step-v1-3.5B"`.
- The upstream checkout at commit
  `1bee4c9f5b43e30995f8d4d33b3919197ce1bd68` hard-codes the same repository ID.
- Batch-1 and Stage-3 generation logs explicitly load
  `/HOME/paratera_xy/pxy1289/.cache/modelscope/hub/models/ACE-Step/ACE-Step-v1-3___5B`.
- Every audited generation worker instantiates `AceStepModel`; no alternate
  v1.5 loader was found.
- Full hashes are frozen in
  `paper_prep/model_identity/MODEL_IDENTITY_AUDIT_20260709.md`.

## Impact

Claims remain internally comparable on one backbone, but backbone naming and
scope are wrong wherever the artifacts are called ACE-Step v1.5. A v1.5
robustness claim cannot be made from the frozen runs.

## Required Recovery

1. Add supersession-facing documentation without editing frozen historical
   reports.
2. Relabel current paper-planning documents to ACE-Step v1.
3. Run T9 after T0-T6 stabilize: 128 prompts x 8 seeds on actual ACE-Step v1.5,
   a focused retry map, and one matched reconditioning intervention, with seed
   base `2033000000` registered before launch.

## PI Decision

No immediate decision is required to continue recovery. Dual-PI approval is
needed only if the paper is to retain a v1.5 claim before T9 supplies evidence.
