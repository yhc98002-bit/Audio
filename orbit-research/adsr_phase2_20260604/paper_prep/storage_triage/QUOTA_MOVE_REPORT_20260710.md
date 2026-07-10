# Quota Recovery Move Report

`QUOTA_MOVE_STATUS = COMPLETE`

## Incident

During T9 follow-up export and the self-hosted-judge downloads, pytest,
ModelScope, and official audio export independently returned `Errno 122: Disk
quota exceeded`. The aggregate filesystem remained below capacity, so this was
a user/project quota boundary rather than physical disk exhaustion.

## Scan

Top-level workspace usage before the move was approximately 185 GB:

- `orbit-research/`: 162 GB, predominantly frozen or claim-supporting audio.
- `runs/`: 13 GB, frozen by project policy.
- `model_cache/`: 9.8 GB, deployed project models.
- `_pi_review_pkg/`: 176 MB, protected review material.

Within `paper_prep/`, the largest paths were frozen N2 audio (73 GB), Stage 3
audio (33 GB), SA3 evidence (18 GB), storage/release evidence (8.4 GB), and the
active v1.5 replication (4.0 GB). None was moved.

## Authorized Move

Two stopped, incomplete, resumable ModelScope snapshots were moved without
deleting claim-supporting evidence:

| Source | Size before | Destination | Status |
|---|---:|---|---|
| `AudioDiffusion_envs/model_cache/Qwen3-Omni-30B-A3B-Instruct` | 31 GB | `/tmp/ADSR_QUOTA_QUARANTINE_20260710/model_cache/Qwen3-Omni-30B-A3B-Instruct` | MOVED |
| `AudioDiffusion_envs/model_cache/Qwen3-Omni-30B-A3B-Captioner` | 13 GB | `/tmp/ADSR_QUOTA_QUARANTINE_20260710/model_cache/Qwen3-Omni-30B-A3B-Captioner` | MOVED |

The download logs remain under `paper_prep/judge_selfhost_20260709/logs/`.
Both `/tmp` copies retain partial files for resume. No Stage 3, N2, SA3,
Gate-B, validation-package, release, or v1.5 evidence was deleted or moved.

## Result

Approximately 44 GB was removed from quota-charged shared model cache. Project
writes and no-cache pytest completed successfully afterward. The v1.5 bulk
follow-up audio was written to `/HOME/paratera_xy/pxy1289/ADSR_T9_20260709`
with ledgers copied back into the publication package.
