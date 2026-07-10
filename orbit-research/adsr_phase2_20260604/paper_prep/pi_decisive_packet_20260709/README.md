# PI Decisive Construct Packet

This is a 42-clip branch-selection packet. It is **not A-prime gate
validation** and cannot be used to claim that A-prime passed.

The blinded order contains four failed-smoke negatives, 20 Qwen-yes/Demucs-no
clips spread across the detector-ratio histogram, six original rare-basin
clips, six original threshold-near clips, and six obvious-agreement controls.

Use the D5 Label A and Label B definitions in
`paper_prep/HUMAN_STUDY_CRITERIA_AMENDMENT_20260709.md`. Keep `Unsure` rather
than forcing a label. After all rows are rated with non-synthetic provenance,
run:

```bash
python paper_prep/pi_decisive_packet_20260709/score_decisive_packet.py
```

The scorer returns one branch: `judge_over_calling`, `demucs_missing`, or
`construct_mismatch`. A `demucs_missing` branch is an escalation trigger.
