# Legacy CXY Scoring Report

> **PI: read after your fresh sittings.** This file contains per-clip and
> per-bucket legacy outcomes and can spoil the blinded July 9 packages.

`LEGACY_CLASSIFICATION = LEGACY_NON_PRIMARY`

All ratings were collected before the signed amendment, against historical
manifests and the old B-prime question set. They are descriptive legacy
evidence only. They were not passed to either primary gate scorer, and no
A-prime or B-prime status changes are authorized by this report.

## Input Custody

| Input | UTC modification time | Bytes | SHA-256 |
|---|---|---:|---|
| `orbit-research/adsr_phase2_20260604/paper_prep/legacy_human_results_20260710/incoming/result/1_quality_AB_result/ab_responses_CXY.csv` | 2026-07-10T13:38:29+00:00 | 2766 | `4aedac8b76547e196620657e015f9494507f7cd62d82f4fcc6c241338eeef379` |
| `orbit-research/adsr_phase2_20260604/paper_prep/legacy_human_results_20260710/incoming/result/1_quality_AB_result/ab_backup_CXY.json` | 2026-07-10T13:38:30+00:00 | 8502 | `cacbe81fb0d1c6c5fb472317f6c1b946d1860d2553842193c593b67808bc1d30` |
| `orbit-research/adsr_phase2_20260604/paper_prep/legacy_human_results_20260710/incoming/result/2_label_adjudication_result/adjudication_responses_CXY.csv` | 2026-07-10T01:40:41+00:00 | 2115 | `56b42f62bf2a17f89855a67bf1f1907ddfb2818e05f6ec61679bab3f97bcb3b0` |
| `orbit-research/adsr_phase2_20260604/paper_prep/legacy_human_results_20260710/incoming/result/2_label_adjudication_result/adj_backup_CXY.json` | 2026-07-10T01:40:43+00:00 | 3645 | `e3a4e293817833a891437efe1422ed6cb5f92d5f9dc66e4830695aa2fd208f93` |
| `orbit-research/adsr_phase2_20260604/paper_prep/legacy_human_results_20260710/incoming/result/2b_rare_basin_audit_result/rare_basin_audit_responses_CXY.csv` | 2026-07-10T06:52:36+00:00 | 1155 | `80e6357d753385e642b84f22beae8d615df3aa06fb6c3f98c2b0fc2a57488b23` |
| `orbit-research/adsr_phase2_20260604/paper_prep/legacy_human_results_20260710/incoming/result/2b_rare_basin_audit_result/rare_basin_audit_backup_CXY.json` | 2026-07-10T06:52:37+00:00 | 1957 | `53d4f619a3fbb8d57fed41fc882f1b073b036d4873c2207d60dbe7e9d8ec62d9` |
| `orbit-research/adsr_phase2_20260604/paper_prep/legacy_human_results_20260710/incoming/result/2c_detector_agreement_spotcheck_result/detector_agreement_spotcheck_responses_CXY.csv` | 2026-07-10T07:00:20+00:00 | 597 | `99d5f3d0cd0bf1ed2771afc45538b1d9ee87e2442738358b22d781920c2278b9` |
| `orbit-research/adsr_phase2_20260604/paper_prep/legacy_human_results_20260710/incoming/result/2c_detector_agreement_spotcheck_result/detector_agreement_spotcheck_backup_CXY.json` | 2026-07-10T07:00:21+00:00 | 962 | `09410548f52cae2f138a19caadfef80d5f9630434a97f09a9fb36f9d5df51ac7` |

Each CSV has a matching browser-backup JSON with an identical ID set and
identical saved answers. The A/B arm mapping was joined only through the
permission-restricted on-cluster PI-only key; the key content is not reproduced here.

## Manifest And Mapping Audit

| Incoming result | Historical GUI row manifest | Media/key provenance | Join result |
|---|---|---|---|
| `1_quality_AB_result/ab_responses_CXY.csv` | `phase3/human_ab/response_sheet.csv`; `phase3/human_ab/human_adsr_pairs.jsonl` | `phase3/human_ab/audio_manifest.csv`; on-cluster mode-600 PI-only `UNBLINDING_KEY.jsonl` | exact one-to-one pair/key join |
| `2_label_adjudication_result/adjudication_responses_CXY.csv` | `validation_A_prime/tar_extracted/adsr_human_eval_pkg/2_label_adjudication/response_sheet.csv`; `phase0/rater_packet/cases_blinded.jsonl` | extracted original packet media plus A-prime admin hashes | exact one-to-one case/media join |
| `2b_rare_basin_audit_result/rare_basin_audit_responses_CXY.csv` | `validation_A_prime/A_PRIME_MANIFEST.csv` | `storage_triage/HUMAN_PACKAGE_SOURCE_REFERENCES.csv`; `storage_triage/RARE_CLEAN_PROTECTED/manifest.csv`; A-prime admin hashes | exact one-to-one case/media join |
| `2c_detector_agreement_spotcheck_result/detector_agreement_spotcheck_responses_CXY.csv` | extracted `2c_detector_agreement_spotcheck/response_sheet.csv` | extracted `manifest.csv` and original packet media plus A-prime admin hashes | exact one-to-one case/media join |

- Legacy rows classified: 282 / 282 as `LEGACY_NON_PRIMARY`.
- Missing or ambiguous manifest/key mappings: 0.
- Legacy rows overlapping a July 9 primary or decisive packet: 180.
- Cross-manifest canonical-label conflicts: 0.
- The rare-basin regenerated cohort is marked `flip-risk`; it is sensitivity-only and excluded from judge gold.

