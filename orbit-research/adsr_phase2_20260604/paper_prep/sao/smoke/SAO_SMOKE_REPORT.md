# SAO Smoke Report

Generated: 2026-07-07

SAO_SMOKE_STATUS = FAIL

## Attempt

- Node: `an29`
- Environment: `audio-prm`
- Command: `CUDA_VISIBLE_DEVICES=0 PYTHONPATH=src python scripts/d1_model_load.py --model sao_1_0 --seed 20260707 --duration 10 --out paper_prep/sao/smoke/audio`
- Return code: `1`
- Log: `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion/paper_prep/sao/smoke/sao_smoke_an29_20260708T052823.log`
- Audio files: none
- Ledger: `paper_prep/sao/smoke/SAO_SMOKE_LEDGER.jsonl`

## Interpretation

PASS requires model load, one generated non-empty decodable audio file, and the
existing `scripts/d1_model_load.py` non-silence check to print `D1 PASS`.
If this report says FAIL, the log path above is the exact traceback/evidence for
the next recovery path.
