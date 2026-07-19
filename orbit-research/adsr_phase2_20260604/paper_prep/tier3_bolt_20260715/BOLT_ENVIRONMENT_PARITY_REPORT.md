# BOLT Cross-Node Environment Parity

ENVIRONMENT_PARITY_STATUS = PASS

The source checkout is a content-only copy without `.git`; its frozen W2 upstream commit provenance is `1bee4c9f5b43e30995f8d4d33b3919197ce1bd68`, and the current source is bound by the manifest hash below. Both nodes read the same shared artifacts but independently hashed and imported them.

| Component | an12 | an29 | Match |
| --- | --- | --- | --- |
| Python | `3.10.20` | `3.10.20` | YES |
| torch | `2.5.1+cu121` | `2.5.1+cu121` | YES |
| CUDA build | `12.1` | `12.1` | YES |
| torchaudio | `2.5.1+cu121` | `2.5.1+cu121` | YES |
| ACE-Step declared commit | `1bee4c9f5b43e30995f8d4d33b3919197ce1bd68` | `1bee4c9f5b43e30995f8d4d33b3919197ce1bd68` | YES |
| ACE-Step source manifest | `203e623b252592794e667015ca51cab23d9bfdf74ad56c98efca5d4c2cf179ab` | `203e623b252592794e667015ca51cab23d9bfdf74ad56c98efca5d4c2cf179ab` | YES |
| Checkpoint manifest | `2058d6c10bd348da51669ff3886c6b4080405fe4c23bb3de183c293cb5f0bef9` | `2058d6c10bd348da51669ff3886c6b4080405fe4c23bb3de183c293cb5f0bef9` | YES |
| Scheduler | `d3d724dec32d4f2d3df62d4dc9de30c1b74c0d2602e19063ec00031e2f7ebe8d` | `d3d724dec32d4f2d3df62d4dc9de30c1b74c0d2602e19063ec00031e2f7ebe8d` | YES |
| Promoted instrument record | `2ec9f12fd9008dae0e32675fcdaaf9e7a22fe0ed7006dd310b665b1e82be2ff2` | `2ec9f12fd9008dae0e32675fcdaaf9e7a22fe0ed7006dd310b665b1e82be2ff2` | YES |
| Instrument implementation | `3aa68674b9ce919d407f25070a93ca73f14ed39af36f41090a4db000b5df1524` | `3aa68674b9ce919d407f25070a93ca73f14ed39af36f41090a4db000b5df1524` | YES |
| Quality policy | `34db933b67d06f3acc3780e70b2f492a20d685ef710777fc81eaffba1d2806e9` | `34db933b67d06f3acc3780e70b2f492a20d685ef710777fc81eaffba1d2806e9` | YES |
| Quality artifact manifest | `18834c4755d3afabcccb4709887fe238b0834bf084be203a6103ae4e75483037` | `18834c4755d3afabcccb4709887fe238b0834bf084be203a6103ae4e75483037` | YES |
| BOLT code manifest | `6125c3f6b11dedefcb2728ed9c61f5f7d0fe1d63f5e881ecdecfddfd4e1ee48d` | `6125c3f6b11dedefcb2728ed9c61f5f7d0fe1d63f5e881ecdecfddfd4e1ee48d` | YES |
| BOLT git SHA | `9ffc191266dcf24dd8f76d39e4f0c734656dee75` | `9ffc191266dcf24dd8f76d39e4f0c734656dee75` | YES |
| Environment | `d1c44cb0fec1fa4347ba3b0908cab561ebbbbba648026c57c0b79aeffb0df542` | `d1c44cb0fec1fa4347ba3b0908cab561ebbbbba648026c57c0b79aeffb0df542` | YES |

## Differences

None.