## Human Versus Demucs By Bucket

Match means the CXY voice-presence answer equals the canonical Demucs label
attached to the exact rated media. Intervals are two-sided 95% Wilson intervals.

| Bucket | Media scope | Rows | Expected yes | Expected no | Missing expected | Decided | Matches | Errors | Match rate | Wilson CI |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| adjudication | all | 112 | 11 | 101 | 0 | 112 | 6 | 106 | 0.053571 | [0.024781, 0.111970] |
| rare_basin | all | 60 | 28 | 32 | 0 | 60 | 27 | 33 | 0.450000 | [0.330937, 0.575081] |
| rare_basin | original-only | 34 | 4 | 30 | 0 | 34 | 3 | 31 | 0.088235 | [0.030466, 0.229605] |
| spotcheck | all | 30 | 26 | 4 | 0 | 30 | 27 | 3 | 0.900000 | [0.743789, 0.965400] |

## Legacy A/B Arm-Mapped Preferences

The method arm is historical `arm6`; baselines are `arm1` or `arm4` as
specified by the PI-only key. These are not amended B-prime quality ratings.

| Contrast | Question | Rows | Method | Baseline | Ties | Tie-excluded method rate | Wilson CI | Ties-as-half | Ties-against-method |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|
| all | overall preference | 80 | 20 | 35 | 25 | 0.363636 | [0.249305, 0.495772] | 0.406250 | 0.250000 |
| all | prompt fit | 80 | 20 | 19 | 41 | 0.512821 | [0.361994, 0.661348] | 0.506250 | 0.250000 |
| all | fewer vocal artifacts | 80 | 20 | 29 | 31 | 0.408163 | [0.282152, 0.547527] | 0.443750 | 0.250000 |
| arm6_vs_arm1 | overall preference | 40 | 9 | 19 | 12 | 0.321429 | [0.179332, 0.506612] | 0.375000 | 0.225000 |
| arm6_vs_arm1 | prompt fit | 40 | 9 | 9 | 22 | 0.500000 | [0.290310, 0.709690] | 0.500000 | 0.225000 |
| arm6_vs_arm1 | fewer vocal artifacts | 40 | 9 | 16 | 15 | 0.360000 | [0.202479, 0.554815] | 0.412500 | 0.225000 |
| arm6_vs_arm4 | overall preference | 40 | 11 | 16 | 13 | 0.407407 | [0.245148, 0.592733] | 0.437500 | 0.275000 |
| arm6_vs_arm4 | prompt fit | 40 | 11 | 10 | 19 | 0.523810 | [0.323695, 0.716560] | 0.512500 | 0.275000 |
| arm6_vs_arm4 | fewer vocal artifacts | 40 | 11 | 13 | 16 | 0.458333 | [0.278913, 0.649251] | 0.475000 | 0.275000 |

## Per-Clip Label Results

