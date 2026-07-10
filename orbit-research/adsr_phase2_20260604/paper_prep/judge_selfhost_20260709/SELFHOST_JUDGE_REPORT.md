# Self-Hosted Audio Judge Report

Date: 2026-07-10 (Asia/Shanghai)

Task: T7 self-hosted judge recovery

Host: `an29` (4 x NVIDIA A800 80GB PCIe)

`JUDGE_VALIDATION_STATUS = PI_BLOCKED`

## Outcome

The self-hosted Qwen3-Omni deployment is operational. The selected Instruct
checkpoint was downloaded from ModelScope, checksum-frozen, staged to node-local
memory, loaded with vLLM in bf16 tensor-parallel mode, and exercised on ten audio
files. All ten requests completed without client errors and all ten responses
were parsed by the strict label parser.

This is an infrastructure result, not a judge-validation result. No PI-corrected
truth labels exist in the decisive packet, A-prime package, or B-prime package.
Consequently, sensitivity, specificity, balanced accuracy, MCC, abstention rate,
A-prime scale calls, and B-prime calls were not computed. The judge must not be
used as a calibrated measurement instrument until the human-gold gate passes.

## Model Selection And Custody

The public ModelScope availability check returned:

| Candidate | HTTP result | Decision |
|---|---:|---|
| `Qwen/Qwen3.5-Omni-Light` | 404 | unavailable as a public snapshot |
| `Qwen/Qwen3.5-Omni-Flash` | 404 | unavailable as a public snapshot |
| `Qwen/Qwen3-Omni-30B-A3B-Instruct` | 200 | selected primary judge candidate |
| `Qwen/Qwen3-Omni-30B-A3B-Captioner` | 200 | downloaded secondary candidate |

Both selected snapshots are complete on `an29` under
`/dev/shm/ADSR_QWEN3_OMNI_MODELS/`, with `STAGING_COMPLETE` markers and no
`.incomplete` files. The Instruct snapshot contains 15 weight shards and its
index resolves 28,010 tensors. The Captioner snapshot contains 16 weight shards
and its index resolves 19,743 tensors. Checksums cover 26 Instruct files and 27
Captioner files, excluding each TSV header.

Evidence:

- `MODEL_SELECTION_CHECK.tsv`
- `INSTRUCT_MODEL_CHECKSUMS.tsv`
- `CAPTIONER_MODEL_CHECKSUMS.tsv`
- `stage_qwen_snapshots.sh`
- `logs/model_stage_orchestration.status`
- `logs/Qwen3-Omni-30B-A3B-Instruct_complete_transfer_an29.log`
- `logs/Qwen3-Omni-30B-A3B-Captioner_complete_transfer_an29.log`

## Runtime Recovery

Two failed environment candidates were preserved rather than hidden:

1. The newest unconstrained vLLM resolver selected Torch 2.11/CUDA 13.0, which
   was incompatible with the installed 535-series driver. Its environment is
   preserved at `/dev/shm/adsr_qwen_omni_env_cu130_incompatible_20260710T1655`.
2. vLLM 0.11.0 selected a CUDA 12.8-compatible stack, but that release's model
   registry did not support `Qwen3OmniMoeForConditionalGeneration`. Its
   environment is preserved at
   `/dev/shm/adsr_qwen_omni_env_vllm0110_unsupported_20260710T1702`.
3. vLLM 0.11.1 is the first tested pinned release whose registry includes the
   checkpoint architecture. It installed successfully in
   `/dev/shm/adsr_qwen_omni_env` from a resumable, checksum-verified wheelhouse.

Working environment:

| Component | Value |
|---|---|
| Python | 3.10.20 |
| Torch | 2.9.0+cu128 |
| Torch CUDA runtime | 12.8 |
| vLLM | 0.11.1 |
| Transformers | 4.57.6 |
| qwen-omni-utils | 0.0.9 |
| xformers | 0.0.33.post1 |
| CUDA visible | yes, 8 A800 devices |

Evidence:

