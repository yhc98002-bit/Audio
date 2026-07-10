# T9 ACE-Step 1.5 Replication Plan

`V15_REPLICATION_STATUS = COMPLETE`

## Scope

T9 is the bounded second-version replication triggered by T0's finding that
the frozen ADSR evidence uses ACE-Step v1 rather than v1.5. The run is capped
at 72 hours and uses the reserved seed base `2033000000`.

1. Build an isolated Python 3.11 environment from the official ACE-Step 1.5
   lockfile and pin the official source revision.
2. Download `ACE-Step/Ace-Step1.5` through ModelScope into external model
   storage. Do not place model weights in Git.
3. Pass one instrumental and one vocal smoke on `an12`, including audio decode,
   non-silence, model identity, seed, and runtime checks.
4. Generate 128 selected held-out prompts x 8 disjoint seeds. This is a
   difficult/stratified replication set, not a generic population sample.
5. Canonically score vocal presence and identify the hardest prompts under
   ACE-Step 1.5.
6. Run a focused retry map on the hardest prompts and one matched
   baseline-versus-reconditioning intervention.
7. Deduplicate by `(prompt_id, condition, seed)` and fail closed on missing,
   duplicate, generation-error, decode-error, or near-silent rows.

## Frozen Runtime Choices

- Official source: `ace-step/ACE-Step-1.5`.
- DiT: `acestep-v15-turbo`.
- Inference: ODE, 8 steps, shift 3.0, batch size 1.
- Prevalence seeds: `2033000000 + prompt_index * 8 + seed_idx`.
- Detector rule: project canonical Demucs vocal-energy ratio, present at
  `ratio >= 0.1791`, near-silent at RMS `< 1e-3`.
- Prompt set: the frozen 128-row N2 difficult/stratified manifest, preserving
  vocal/instrumental request strata.

## Recovery Policy

ModelScope is the download source. The requested local proxy at port 3138 is
tested first; if no listener exists, the active working login-node proxy is
used and recorded. Hugging Face is not used as an unrecorded fallback. A failed
smoke is repaired before scale generation.

## Completed Outputs

- Smoke report: `smoke/V15_SMOKE_REPORT.md`.
- Prevalence report: `prevalence_analysis/V15_PREVALENCE_REPORT.md`.
- Focused retry report: `retry_analysis/V15_RETRY_REPORT.md`.
- Matched intervention report:
  `intervention_analysis/V15_INTERVENTION_REPORT.md`.
- Final cross-stage audit: `V15_FINAL_REPLICATION_REPORT.md`.
- Attempt audit and audio hashes: `V15_ATTEMPT_AUDIT.csv` and
  `V15_AUDIO_MANIFEST.csv`.

Bulk retry/intervention audio is stored outside Git at
`/HOME/paratera_xy/pxy1289/ADSR_T9_20260709`. Raw generation and score ledgers
were copied into `valid_ledgers/` so the report does not depend on external
terminal state.