| Packet | Clip ID | Human Label A | Demucs expected | Match | Media class | Flip-risk | New primary ID | Decisive ID | Canonical conflict |
|---|---|---|---|---|---|---|---|---|---|
| adjudication | `0462eb3b91` | yes | no | no | original | no | aprime_0186_974bb909f260 | - | no |
| adjudication | `05ce645a00` | yes | no | no | original | no | aprime_0375_6583ccd2159b | - | no |
| adjudication | `09f81ecff2` | yes | no | no | original | no | aprime_0410_8446dfa77b62 | - | no |
| adjudication | `0c944609f0` | yes | no | no | original | no | aprime_0663_d40cba210a01 | - | no |
| adjudication | `0cc3ea5a73` | yes | no | no | original | no | aprime_0421_dac3243f8e5f | - | no |
| adjudication | `0d3315c21f` | yes | no | no | original | no | aprime_0123_65afee322263 | - | no |
| adjudication | `0ec02e217b` | yes | no | no | original | no | aprime_0236_478362009a33 | - | no |
| adjudication | `10b5a4a982` | yes | no | no | original | no | aprime_0437_f520ccdf1cae | - | no |
| adjudication | `14b128eef4` | yes | no | no | original | no | aprime_0509_0b45d7de17e5 | - | no |
| adjudication | `1592c7c9a9` | yes | no | no | original | no | aprime_0535_58533f52c8d7 | - | no |
| adjudication | `17c9c14d1f` | yes | no | no | original | no | aprime_0502_95ced68c584f | - | no |
| adjudication | `18a56a64a0` | yes | no | no | original | no | aprime_0617_862c4e1adf94 | - | no |
| adjudication | `1bf508d52f` | yes | no | no | original | no | aprime_0394_166a16fd29b6 | - | no |
| adjudication | `1d950f946a` | yes | no | no | original | no | aprime_0210_a1d0917b9271 | - | no |
| adjudication | `1e0e0bc592` | yes | no | no | original | no | aprime_0357_e095ef7dbc7b | - | no |
| adjudication | `20ba693c1f` | yes | no | no | original | no | aprime_0049_e0aac6d99ffa | - | no |
| adjudication | `232468ea31` | yes | no | no | original | no | aprime_0069_58b473a79c94 | - | no |
| adjudication | `23532447a5` | yes | no | no | original | no | aprime_0648_b632fdc8b8b2 | - | no |
| adjudication | `2df83e6229` | yes | no | no | original | no | aprime_0588_1e3858b0eca8 | - | no |
| adjudication | `30999be08d` | yes | no | no | original | no | aprime_0099_659447258733 | - | no |
| adjudication | `30bc8325b0` | yes | no | no | original | no | aprime_0064_57bc5f2e1e77 | - | no |
| adjudication | `34ee91d6a0` | yes | no | no | original | no | aprime_0001_2856569ce627 | - | no |
| adjudication | `3744abd84b` | yes | yes | yes | original | no | aprime_0451_f2a3046bab38 | - | no |
| adjudication | `38b86373e6` | no | yes | no | original | no | aprime_0066_863db45703ed | - | no |
| adjudication | `3ac836c596` | yes | no | no | original | no | aprime_0593_4efe81c7d888 | - | no |
| adjudication | `3c349740ba` | yes | no | no | original | no | aprime_0201_c50b8689821f | - | no |
| adjudication | `3fb5cf1de0` | yes | no | no | original | no | aprime_0403_40521083e3a1 | - | no |
| adjudication | `462b0677d0` | yes | yes | yes | original | no | aprime_0681_9793870cebeb | - | no |
| adjudication | `47bdd38200` | yes | no | no | original | no | aprime_0255_7b8a6ae8b538 | - | no |
| adjudication | `48d2e04417` | yes | no | no | original | no | aprime_0473_088b54d5fec7 | - | no |
| adjudication | `4e851ff3bd` | yes | no | no | original | no | aprime_0092_0f4aaa6c5077 | decisive_17_4217d6b8e4a2 | no |
| adjudication | `4fd6775d22` | yes | no | no | original | no | aprime_0490_55ab8e50a996 | - | no |
| adjudication | `50d73b401e` | yes | no | no | original | no | aprime_0321_f0230ca0f72e | - | no |
| adjudication | `51f074892f` | yes | no | no | original | no | aprime_0033_1fa2a7ff3d3b | - | no |
| adjudication | `520cd89371` | yes | no | no | original | no | aprime_0402_d5d9911e4dba | - | no |
| adjudication | `54d9222ca7` | yes | no | no | original | no | aprime_0101_a0d29cf558ff | - | no |
| adjudication | `54d9927de3` | yes | yes | yes | original | no | aprime_0627_a8555cc90269 | - | no |
| adjudication | `58e7d2e6a9` | yes | no | no | original | no | aprime_0162_8bfe80d445ae | - | no |
| adjudication | `5ae3e43aef` | yes | no | no | original | no | aprime_0313_1f330e151b70 | decisive_09_91f361499026 | no |
| adjudication | `5cd6a5a933` | yes | no | no | original | no | aprime_0129_d232b51597ad | - | no |
| adjudication | `6053073dd2` | yes | no | no | original | no | aprime_0557_4917ed5ea1b2 | - | no |
| adjudication | `607c7c8b46` | yes | no | no | original | no | aprime_0686_e1ab9d96e86d | - | no |
| adjudication | `61e727e07d` | yes | no | no | original | no | aprime_0462_c4e504aa2898 | - | no |
| adjudication | `620ef52d56` | yes | no | no | original | no | aprime_0253_0c49c4ef352f | - | no |
| adjudication | `66e3cf05da` | yes | no | no | original | no | aprime_0523_32ae483f177e | - | no |
| adjudication | `68ba4f10d4` | yes | no | no | original | no | aprime_0292_7f0236a459a4 | - | no |
| adjudication | `6bae4a7691` | yes | no | no | original | no | aprime_0211_50059199e23a | - | no |
| adjudication | `6f8d7d94a2` | yes | yes | yes | original | no | aprime_0304_6033f5316189 | - | no |
| adjudication | `717304485f` | yes | no | no | original | no | aprime_0183_d920698ee434 | - | no |
| adjudication | `7479bc365c` | yes | no | no | original | no | aprime_0169_53af4593e3de | - | no |
| adjudication | `763836eaa0` | yes | no | no | original | no | aprime_0083_83e193e56a5d | - | no |
| adjudication | `7b904ecdf4` | no | yes | no | original | no | aprime_0434_45584248d7cc | - | no |
| adjudication | `7e83886fe3` | yes | no | no | original | no | aprime_0461_6d766c6417a7 | - | no |
| adjudication | `80b68ef0c2` | yes | no | no | original | no | aprime_0381_83810fadeaa6 | - | no |
| adjudication | `8187dd9cd3` | yes | no | no | original | no | aprime_0399_c408c8caeb94 | decisive_14_e7a8cf805731 | no |
| adjudication | `86d96700b5` | yes | no | no | original | no | aprime_0042_81377c8748f8 | decisive_05_74e8e1d035d2 | no |
| adjudication | `8cac881e2f` | yes | no | no | original | no | aprime_0377_f5a5087746aa | - | no |
| adjudication | `8d66491daf` | yes | no | no | original | no | aprime_0612_8155ef783a1e | - | no |
| adjudication | `90043c568d` | yes | no | no | original | no | aprime_0152_293b2034cccc | - | no |
| adjudication | `90871c664c` | yes | no | no | original | no | aprime_0610_1bc7779898df | - | no |
| adjudication | `92c9ca96e1` | yes | no | no | original | no | aprime_0228_821d00820017 | - | no |
| adjudication | `939c52e0fd` | yes | no | no | original | no | aprime_0383_0d49a21c2ebc | - | no |
| adjudication | `95a433a630` | no | yes | no | original | no | aprime_0318_aff50034eabd | - | no |
| adjudication | `969a058baa` | yes | no | no | original | no | aprime_0320_93f891edfbd2 | - | no |
| adjudication | `996e4da940` | yes | no | no | original | no | aprime_0504_a572116e2b38 | - | no |
| adjudication | `9b235a332d` | yes | no | no | original | no | aprime_0251_85dbff5dabd1 | - | no |
| adjudication | `9b9b7358d2` | yes | no | no | original | no | aprime_0334_ffa479660183 | - | no |
| adjudication | `a461de6acd` | yes | no | no | original | no | aprime_0468_95eb0717de90 | - | no |
| adjudication | `a46eb6ec7b` | yes | no | no | original | no | aprime_0194_2fece6846043 | - | no |
| adjudication | `ac7444d64c` | yes | no | no | original | no | aprime_0043_ebc25c0f11b3 | - | no |
| adjudication | `aee5f30ccb` | yes | no | no | original | no | aprime_0016_190db19d0ad7 | - | no |
| adjudication | `b543bf3e25` | yes | no | no | original | no | aprime_0104_48bbf5a928f5 | - | no |
| adjudication | `bb56e24b43` | yes | no | no | original | no | aprime_0071_a6902228de1a | - | no |
| adjudication | `bba9b607a2` | yes | no | no | original | no | aprime_0651_ca2b2105628f | - | no |
| adjudication | `bc2b100662` | yes | no | no | original | no | aprime_0011_b9def10055a4 | - | no |
| adjudication | `bc807e6c28` | yes | no | no | original | no | aprime_0570_e6aa58736a3d | - | no |
| adjudication | `bca94602c7` | yes | no | no | original | no | aprime_0020_165d2ca6da9c | - | no |
| adjudication | `bd008df9d0` | yes | no | no | original | no | aprime_0366_9e753224479c | - | no |
| adjudication | `bd8858cb7e` | yes | no | no | original | no | aprime_0220_26f2409390d0 | - | no |
| adjudication | `c0022b7598` | yes | no | no | original | no | aprime_0647_92e26629e8be | - | no |
| adjudication | `c7e03344ef` | yes | no | no | original | no | aprime_0626_2ef9235a4c99 | - | no |
| adjudication | `c87365fc8d` | yes | no | no | original | no | aprime_0090_cda7942f8b50 | - | no |
| adjudication | `c9372b74dd` | yes | no | no | original | no | aprime_0021_ba5e95fbb64d | - | no |
| adjudication | `c95376a3eb` | no | yes | no | original | no | aprime_0280_d7a50f490b4f | - | no |
| adjudication | `c9c7da8014` | yes | no | no | original | no | aprime_0293_02e92a28b5e8 | - | no |
| adjudication | `cb1a090c71` | no | yes | no | original | no | aprime_0586_b4d59b9dd370 | decisive_42_1108911c47cd | no |
| adjudication | `cb56b9b272` | yes | no | no | original | no | aprime_0385_c0d11033eab8 | - | no |
| adjudication | `cd6b274756` | yes | no | no | original | no | aprime_0013_787b3b17faad | - | no |
| adjudication | `cf985bf858` | yes | no | no | original | no | aprime_0223_801655f5e5e8 | - | no |
| adjudication | `cfb936d14b` | yes | no | no | original | no | aprime_0156_48ce3ea0918f | - | no |
| adjudication | `cfd7e08376` | yes | no | no | original | no | aprime_0018_39e73630f43c | - | no |
| adjudication | `d51b3f1e9a` | yes | no | no | original | no | aprime_0117_d5f69168ea1c | - | no |
| adjudication | `d5c877d981` | yes | no | no | original | no | aprime_0110_2e424726f7ec | - | no |
| adjudication | `d5de275976` | yes | no | no | original | no | aprime_0250_e8b755a84a0d | - | no |
| adjudication | `d7a9a10b56` | yes | no | no | original | no | aprime_0606_418aa78713d9 | - | no |
| adjudication | `d8ebcccbe8` | yes | yes | yes | original | no | aprime_0153_10b8552cf5af | - | no |
| adjudication | `e0c37d70f7` | yes | no | no | original | no | aprime_0004_135d175c5132 | - | no |
| adjudication | `e29f8613a5` | yes | yes | yes | original | no | aprime_0548_94fe5343553d | - | no |
| adjudication | `e8bde3e094` | yes | no | no | original | no | aprime_0470_d418f7dcf6a8 | decisive_15_cc2eb6bbefa7 | no |
| adjudication | `e97663c199` | yes | no | no | original | no | aprime_0552_bcf31e098af0 | - | no |
| adjudication | `ecd650f632` | yes | no | no | original | no | aprime_0528_0dbe28d0086c | - | no |
| adjudication | `ee1c686eef` | yes | no | no | original | no | aprime_0178_426aef858d6a | - | no |
| adjudication | `efc9f29abe` | yes | no | no | original | no | aprime_0480_dde3d7023a12 | - | no |
| adjudication | `f12aa92316` | yes | no | no | original | no | aprime_0148_6322db97e0dc | - | no |
| adjudication | `f4ba2c022f` | yes | no | no | original | no | aprime_0503_7bde6b74b0bd | - | no |
| adjudication | `f59253d6e0` | yes | no | no | original | no | aprime_0378_df8ae0b4e89e | - | no |
| adjudication | `f6055b026c` | yes | no | no | original | no | aprime_0181_4a745e5475ed | - | no |
| adjudication | `f6a675aa1a` | yes | no | no | original | no | aprime_0475_70f31eededf2 | - | no |
| adjudication | `f94b389a30` | yes | no | no | original | no | aprime_0628_28952d1a4b83 | - | no |
| adjudication | `fb046871a7` | yes | no | no | original | no | aprime_0677_433b5bab9af2 | - | no |
| adjudication | `fc14994663` | yes | no | no | original | no | aprime_0252_b907516a65fc | - | no |
| adjudication | `ff99cc7c12` | yes | no | no | original | no | aprime_0075_1b2aad741e6c | - | no |
| rare_basin | `07b882d9bc` | yes | yes | yes | regenerated | yes | - | - | no |
| rare_basin | `0a0c7b4e32` | yes | no | no | original | no | aprime_0652_9cbc424a39c7 | - | no |
| rare_basin | `14df153618` | yes | no | no | original | no | aprime_0572_de34dd4a9828 | - | no |
| rare_basin | `15d597fdf8` | yes | no | no | original | no | aprime_0582_8d2153d7e3aa | - | no |
| rare_basin | `1615dd2d17` | yes | yes | yes | regenerated | yes | - | - | no |
| rare_basin | `16251803a3` | yes | no | no | original | no | aprime_0051_63864ca8c042 | - | no |
| rare_basin | `1704261cb0` | yes | yes | yes | regenerated | yes | - | decisive_11_a8223b360df8 | no |
| rare_basin | `18fd030a7c` | yes | no | no | original | no | aprime_0621_58e54051eb54 | - | no |
| rare_basin | `19eb9a5b78` | yes | yes | yes | regenerated | yes | - | - | no |
| rare_basin | `1b26f35933` | yes | no | no | original | no | aprime_0644_d370ede41172 | - | no |
| rare_basin | `1bfba5cfd7` | yes | no | no | original | no | aprime_0415_fca707c18fa5 | - | no |
| rare_basin | `1cdbebb411` | yes | no | no | original | no | aprime_0599_fd0ddd8ffc16 | - | no |
| rare_basin | `29f9799414` | yes | yes | yes | regenerated | yes | - | - | no |
| rare_basin | `319e8e2df6` | yes | yes | yes | regenerated | yes | - | - | no |
| rare_basin | `33c9eed219` | yes | no | no | original | no | aprime_0458_e87ad357f1dc | - | no |
| rare_basin | `365acd5bd6` | yes | yes | yes | regenerated | yes | - | - | no |
| rare_basin | `3be39ff2ae` | yes | no | no | original | no | aprime_0237_5fce794f620c | - | no |
| rare_basin | `428182a23c` | yes | yes | yes | original | no | aprime_0441_ba8caca5699d | - | no |
| rare_basin | `4d32bb0ea6` | yes | yes | yes | regenerated | yes | - | decisive_21_61e688012e92 | no |
| rare_basin | `4d5901eaee` | yes | yes | yes | regenerated | yes | - | - | no |
| rare_basin | `50339d0b18` | yes | no | no | original | no | aprime_0471_c8d3ce354559 | - | no |
| rare_basin | `59c330181d` | yes | yes | yes | regenerated | yes | - | - | no |
| rare_basin | `61c39609e6` | yes | no | no | original | no | aprime_0478_b5689521556c | - | no |
| rare_basin | `68e7809afe` | yes | yes | yes | regenerated | yes | - | - | no |
| rare_basin | `6a43450649` | yes | yes | yes | regenerated | yes | - | - | no |
| rare_basin | `6a5179f343` | yes | yes | yes | regenerated | yes | - | - | no |
| rare_basin | `6ba1608eba` | yes | no | no | original | no | aprime_0087_9db027afddca | - | no |
| rare_basin | `6edcba0b6c` | yes | yes | yes | regenerated | yes | - | - | no |
| rare_basin | `7056d9cbc9` | yes | no | no | original | no | aprime_0256_ed28eaa9f22c | - | no |
| rare_basin | `738f07b3c9` | yes | yes | yes | regenerated | yes | - | - | no |
| rare_basin | `7748df8143` | yes | no | no | original | no | aprime_0405_268bd5265d8e | decisive_38_217a8f3c70ce | no |
| rare_basin | `789f80e3f1` | yes | no | no | original | no | aprime_0474_0952ccd5b41b | - | no |
| rare_basin | `78ef8aca62` | yes | yes | yes | original | no | aprime_0030_61dd0835fc9a | - | no |
| rare_basin | `85e22b2802` | yes | no | no | original | no | aprime_0567_07c3ec3b4c72 | - | no |
| rare_basin | `86d309e93b` | yes | no | no | original | no | aprime_0037_7370940bf1a8 | - | no |
| rare_basin | `8880cf129b` | yes | yes | yes | regenerated | yes | - | - | no |
| rare_basin | `904cfb5567` | yes | no | no | original | no | aprime_0452_2a25e418359d | - | no |
| rare_basin | `923c5f64e1` | yes | no | no | original | no | aprime_0442_b851c112731a | - | no |
| rare_basin | `94d1f69322` | yes | no | no | original | no | aprime_0367_865a227d0643 | - | no |
| rare_basin | `96208fa985` | yes | no | no | original | no | aprime_0450_30f99bdb26e3 | - | no |
| rare_basin | `a15a44a9dc` | yes | no | no | original | no | aprime_0206_3e7faf12cf26 | - | no |
| rare_basin | `a5678d87d0` | yes | yes | yes | regenerated | yes | - | - | no |
| rare_basin | `a924eb3729` | yes | no | no | original | no | aprime_0151_ba0b2687d533 | - | no |
| rare_basin | `b15b6236be` | yes | yes | yes | regenerated | yes | - | decisive_40_2fbec10d8a00 | no |
| rare_basin | `b22b8fc0c4` | yes | no | no | original | no | aprime_0120_d6228d2f0283 | - | no |
| rare_basin | `b2f6ac09e4` | yes | yes | yes | regenerated | yes | - | - | no |
| rare_basin | `b70ed32290` | yes | no | no | original | no | aprime_0301_c2054a7fdca5 | - | no |
| rare_basin | `b7caffd851` | yes | yes | yes | regenerated | yes | - | - | no |
| rare_basin | `c26530bc5e` | yes | no | no | regenerated | yes | - | - | no |
| rare_basin | `c6d2887cf8` | yes | yes | yes | regenerated | yes | - | - | no |
| rare_basin | `c748394525` | yes | no | no | original | no | aprime_0356_e96e6b9403ea | - | no |
| rare_basin | `c96ae83403` | no | yes | no | original | no | aprime_0683_4ccc666fc57d | - | no |
| rare_basin | `d8f63ba5f0` | yes | no | no | original | no | aprime_0635_0976fdc8bd3d | - | no |
| rare_basin | `dff3291a34` | yes | yes | yes | original | no | aprime_0430_f9f21f0c2ce4 | - | no |
| rare_basin | `e1c09449b3` | yes | no | no | original | no | aprime_0418_381620104ef8 | - | no |
| rare_basin | `e85969841f` | yes | yes | yes | regenerated | yes | - | decisive_02_9643022ddbf6 | no |
| rare_basin | `eb8a69c4bb` | yes | no | no | regenerated | yes | - | - | no |
| rare_basin | `ebe9bb7289` | yes | yes | yes | regenerated | yes | - | - | no |
| rare_basin | `eea0a81585` | yes | no | no | original | no | aprime_0614_0639947cd40b | - | no |
| rare_basin | `fbc623a9c5` | yes | yes | yes | regenerated | yes | - | - | no |
| spotcheck | `02a0495b02` | yes | yes | yes | original | no | aprime_0311_b51e6eaab5cc | - | no |
| spotcheck | `048a3b2598` | yes | yes | yes | original | no | aprime_0680_4345318d0dab | - | no |
| spotcheck | `0599f7b6cf` | yes | yes | yes | original | no | aprime_0336_508baa6a6950 | - | no |
| spotcheck | `0633d156ca` | no | no | yes | original | no | aprime_0331_f1ff243304fe | - | no |
| spotcheck | `109a31f696` | yes | yes | yes | original | no | aprime_0564_41ea0a00617f | - | no |
| spotcheck | `18457d8685` | yes | yes | yes | original | no | aprime_0072_8bbd84c662c3 | - | no |
| spotcheck | `1f31df91c6` | yes | no | no | original | no | aprime_0035_dd7fe5ad978b | - | no |
| spotcheck | `24e7154ef5` | yes | yes | yes | original | no | aprime_0529_8e2c9a3cee0a | - | no |
| spotcheck | `27bbfbd27c` | yes | yes | yes | original | no | aprime_0440_5a67c447858a | - | no |
| spotcheck | `393f2d6019` | yes | yes | yes | original | no | aprime_0656_10c9239a727c | - | no |
| spotcheck | `3954e24faa` | yes | yes | yes | original | no | aprime_0395_eda0a4601ec1 | - | no |
| spotcheck | `5f538942f7` | yes | yes | yes | original | no | aprime_0045_5a7b34ed6e73 | - | no |
| spotcheck | `63c6733bc5` | yes | yes | yes | original | no | aprime_0620_236a995d6151 | - | no |
| spotcheck | `6512aa9084` | yes | yes | yes | original | no | aprime_0009_29c5a77f0573 | - | no |
| spotcheck | `7083396553` | yes | yes | yes | original | no | aprime_0678_0359e11aa43e | - | no |
| spotcheck | `760b82308f` | yes | no | no | original | no | aprime_0234_f26770d95b42 | - | no |
| spotcheck | `8267b168f0` | yes | yes | yes | original | no | aprime_0126_a6a45628d4c6 | - | no |
| spotcheck | `96b711e3a7` | yes | yes | yes | original | no | aprime_0242_d75f2ac745df | - | no |
| spotcheck | `a04761fb39` | yes | no | no | original | no | aprime_0142_a2eefd741ab7 | - | no |
| spotcheck | `a1a793502b` | yes | yes | yes | original | no | aprime_0604_4689a2a5a637 | - | no |
| spotcheck | `a2b12a2559` | yes | yes | yes | original | no | aprime_0508_7023bce96948 | - | no |
| spotcheck | `b3617ad47e` | yes | yes | yes | original | no | aprime_0109_dd82db742d14 | - | no |
| spotcheck | `bec2ff45d5` | yes | yes | yes | original | no | aprime_0538_8bc15fc6a73b | - | no |
| spotcheck | `c0461169c3` | yes | yes | yes | original | no | aprime_0281_36a3b49e6073 | - | no |
| spotcheck | `c0bba8ee6b` | yes | yes | yes | original | no | aprime_0199_0b332e9c48bb | - | no |
| spotcheck | `cb09c10e69` | yes | yes | yes | original | no | aprime_0282_16cf52f5ed06 | - | no |
| spotcheck | `cb74d50a62` | yes | yes | yes | original | no | aprime_0560_b05493151a2a | - | no |
| spotcheck | `d981650d64` | yes | yes | yes | original | no | aprime_0534_77fb5f4d206c | - | no |
| spotcheck | `ed00dc61dc` | yes | yes | yes | original | no | aprime_0089_0605fcbde128 | - | no |
| spotcheck | `f07dd75551` | yes | yes | yes | original | no | aprime_0347_c1e3b56da474 | - | no |

