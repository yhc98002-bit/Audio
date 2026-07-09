# SAO Execution Plan

Generated: 2026-07-07

## Objective

Execute the Stable Audio Open second-model spike on `an29` with actual attempted
model installation and smoke generation. The previous shared-env blocker is not
treated as final.

## Environment Strategy

Primary strategy: create a dedicated conda environment named `audio-prm-sao` in
the user conda env directory.

Fallback order:

1. Dedicated env: `audio-prm-sao`, Python 3.10, `stable-audio-tools==0.0.20`.
2. Clone or approximate `audio-prm` into a separate env and mutate only the clone.
3. Local venv under `paper_prep/sao/envs/`.
4. Use an existing non-project env with compatible torch, after recording versions.
5. Mutate an expendable working env only if all clean routes fail, with package
   diffs recorded.

Shared `audio-prm` is not the first target, but environment mutation is
authorized if all isolated routes fail.

## Initial Commands

Run on `an29` in tmux session `sao_env_20260707`:

```bash
cd /XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion
mkdir -p paper_prep/sao/logs paper_prep/sao/smoke paper_prep/sao/prevalence paper_prep/sao/observability paper_prep/sao/intervention
bash paper_prep/sao/run_sao_env_install.sh
```

The install script tries dedicated conda first, records `conda list`, `pip
freeze`, CUDA visibility, and import checks, then leaves a concrete status file.

## Model Source

- Model: `stabilityai/stable-audio-open-1.0`
- Package: `stable-audio-tools==0.0.20`
- Local wrapper: `src/mprm/inference/sao.py`
- Smoke runner target: `scripts/d1_model_load.py --model sao_1_0`

## Expected Output Paths

- Env install log: `paper_prep/sao/logs/sao_env_install_20260707.log`
- Env status: `paper_prep/sao/SAO_ENV_STATUS_20260707.json`
- Smoke ledger: `paper_prep/sao/smoke/SAO_SMOKE_LEDGER.jsonl`
- Smoke report: `paper_prep/sao/smoke/SAO_SMOKE_REPORT.md`
- Smoke audio: `paper_prep/sao/smoke/audio/`
- Prevalence: `paper_prep/sao/prevalence/SAO_PREVALENCE_*`
- Observability: `paper_prep/sao/observability/SAO_OBSERVABILITY_*`
- Intervention: `paper_prep/sao/intervention/SAO_INTERVENTION_*`

## Smoke Criteria

PASS only if:

- `stable_audio_tools` imports.
- SAO model loads or reaches an authenticated/model-access boundary with exact
  provider error logged.
- One prompt generation runs to completion.
- Output audio exists, is non-empty, decodable, and has recorded sample rate and
  duration.
- `SAO_SMOKE_LEDGER.jsonl` contains a PASS row.

## Full Scan Criteria

After smoke PASS, run 128 prompts x 8 seeds first. Scale to 500 x 8 only if
throughput and storage are acceptable. The scan must compute a dominant failure
mode instead of assuming vocal/instrumental.

## Current Status

`SAO_STATUS = EXECUTION_STARTED`

