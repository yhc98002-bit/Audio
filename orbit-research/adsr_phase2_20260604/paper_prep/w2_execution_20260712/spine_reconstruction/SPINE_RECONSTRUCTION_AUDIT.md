# W2 Spine Reconstruction Audit

`SPINE_REGEN_STATUS = FAILED_ESCALATED`

`SPINE_REGEN_AUDIT = FAIL`

- Manifest rows: 4096
- Missing candidates reconstructed: 4095
- Surviving-original audit replays: 1
- Successful generation rows: 4096
- Successful old/candidate instrument scoring rows after task-ID deduplication: 4096
- Raw successful scoring rows: 4100; deterministic handoff duplicates: 4; conflicting duplicates: 0
- Missing generation rows: 0
- Invalid or checksum-mismatched media: 0
- Missing scoring rows: 0
- Invalid duration/sample-rate rows: 0
- Near-silent generation/scoring rows: 0/0
- Sample-rate counts: {48000: 4096}
- Duration range: 29.907312-74.675375 s
- Historical-versus-recomputed current-detector label flips: 85/4096
- Surviving originals exact by decoded hash: 0/1
- Independent regeneration controls exact by decoded hash: 0/50

The Demucs-and-PANNs instrument is a candidate sensitivity instrument only. This audit does not promote it and does not change PLAN.md.