## Per-Pair Legacy B Results

| Pair ID | Contrast | A arm | B arm | Overall mapped | Prompt-fit mapped | Artifact mapped | Flip-risk |
|---|---|---|---|---|---|---|---|
| `0452678119` | arm6_vs_arm1 | arm1 | arm6 | baseline | method | baseline | no |
| `069de95daf` | arm6_vs_arm4 | arm4 | arm6 | method | method | method | no |
| `06f4701ac6` | arm6_vs_arm1 | arm1 | arm6 | baseline | method | baseline | no |
| `0964546740` | arm6_vs_arm1 | arm1 | arm6 | method | tie | method | no |
| `0c400857a4` | arm6_vs_arm1 | arm6 | arm1 | baseline | method | baseline | no |
| `0d73d4c967` | arm6_vs_arm1 | arm6 | arm1 | baseline | baseline | baseline | no |
| `0dc621676d` | arm6_vs_arm1 | arm1 | arm6 | baseline | baseline | baseline | no |
| `0e929f6df2` | arm6_vs_arm4 | arm4 | arm6 | tie | tie | tie | no |
| `0ed5ee6322` | arm6_vs_arm4 | arm4 | arm6 | baseline | baseline | baseline | no |
| `0edf418c90` | arm6_vs_arm1 | arm1 | arm6 | method | tie | method | no |
| `0ee6281212` | arm6_vs_arm1 | arm1 | arm6 | baseline | baseline | baseline | no |
| `12b92c7484` | arm6_vs_arm4 | arm4 | arm6 | method | method | method | no |
| `14439f519a` | arm6_vs_arm4 | arm4 | arm6 | method | method | method | no |
| `15c5ab12b4` | arm6_vs_arm1 | arm1 | arm6 | method | tie | method | no |
| `192439394a` | arm6_vs_arm4 | arm4 | arm6 | tie | tie | tie | no |
| `1afed822a5` | arm6_vs_arm1 | arm6 | arm1 | baseline | method | method | no |
| `1b2e1ef1e1` | arm6_vs_arm4 | arm6 | arm4 | baseline | baseline | tie | no |
| `1b56e856e6` | arm6_vs_arm4 | arm6 | arm4 | baseline | baseline | baseline | no |
| `1bcc08bf50` | arm6_vs_arm1 | arm6 | arm1 | tie | tie | tie | no |
| `1bfaec2e1a` | arm6_vs_arm4 | arm6 | arm4 | baseline | baseline | baseline | no |
| `1de7136439` | arm6_vs_arm4 | arm4 | arm6 | baseline | baseline | baseline | no |
| `1dec4ff807` | arm6_vs_arm1 | arm6 | arm1 | tie | tie | tie | no |
| `1f45861ddf` | arm6_vs_arm1 | arm6 | arm1 | tie | tie | tie | no |
| `2286127a28` | arm6_vs_arm4 | arm4 | arm6 | baseline | tie | tie | no |
| `23a4428f3b` | arm6_vs_arm1 | arm1 | arm6 | tie | tie | tie | no |
| `264728786f` | arm6_vs_arm4 | arm6 | arm4 | method | baseline | method | no |
| `28c0b8d178` | arm6_vs_arm4 | arm6 | arm4 | baseline | tie | baseline | no |
| `2b1b642d29` | arm6_vs_arm4 | arm6 | arm4 | method | method | method | no |
| `312449388f` | arm6_vs_arm4 | arm6 | arm4 | tie | tie | tie | no |
| `35461ee581` | arm6_vs_arm4 | arm4 | arm6 | method | tie | method | no |
| `369f221eb7` | arm6_vs_arm1 | arm6 | arm1 | tie | tie | tie | no |
| `377c6103fb` | arm6_vs_arm4 | arm4 | arm6 | tie | tie | tie | no |
| `37ddd7508b` | arm6_vs_arm4 | arm4 | arm6 | tie | tie | tie | no |
| `37f3136689` | arm6_vs_arm1 | arm6 | arm1 | baseline | baseline | baseline | no |
| `39cdd7883c` | arm6_vs_arm1 | arm1 | arm6 | tie | tie | tie | no |
| `3a3a027580` | arm6_vs_arm1 | arm6 | arm1 | tie | tie | tie | no |
| `3a75fafe4a` | arm6_vs_arm4 | arm4 | arm6 | method | method | baseline | no |
| `3a80d5e5d6` | arm6_vs_arm4 | arm6 | arm4 | baseline | baseline | baseline | no |
| `3e11db4efe` | arm6_vs_arm4 | arm6 | arm4 | tie | tie | tie | no |
| `3f73378469` | arm6_vs_arm4 | arm4 | arm6 | method | tie | method | no |
| `4330d3ef21` | arm6_vs_arm1 | arm1 | arm6 | method | method | method | no |
| `45f9308b5c` | arm6_vs_arm1 | arm1 | arm6 | tie | tie | tie | no |
| `469135185c` | arm6_vs_arm1 | arm6 | arm1 | tie | tie | tie | no |
| `48ee6761b0` | arm6_vs_arm4 | arm4 | arm6 | method | method | method | no |
| `4b0b74e60f` | arm6_vs_arm4 | arm4 | arm6 | baseline | method | baseline | no |
| `4c5a75414f` | arm6_vs_arm4 | arm4 | arm6 | tie | tie | tie | no |
| `4c7a1ff29e` | arm6_vs_arm4 | arm4 | arm6 | baseline | tie | baseline | no |
| `4cf922879e` | arm6_vs_arm1 | arm1 | arm6 | method | method | method | no |
| `4d52fdb395` | arm6_vs_arm1 | arm6 | arm1 | baseline | baseline | tie | no |
| `4dd84edc4d` | arm6_vs_arm4 | arm6 | arm4 | baseline | tie | baseline | no |
| `517b7a7682` | arm6_vs_arm4 | arm6 | arm4 | tie | tie | tie | no |
| `52a3395873` | arm6_vs_arm1 | arm1 | arm6 | baseline | baseline | baseline | no |
| `559e9c07d6` | arm6_vs_arm1 | arm1 | arm6 | method | tie | method | no |
| `58d566feba` | arm6_vs_arm1 | arm1 | arm6 | baseline | tie | baseline | no |
| `59691e99aa` | arm6_vs_arm1 | arm1 | arm6 | baseline | baseline | method | no |
| `5a1a9b570b` | arm6_vs_arm1 | arm6 | arm1 | tie | tie | tie | no |
| `5c3837be9b` | arm6_vs_arm1 | arm1 | arm6 | method | tie | tie | no |
| `5c95b4856b` | arm6_vs_arm4 | arm6 | arm4 | baseline | method | method | no |
| `5f883dad0b` | arm6_vs_arm1 | arm1 | arm6 | baseline | baseline | baseline | no |
| `610e49ae0e` | arm6_vs_arm1 | arm6 | arm1 | baseline | method | baseline | no |
| `658a086f98` | arm6_vs_arm1 | arm1 | arm6 | baseline | method | baseline | no |
| `65b7dc1f0c` | arm6_vs_arm4 | arm6 | arm4 | tie | tie | tie | no |
| `68917e9ad4` | arm6_vs_arm4 | arm6 | arm4 | baseline | baseline | baseline | no |
| `6ebb11813a` | arm6_vs_arm4 | arm6 | arm4 | baseline | baseline | baseline | no |
| `74e77a5d91` | arm6_vs_arm4 | arm6 | arm4 | tie | tie | tie | no |
| `775110280c` | arm6_vs_arm1 | arm6 | arm1 | tie | tie | tie | no |
| `7785d4d1e3` | arm6_vs_arm4 | arm4 | arm6 | baseline | method | baseline | no |
| `79cd69caa5` | arm6_vs_arm1 | arm1 | arm6 | baseline | tie | baseline | no |
| `7c68b8be11` | arm6_vs_arm1 | arm1 | arm6 | method | tie | tie | no |
| `7cd6073fb3` | arm6_vs_arm1 | arm6 | arm1 | baseline | baseline | baseline | no |
| `7d5f199c74` | arm6_vs_arm1 | arm1 | arm6 | baseline | tie | baseline | no |
| `819e7fb30f` | arm6_vs_arm4 | arm4 | arm6 | tie | tie | tie | no |
| `8ca6dff588` | arm6_vs_arm4 | arm4 | arm6 | method | method | method | no |
| `8d9b963d6e` | arm6_vs_arm4 | arm4 | arm6 | tie | tie | tie | no |
| `8dcd41f95c` | arm6_vs_arm4 | arm6 | arm4 | method | method | method | no |
| `966bfff564` | arm6_vs_arm1 | arm1 | arm6 | baseline | tie | baseline | no |
| `a2b5e83a7b` | arm6_vs_arm1 | arm6 | arm1 | tie | tie | tie | no |
| `aaafe53dd7` | arm6_vs_arm4 | arm4 | arm6 | baseline | baseline | tie | no |
| `ab23d83c0f` | arm6_vs_arm4 | arm4 | arm6 | tie | tie | tie | no |
| `ab9bad400f` | arm6_vs_arm1 | arm1 | arm6 | method | method | method | no |

## Judge Gold

`JUDGE_GOLD_CXY_20260710.csv` contains 176 unique original-media, unambiguous Label-A-equivalent rows: 169 yes and 7 no. The deterministic stratified held-out split contains 37 rows.

This gold is **single-rater evidence pending PI or second-rater inter-rater
agreement (kappa)**. It may support provisional T7 diagnostics but cannot by
itself auto-pass judge validation or either human gate.

## Escalation Evaluation

- Missing/ambiguous key rate: 0/282.
- Spotcheck human-versus-Demucs errors: 3/30.
- Legacy overall method preference among decided pairs: 0.363636.
- Conflicting canonical labels on rows overlapping the new primary package: 0.

The mechanical escalation packet, when required, points back to this section
rather than duplicating spoiler numbers elsewhere.
