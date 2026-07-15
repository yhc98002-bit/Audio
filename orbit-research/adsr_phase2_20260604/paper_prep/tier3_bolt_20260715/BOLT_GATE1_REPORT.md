# BOLT Gate 1 Report

GATE0_STATUS = PASS
ENVIRONMENT_PARITY_STATUS = PASS
RESUME_EQUIVALENCE_STATUS = PASS
CONDITION_SWITCH_STATUS = PASS
FORK_STATUS = PASS
ACTUAL_NFE_STATUS = PASS
TRUE_ROLLOVER_STATUS = PASS
COMPLETION_RESERVE_STATUS = PASS
ROOT_TRAJECTORIES = 96
CHECKPOINT_STATES = 288
PILOT_ACTION_OUTCOMES = 1440
BEST_STATIC_CQS60 = 0.745199693
ORACLE_CQS60 = 0.931451613
ORACLE_HEADROOM_CQS60 = 0.186251920
ORACLE_HEADROOM_LCB95 = 0.096069007
ORACLE_COMPUTE_SAVING = 0.342115277
ORACLE_NONSTATIC_PROMPT_SHARE = 1.000000000
BOLT_GATE1 = GO_ACTION_VALUE_LEARNING
TEST_SUITE_STATUS = PASS

Branch: `codex/tier3-bolt-gate01-20260715`. Analysis-parent commit: `bc302b6feb6ebf72732a7312c5bd710bc03b51f8`. The containing final Git commit is reported by the immutable branch ref because a commit cannot embed its own SHA.

Prompt IDs: `dev_0026, dev_0038, dev_0054, dev_0073, dev_0074, dev_0083, dev_0087, dev_0121, dev_0150, dev_0187, dev_0221, dev_0254, dev_0010, dev_0041, dev_0080, dev_0095, dev_0130, dev_0133, dev_0137, dev_0140, dev_0144, dev_0147, dev_0160, dev_0174, dev_0028, dev_0030, dev_0033, dev_0070, dev_0126, dev_0142, dev_0159, dev_0162, dev_0194, dev_0212, dev_0243, dev_0244, dev_0011, dev_0017, dev_0023, dev_0031, dev_0050, dev_0075, dev_0097, dev_0107, dev_0152, dev_0181, dev_0217, dev_0239`. Seed namespace: `2060000000`.

Quality floors: `paper_prep/tier3_bolt_20260715/BOLT_QUALITY_FLOORS.json`. Static table: `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_STATIC_PROGRAM_TABLE.csv`. Oracle table: `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_ORACLE_ACTION_TABLE.csv`. Strata: `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_ORACLE_STRATUM_RESULTS.csv`.

Decision checks: headroom=True; compute-saving=True; nonstatic=True. No Gate 2 work was launched.

## Frozen runtime identity

- Python: `3.10.20`; torch/torchaudio: `2.5.1+cu121`; CUDA build: `12.1`.
- ACE-Step declared source commit: `1bee4c9f5b43e30995f8d4d33b3919197ce1bd68`.
- ACE-Step source manifest: `203e623b252592794e667015ca51cab23d9bfdf74ad56c98efca5d4c2cf179ab`.
- ACE-Step checkpoint manifest: `2058d6c10bd348da51669ff3886c6b4080405fe4c23bb3de183c293cb5f0bef9`.
- Scheduler source: `d3d724dec32d4f2d3df62d4dc9de30c1b74c0d2602e19063ec00031e2f7ebe8d`.
- Promoted W2 instrument record: `2ec9f12fd9008dae0e32675fcdaaf9e7a22fe0ed7006dd310b665b1e82be2ff2`.
- Quality policy: `34db933b67d06f3acc3780e70b2f492a20d685ef710777fc81eaffba1d2806e9`.
- Generation-time BOLT code manifest: `6125c3f6b11dedefcb2728ed9c61f5f7d0fe1d63f5e881ecdecfddfd4e1ee48d` at inference commit `9ffc191266dcf24dd8f76d39e4f0c734656dee75`.
- Cross-node environment hash: `d1c44cb0fec1fa4347ba3b0908cab561ebbbbba648026c57c0b79aeffb0df542`.

Both nodes independently reported these values before GPU generation. The later analysis-only hardening changed `bolt_oracle_headroom.py` and its tests, not inference, scoring, frozen floors, atlas rows, or thresholds.

## Compute and state contract

One ordinary 30-step generation measured `45` raw transformer calls, so the pilot budget was `B_NFE = 90`. Checkpoint continuations from steps 6, 12, and 18 measured `39`, `28`, and `16` calls. Gate 0 passed 48/48 exact resume controls with zero Label-B or quality-floor flips, maximum waveform NRMSE `0`, minimum deterministic CLAP audio-audio cosine `0.9999999999999999`, and exact latent save/load hashes. Fork eta `0.025` was frozen before the pilot.

## Quality floors

No BOLT output influenced the floors. They are linear 10th percentiles over pre-existing development outputs that satisfied the promoted Label-B instrument:

| Request direction | Eligible rows | Common robust LCB floor | CLAP-to-original-prompt floor |
|---|---:|---:|---:|
| Instrumental | 363 | 2.015776147752155 | 0.21262885928153993 |
| Vocal | 1,253 | 1.8113942439593411 | 0.14700739681720734 |

The complete 1,616-row source identity list and hashes are in `BOLT_QUALITY_FLOOR_SOURCE_ROWS.jsonl` and `BOLT_QUALITY_FLOORS.json`.

## Pilot identity and integrity

The prompt sample contains 48 development prompts only, with 12 in each frozen risk/request stratum. Sampling used frozen risk evidence, genre-cell allocation, exact inclusion probabilities, and inverse-probability design weights. The seed collision audit rejected occupied bases `2040000000` and `2050000000`; the collision-free namespace is `2060000000`, and no seed depends on action order.

Strict audit results are 96 unique roots, 288 unique checkpoint states, 1,440 unique action outcomes, zero missing/duplicate/conflicting/error keys, and 1,248 unique decoded media files with zero checksum or decode errors. Canonical ledger SHA256 values are:

- roots: `090b7aaa471e9ca02abe73d746cf0a3ff900579ba08f3080634cd2f67773404d`;
- states: `adea9f62327537b3e7eb2f096d33e21ac0e67253ade1ee6156bc193228c85781`;
- actions: `934d63566421b4bcf3e6b60f42155cdb5f3445cb03c9353a79065a76f129196b`.

## Static and oracle result

The best globally feasible fixed program was the frozen W2 two-slot policy. The design-weighted oracle headroom is `0.186251920`; its one-sided prompt-bootstrap 95% lower bound is `0.096069007`. Matched-CQS compute saving is `0.342115277`, with lower bound `0.275409155`. The frozen nonstatic-program share is `1.000000000`.

Equal-stratum diagnostic CQS@60 is `0.679135818` static and `0.959865196` oracle. Stratum headroom is `0.380208` high-risk instrumental, `0.419355` medium-risk instrumental, `0.235119` low-risk instrumental, and `0.088235` vocal. The full static table, state/per-root/full-tree oracle table, and 10,000 prompt-bootstrap replicates are tracked beside this report.

## Node utilization and recovery

`an12` produced 48 roots and 720 outcomes on GPUs 4–7; GPUs 0–3 were occupied by pre-existing work and were not preempted. `an29` produced 48 roots and 720 outcomes on GPUs 0–7. There were zero failed or recovered workers. The 98 successful attempt-completion entries comprise 96 unique roots and two idempotent preflight redispatch confirmations; canonical ledgers contain no duplicates. See `BOLT_NODE_UTILIZATION_REPORT.md` and both heartbeat logs.

## Tests

The final focused BOLT suite passed 27/27 in 80.81 seconds. The final canonical repository suite passed 355/355 in 331.24 seconds. There were no skips. Commands, the one recovered test-assumption failure, and logs are in `BOLT_TEST_REPORT.md`.

## Files changed

This branch adds or updates only `paper_prep/tier3_bolt_20260715/`: method/preregistration and seed records; frozen environment and floor records; inference/state/scoring/budget/worker code; focused tests; Gate 0 controls and reports; prompt frame and manifest; append-only root/state/action ledgers; preflight, audit, static, oracle, bootstrap, node, test, and Gate 1 reports; and execution/heartbeat logs. Generated FLAC and checkpoint tensors remain at the artifact paths referenced by the ledgers and are not Git payloads.

## Deviations and limitations

- `an12` used four rather than eight BOLT workers because GPUs 0–3 were already occupied. Root ownership and the frozen design were unchanged.
- A simple-random prompt preflight was rejected before pilot generation because it failed the frozen genre-balance requirement. It is preserved with `_simple_random_preflight_rejected` filenames; the canonical manifest uses the preregistered genre-cell design.
- Post-audit and before inspecting CQS summaries, analysis code was hardened to reject empty oracle programs, apply the exact physical-leaf nonstatic definition, expose per-root subsets, and add interval/structural diagnostics. Thresholds and outcomes were unchanged.
- One focused test initially encoded an incorrect 45-NFE expectation for a zero-CQS but positive-option case. The failed run is preserved; the corrected completion-reserve assertion passes.
- The tree oracle is outcome-aware, uses development prompts, and is an upper bound rather than a learned or prospective policy result. No held-out prompt, policy training, full atlas, live BOLT pilot, transfer experiment, or Gate 2 work was run.
- The globally fixed conditioned programs are infeasible for all 12 vocal prompts under the measured 90-NFE budget because vocal guidance raises per-generation NFE; they are reported but excluded from best-feasible-static selection.
- `ORACLE_NONSTATIC_PROMPT_SHARE` compares exact selected physical leaf sets. It establishes structural program heterogeneity in this pilot but does not estimate future policy accuracy.

## Commit convention

The final immutable commit is the pushed branch tip reported in the PI response. A tracked file cannot contain the SHA of the commit that contains that same file without changing the SHA; this report therefore records the inference commit and analysis-parent commit above, while the final branch tip is authoritative for the complete package.
