# Model Identity Audit

`MODEL_IDENTITY_STATUS = RESOLVED_ACE_STEP_V1`

## Decisive Finding

The ACE-Step evidence in Batch 1, Batch 3, Stage 3, N2, the retry atlas, and
phase 0 was generated with the original ACE-Step v1 code and the
`ACE-Step/ACE-Step-v1-3.5B` checkpoint. It was not generated with ACE-Step
v1.5. Batch 2 is a read-only analysis family over Batch-1 outputs and therefore
inherits the Batch-1 backbone identity.

The logical adapter name `ace_step_v1_5` is misleading. The adapter module
explicitly says it binds upstream v1, its `UPSTREAM_REPO_ID` is
`ACE-Step/ACE-Step-v1-3.5B`, and the upstream pipeline hard-codes the same
repository ID. No audited worker bypasses `AceStepModel` to load a different
ACE-Step backbone.

## Shared Model Provenance

| Field | Audited value |
|---|---|
| Project adapter | `src/mprm/inference/ace_step.py` |
| Imported class | `mprm.inference.ace_step.AceStepModel` |
| Misleading logical class name | `ace_step_v1_5` |
| Actual upstream source | `/XYFS02/HDD_POOL/paratera_xy/pxy1289/source/ACE-Step/acestep/pipeline_ace_step.py` |
| Upstream repository | `https://github.com/ace-step/ACE-Step.git` |
| Upstream checkout | `1bee4c9f5b43e30995f8d4d33b3919197ce1bd68` |
| Upstream model ID | `ACE-Step/ACE-Step-v1-3.5B` |
| Logged checkpoint directory | `/HOME/paratera_xy/pxy1289/.cache/modelscope/hub/models/ACE-Step/ACE-Step-v1-3___5B` |
| Scheduler | `FlowMatchEulerDiscreteScheduler`, `scheduler_type=euler`, `shift=3.0` |
| Standard inference budget | 30 steps, guidance scale 5.0 |
| Historical shared runtime | Python 3.10; torch 2.5.1+cu121; torchaudio 2.5.1+cu121; CUDA build 12.1 |
| Current mutated login runtime | Python 3.10.20; torch 2.7.1+cu126; torchaudio 2.7.1+cu126; CUDA unavailable on login host |

The historical runtime values are documented in
`paper_prep/execution_20260707/EXECUTION_LEDGER.md` and
`paper_prep/execution_20260707/STAGE4_SAO_BLOCKED_20260707.md`. The shared
environment was subsequently upgraded for SA3, so the current package versions
must not be substituted for the generation-time values.

## Weight Checksums

The checkpoint path logged by generation workers contains these primary
weights:

| Component | Bytes | SHA256 |
|---|---:|---|
| `ace_step_transformer/diffusion_pytorch_model.safetensors` | 6,611,422,728 | `e810f16728d8a2e0d1b9c3a907aac8c9a427ce38edbd890cb3dce5ff92da5aad` |
| `music_dcae_f8c8/diffusion_pytorch_model.safetensors` | 313,646,516 | `2b0cb469307ac50659d1880db2a99bae47d0df335cbb36853964662d4b80e8ee` |
| `music_vocoder/diffusion_pytorch_model.safetensors` | 206,350,988 | `c92c9b46e28ab7b37b777780cf4308ad7ddac869636bb77aa61599358c4bc1c0` |
| `umt5-base/model.safetensors` | 1,127,460,248 | `779cec0d210b2123e21d0a9cd8128f02b4d412627355028965a8be0b241cc3b6` |

The checkpoint files predate all audited run families. Representative run logs
explicitly print the same checkpoint directory. No per-run copy of these
weights was created.

## Run-Family Reconciliation

| Run family | Generation or analysis entry point | Model-loading evidence | Scheduler/config evidence | Verdict |
|---|---|---|---|---|
| Batch 1, 4,096 trajectories | `scripts/collect_early_tweedie_validation.py` | Imports and instantiates `AceStepModel`; `runs/early_tweedie_validation_512_bon8_20260527_full01/shard00_stderr.log` prints the audited ModelScope path | `run_summary.json`: 30 steps, CFG 5.0, `cfg_type=cfg`; captured sigma sequence matches shift-3 Euler | ACE-Step v1 |
| Batch 2, EVPD/offline replay | `scripts/batch2_stage1_typeerror.py`, `scripts/batch2_stage3_evpd.py`, `scripts/batch2_stage4_adsr_sim.py` | No generation model is loaded; analyses frozen Batch-1 records | Inherits Batch-1 trajectories and scheduler | ACE-Step v1 inherited |
| Batch 3, online ADSR | `scripts/batch3_online_harness.py` | Imports and instantiates `AceStepModel`; direct upstream import is limited to a scheduler-step capture hook | 30-step Euler through adapter; `cfg_type=apg`, guidance interval 0.5 | ACE-Step v1 |
| Stage 3 intervention | `paper_prep/scripts/stage3_intervention_worker.py` | Imports and instantiates `AceStepModel`; `paper_prep/stage3_intervention_20260707/logs/full64_w0.log` prints the audited ModelScope path | 30 steps, CFG 5.0, APG, shift-3 upstream Euler | ACE-Step v1 |
| N2 population retry | `paper_prep/scripts/population_retry_worker.py` | Imports and instantiates `AceStepModel`; worker family uses the same shared adapter/cache | 30 steps, CFG 5.0, APG, shift-3 upstream Euler | ACE-Step v1 |
| Retry atlas | `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/core_largeN_worker.py` | Imports and instantiates `AceStepModel`; worker logs print the audited ModelScope path | 30 steps, CFG 5.0, APG, shift-3 upstream Euler | ACE-Step v1 |
| Phase 0 respawn screen | `scripts/phase0_respawn_screen.py` | Imports and instantiates `AceStepModel`; `phase0/respawn_screen/gen.log` prints the audited ModelScope path | 30 steps, CFG 5.0, APG, shift-3 upstream Euler | ACE-Step v1 |

## Bypass Audit

The relevant workers were searched for direct pipeline construction and model
imports. All generation paths instantiate `AceStepModel`. Batch 3 also imports
`FlowMatchEulerDiscreteScheduler` directly, but only to intercept scheduler
steps for early probing; model construction and checkpoint loading still occur
through `AceStepModel`.

## Consequences

1. Paper, methods, tables, and limitations must identify the frozen primary
   backbone as ACE-Step v1 (`ACE-Step/ACE-Step-v1-3.5B`).
2. Existing historical files are frozen and must not be rewritten. A
   supersession note must correct later-facing documentation.
3. The project must not imply that frozen v1 evidence came from v1.5.
4. D6 triggers T9: a bounded v1.5 replication is mandatory after T0-T6 are
   stable, using registered seed base `2033000000` and a 72-hour hard stop.

## Audit Status

`RESOLVED_ACE_STEP_V1`. The identity discrepancy changes backbone scope but
does not invalidate the internal comparisons within the frozen v1 evidence.