- `ENV_HEALTH.txt`
- `ENV_FREEZE.txt`
- `SELFHOST_REQUIREMENTS.txt`
- `RESUMABLE_WHEEL_MANIFEST.tsv`
- `stage_resumable_wheelhouse.sh`
- `logs/vllm_env_install_0111_wheelhouse_final_an29.log`
- `logs/wheelhouse_stage_final_an29.log`

## Service

The primary model was served from the complete local snapshot with bf16,
tensor parallelism 4, maximum model length 32,768, one audio item per prompt,
and deterministic client decoding (`temperature=0`, pinned seed). vLLM resolved
the exact architecture `Qwen3OmniMoeForConditionalGeneration` and exposed the
OpenAI-compatible service as `qwen3-omni-judge` on node-local port 8901.

Before loading, all GPUs reported 2 MiB in use. During the ready service, GPUs
0, 2, 3, and 4 used 65,877-65,949 MiB each; GPUs 1, 5, 6, and 7 remained at 2
MiB. Startup, including one-time Torch compilation, completed in approximately
161 seconds. The service remains in tmux session `adsr_qwen_server` for the
PI-gold continuation.

Evidence:

- `launch_vllm_an29.sh`
- `GPU_MEMORY_BEFORE.tsv`
- `GPU_MEMORY_DURING.tsv`
- `SERVICE_HEALTH.json`
- `logs/vllm_server_an29.log`

## Infrastructure Smoke

The smoke manifest contains ten unique, unlabeled clips. Expected labels were
intentionally removed because the previous labels were not PI-corrected truth.
Each clip was submitted once to test audio decoding, request handling, raw
response capture, and strict parsing.

| Check | Result |
|---|---:|
| Manifest rows | 10 |
| HTTP/client successes | 10/10 |
| Strictly parsed responses | 10/10 |
| Logged errors | 0 |
| Unique clip IDs | 10/10 |
| Embedded base64 payloads retained in raw request ledger | 0 |
| Accuracy metrics | not computed: no PI truth |

The returned labels were nine `yes` and one `no`. That distribution has no
validation meaning without human truth and is not used in any paper claim.

Evidence:

- `SELFHOST_INFRASTRUCTURE_MANIFEST.csv`
- `SELFHOST_INFRASTRUCTURE_SUMMARY.json`
- `../judge_raw/selfhost_qwen3_omni_infrastructure_20260710.jsonl`
- `logs/infrastructure_smoke_an29.log`
- `../scripts/run_selfhost_audio_judge.py`
- `../../../../tests/test_selfhost_audio_judge.py`

## Human-Gold Gate

The fail-closed PI-gold builder requires five PI-rated high-confidence positive
clips and five PI-rated high-confidence negative clips. It found zero in each
class and exited nonzero. The current human inputs are:

| Package | Rows | Completed real ratings |
|---|---:|---:|
| Decisive construct packet | 42 | 0 |
| A-prime original-only primary package | 690 | 0 |
| B-prime package, 80 primary plus 24 reversed | 104 | 0 |

Evidence:

- `logs/pi_gold_builder_current_rerun.log`
- `../pi_decisive_packet_20260709/DECISIVE_PACKET_RATINGS.csv`
- `../validation_A_prime/primary_package_20260709/A_PRIME_PRIMARY_RATINGS.csv`
- `../validation_B_prime/pi_package_20260709/B_PRIME_PI_RATINGS.csv`
- `../scripts/build_selfhost_pi_gold_smoke.py`

## Exact Continuation

1. PI rates the 42-row decisive construct packet using Label A and Label B.
2. Re-run `build_selfhost_pi_gold_smoke.py`; it fails closed unless balanced
   high-confidence PI truth exists.
3. Run the ten-clip PI-gold smoke, then a disjoint held-out human-gold set.
4. Compute sensitivity, specificity, balanced accuracy, MCC, and abstention.
5. Only if the frozen validation gate passes, run the stratified-500 A-prime
   scale track and B-prime both-order track. Preserve all raw responses.

Until those steps are complete, allowed wording is limited to: "A self-hosted
audio-language model pipeline was deployed and infrastructure-tested; automatic
judge validation remains pending expert labels." It is forbidden to state that
the judge, A-prime, or B-prime has passed.

`JUDGE_VALIDATION_STATUS = PI_BLOCKED`
