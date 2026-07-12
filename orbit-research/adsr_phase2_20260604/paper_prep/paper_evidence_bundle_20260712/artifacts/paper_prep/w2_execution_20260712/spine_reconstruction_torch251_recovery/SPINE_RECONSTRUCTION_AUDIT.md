# W2 Spine Reconstruction Audit

`SPINE_REGEN_STATUS = COMPLETE_AUDIT_PASS`

`SPINE_REGEN_AUDIT = PASS`

- Manifest rows: 4096
- Missing candidates reconstructed: 4095
- Surviving-original audit replays: 1
- Successful generation rows: 4096
- Successful old/candidate instrument scoring rows after task-ID deduplication: 4096
- Raw successful scoring rows: 4096; deterministic handoff duplicates: 0; conflicting duplicates: 0
- Missing generation rows: 0
- Invalid or checksum-mismatched media: 0
- Missing scoring rows: 0
- Invalid duration/sample-rate rows: 0
- Near-silent generation/scoring rows: 0/0
- Sample-rate counts: {48000: 4096}
- Duration range: 29.907312-74.675375 s
- Historical-versus-recomputed current-detector label flips: 15/4096
- Surviving originals exact by decoded hash: 1/1
- Independent regeneration controls exact by decoded hash: 50/50

The Demucs-and-PANNs instrument is a candidate sensitivity instrument only. This audit does not promote it and does not change PLAN.md.
