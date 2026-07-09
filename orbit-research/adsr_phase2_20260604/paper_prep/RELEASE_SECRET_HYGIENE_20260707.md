# Release Secret Hygiene

Generated: 2026-07-07

SECRET_STATUS = CLEAN

## Actions Taken

- Redacted the literal DashScope credential from `CLAUDE.md`.
- Left runtime credential loading in `paper_prep/scripts/judge_client.py` as environment-first:
  `$DASHSCOPE_API_KEY`, then `paper_prep/scripts/.dashscope_key`.
- Added ignore rules to `.gitignore` for `.env.*`, `.dashscope_key`, and `**/.dashscope_key`.
- Verified these releaseable files contain zero literal `sk-...` credential-pattern hits:
  - `CLAUDE.md`
  - `paper_prep/scripts/judge_client.py`
  - `paper_prep/PLAN.md`
  - `ADSR_Publication_ToDo_Guide.md`
  - `WHAT_HAVE_I_DONE_20260707.md`
  - `paper_prep/FINAL_PREDRAFT_AUDIT_20260707.md`

## Credential-Bearing / Candidate Files

| File | Status | Release action |
|---|---|---|
| `paper_prep/scripts/.dashscope_key` | Actual runtime secret file, mode `0600`. | Exclude from all release packages. Use only locally or replace with `$DASHSCOPE_API_KEY`. |
| `CLAUDE.md` | Previously contained a literal key; now redacted. | Safe after redaction. |
| `ADSR_Publication_ToDo_Guide.md` | Contains DashScope/API-key instructions only, not a literal credential. | Safe. |
| `.aris/meta/events.jsonl` | Scanner produced false-positive `sk-` matches from strings such as `task-id`; ORBIT logs are not release artifacts. | Do not include `.aris/` in public release package. |

## Safe-For-Release Checklist

- Do not package `paper_prep/scripts/.dashscope_key`.
- Prefer `$DASHSCOPE_API_KEY` for live judge execution.
- Exclude `.aris/`, local execution logs containing user prompts, and any local secret files from public artifacts.
- Before final public upload, rerun a filename-only and pattern-count secret scan over the exact release directory.

No secret value is printed or copied into this report.
