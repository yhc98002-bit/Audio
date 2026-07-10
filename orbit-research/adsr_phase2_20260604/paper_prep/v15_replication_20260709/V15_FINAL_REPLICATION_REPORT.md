# ACE-Step v1.5 Bounded Replication

`V15_REPLICATION_STATUS = COMPLETE`

## Coverage And Audit

- Smoke: 2/2 successful, decoded, non-silent, and scored.
- Difficult-set prevalence: 1,024/1,024 successful and scored.
- Focused retry: 512/512 successful and scored.
- Matched intervention: 256/256 successful and scored.
- Near-silent scored rows: 0.
- Audio SHA-256 mismatches: 0.
- Failed generation attempts are retained in raw ledgers and excluded only
  after requiring exactly one PASS for every manifest key.

## Results

- Difficult-set per-draw type-correct rate: 0.448242.
- Vocal-request prompt mean: 0.169753.
- Instrumental-request prompt mean: 0.928191.
- Focused retry prompt mean: 0.500000; zero-clean
  prompts at 32 fresh seeds: 8/16.
- Matched reconditioning prompt-mean delta:
  +0.054688, prompt-bootstrap 95% CI
  [+0.000000, +0.132812].
- Vocal-request delta: +0.078125.
- Instrumental-request delta: +0.031250.

## Claim Boundary

This completes the mandatory bounded v1.5 replication. The 128 prompts are a
selected difficult/stratified set, not a generic population sample. The result
shows severe vocal-request failures and a small, uncertain focused
reconditioning lift. It does not replace the frozen ACE-Step v1 evidence and
does not support a broad v1.5 intervention-success claim.

Audio for retry and intervention is stored outside Git under
`/HOME/paratera_xy/pxy1289/ADSR_T9_20260709`; `V15_AUDIO_MANIFEST.csv` records every path and hash.
