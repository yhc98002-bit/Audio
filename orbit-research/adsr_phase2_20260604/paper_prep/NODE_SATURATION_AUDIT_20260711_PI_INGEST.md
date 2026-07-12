# Node Saturation Audit: PI Ingestion And W2

Audit window: 2026-07-12 12:36–13:16 Asia/Shanghai.

## an12

- 12:36: all eight GPUs were free.
- 12:46: an unrelated BlindGain `run_blind_solvability_v2.py` process appeared
  on physical GPU 6 and used approximately 61.8 GiB. No PI authorization for
  that non-ADSR job is discoverable from this repository. It is not counted as
  ADSR progress and was not terminated.
- 12:52–12:56: W2 PI-gold Demucs/PANNs calibration used physical GPUs 0–5 and
  7; the deferred eighth shard was recycled onto GPU 0 after the first seven
  completed.
- 12:57–13:13: the full corrected-instrument W2 pass used GPUs 0–5 and 7. It
  completed 22,723/22,723 retained files with zero failed or missing rows.
- 13:16 state: W2 is complete; GPU 6 remains occupied by the unrelated job and
  GPUs 0–5/7 are free. No ADSR worker remains unexpectedly running.

The only pre-dispatch idle interval was approximately 16 minutes, below the
30-minute threshold. Seven available GPUs were assigned to ADSR as soon as the
calibration implementation was ready.

## an29

- The ADSR `qwen3-omni-judge` service remained healthy in tmux session
  `adsr_qwen_server` on physical GPUs 0, 2, 3, and 4.
- The PI-gold run completed 30 balanced-smoke calls and 315 held-out calls with
  no client errors or abstentions.
- Physical GPUs 1, 5, 6, and 7 were occupied by an unrelated BlindGain
  Qwen2.5-VL-72B captioning job at the final audit. No PI authorization for that
  non-ADSR job is discoverable from this repository. It is not counted as ADSR
  progress and was not terminated.
- 13:16 state: the judge service is healthy and resident for any PI-approved
  continuation; the four other GPUs remain occupied by non-ADSR work.

## Evidence

- `paper_prep/pi_ratings_20260711/processed/PI_GOLD_JUDGE_VALIDATION_REPORT.md`
- `paper_prep/w2_contingency_20260711/activated_20260711/calibration/W2_INSTRUMENT_CALIBRATION_REPORT.md`
- `paper_prep/w2_contingency_20260711/activated_20260711/full_corrected/W2_CORRECTED_MERGE_AUDIT.json`
- `paper_prep/heartbeat_an12.log`
- `paper_prep/heartbeat_an29.log`
- `paper_prep/execution_20260709/CODE_REVIEW_RECOVERY_LEDGER.jsonl`
