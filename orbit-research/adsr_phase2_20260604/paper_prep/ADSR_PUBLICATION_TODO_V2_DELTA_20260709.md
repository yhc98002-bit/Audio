# ADSR Publication Guide V2 Delta

This file corrects stale operational statements in
`ADSR_Publication_ToDo_Guide.md` without rewriting that historical guide.

| Topic | V2 correction |
|---|---|
| Backbone identity | Frozen ADSR evidence is ACE-Step v1. ACE-Step v1.5 is a separate bounded replication, not the identity of prior results. |
| Second backbone | The executed pilot is Stable Audio 3 Medium. `src/mprm/inference/sao.py` is the legacy Stable Audio Open 1.0 adapter; do not conflate SA3 and SAO. |
| Human evidence | Do not write "human studies confirm" until real A-prime/B-prime ratings pass their signed gates. Prepared packages are not results. |
| Judge evidence | Failed Qwen smoke calls are diagnostic only. A model judge is a scaling instrument only after held-out human-gold validation. |
| Secret location | `DASHSCOPE_API_KEY` must be supplied through the environment or a gitignored secret file. A credential in `CLAUDE.md` is a leak to remove, not a completed task. |
| Node state | Stage 3 and N2 are frozen and complete. `an12` is the v1.5 lane; `an29` is the ADSR detector/calibration and SA3 follow-up lane. |
| Storage | The current recovery brief forbids deletion. Preserve media, ledgers, failed attempts, and model artifacts. |
| Current status | Read `paper_prep/CODE_REVIEW_RECOVERY_REPORT_20260709.md`, not the guide's old task-state prose. |

Paper wording remains bounded: use "rare / impractical to retry," identify
difficult-set rates explicitly, qualify automatic quality instruments, and
never write "proved no loss."
