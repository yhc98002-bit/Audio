# Stage 4 SAO Blocker

Status: **BLOCKED**

## Finding

- an29 sees CUDA and imports `mprm.inference.sao`.
- `stable_audio_tools` is missing in `audio-prm`.
- `pip install --dry-run stable-audio-tools` resolves to `stable-audio-tools==0.0.20`
  and would install/upgrade torch to `2.7.1`, torchaudio to `2.7.1`, torchvision,
  triton, and a large CUDA 12.6 dependency stack.

## Decision

Do not mutate the shared `audio-prm` environment while Stage 3 is running on
torch `2.5.1+cu121`. Stage 4 SAO generation should use one of:

- a separate conda env for SAO,
- a pinned/no-deps install after compatibility testing,
- or prebuilt SAO tooling outside `audio-prm`.

Until then, an29 cannot run the Stable Audio Open prevalence scan safely.
