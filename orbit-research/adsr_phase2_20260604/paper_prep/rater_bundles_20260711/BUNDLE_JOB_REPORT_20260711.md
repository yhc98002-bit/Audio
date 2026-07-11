# Rater Bundle and Corrective Job Report

BUNDLES_STATUS = READY
evidence: paper_prep/rater_bundles_20260711/BUNDLE_AUDIT.json; paper_prep/rater_bundles_20260711/SHA256SUMS; paper_prep/scripts/build_rater_bundles_20260711.py
ADMIN_LEAK_TEST = PASS
evidence: paper_prep/rater_admin_keys_20260711/ADMIN_MOVE_MAP.csv; paper_prep/rater_admin_keys_20260711/README_CLUSTER_ONLY.md; tests/test_rater_bundles_20260711.py
LIGHT_PLAN_ADDENDUM = DRAFTED_AWAITING_SIGNATURE
evidence: paper_prep/LIGHT_PLAN_ADDENDUM_20260711.md
CORRECTIVE_FLIP_SENTENCE = FIXED
evidence: paper_prep/CODE_REVIEW_RECOVERY_REPORT_20260709.md; paper_prep/validation_A_prime/regeneration_fidelity_20260709/REGENERATION_RELABEL_RESULTS.csv
RATING_PROVENANCE_ENFORCED = PASS
evidence: paper_prep/scripts/rating_provenance.py; paper_prep/scripts/validation_gate_v2.py; tests/test_rating_provenance_20260711.py; tests/test_validation_gate_v2.py
MERGE_SCRIPT_STATUS = IMPLEMENTED_TESTED
evidence: paper_prep/rater_admin_keys_20260711/t2_aprime/merge_a_prime_instruments.py; tests/test_a_prime_instrument_merge_20260711.py; paper_prep/scripts/bundle_response_io.py
W2_SCAFFOLD_STATUS = DRY_RUN_PASS
evidence: paper_prep/w2_contingency_20260711/W2_CONTINGENCY_README.md; paper_prep/w2_contingency_20260711/W2_RETAINED_AUDIO_INVENTORY.json; paper_prep/w2_contingency_20260711/dry_run/W2_DRY_RUN_REPORT.md
TEST_SUITE_STATUS = PASS
evidence: paper_prep/execution_20260709/CODE_REVIEW_RECOVERY_LEDGER.jsonl; tests/test_rater_bundles_20260711.py; tests/test_w2_contingency_20260711.py

## Scope and Claim Boundary

This job built new rater-facing instruments and hardened the mechanical scoring
path. It did not collect a rating, relabel evidence, modify a frozen ledger, or
change an A-prime/B-prime claim to PASS. Even when mechanical criteria are met,
the gate scorer returns `CRITERIA_MET_AWAITING_PI_GATE_CALL`; only the PI can
make the final gate call.

The false regeneration sentence now states: 20/126 label flips (18/100
A-prime regenerated + 2/26 rare-clean regenerated); the 50/50 regeneration
controls remain exact.

## Bundle Downloads

Each archive contains one directory with only `index.html`, a three-line
`README`, and `media/`. The ZIPs are local cluster artifacts and are excluded
from Git because they contain 5.2 GB of audio.

| Bundle | Rating rows | Media files | Absolute download path | SHA-256 |
|---|---:|---:|---|---|
| t1_decisive | 42 | 42 | `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion/orbit-research/adsr_phase2_20260604/paper_prep/rater_bundles_20260711/t1_decisive.zip` | `bd3352e2926f5b8f8182e277bdc8448bed31f8267a63cc2be0fc70f4bcb07895` |
| t2_aprime_core | 190 | 190 | `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion/orbit-research/adsr_phase2_20260604/paper_prep/rater_bundles_20260711/t2_aprime_core.zip` | `08ef8b9377c48c0ef0108926c82e2713ec8d461af807629591ec7a2eb212c995` |
| t3_bprime_primary | 80 | 160 | `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion/orbit-research/adsr_phase2_20260604/paper_prep/rater_bundles_20260711/t3_bprime_primary.zip` | `71c4dcbc38e69beadd107b07e283b3fa28c634a5414cc91cb58f01d27901dc97` |
| t4_bprime_reverse | 24 | 48 | `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion/orbit-research/adsr_phase2_20260604/paper_prep/rater_bundles_20260711/t4_bprime_reverse.zip` | `f3225b33fe0eb3a5d5295dd11db9868c23c78dfa0460a9eb96723eca06637c9d` |
| t5_sa3_calibration | 60 | 60 | `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion/orbit-research/adsr_phase2_20260604/paper_prep/rater_bundles_20260711/t5_sa3_calibration.zip` | `ef39419302eab4e9d14357e1144c89e4ca3ba4d42e9207f5b62ceea0c4cb5ed5` |

`sha256sum -c paper_prep/rater_bundles_20260711/SHA256SUMS` returned OK for
all five archives. `unzip -tq` reported no errors for every archive.

## Bundle Behavior

- The build fails closed when `ADSR_BLINDING_NONCE` is absent.
- A new mode-600, Git-ignored nonce generated the bundle IDs and shuffle order.
  Only its SHA-256 is recorded; the nonce itself is absent from tracked files.
- The HTML uses only local assets. It provides audio playback, keyboard
  navigation, progress autosave, CSV export, and JSON backup export.
- The one-time rater source accepts only `pi:<name>` or `human:CXY`.
- T1 includes the signed amendment's Label A and Label B wording plus vocal
  type, extent, confidence, and notes.
- T2 contains exactly the 190 human-core rows: 112 detector disagreements, 48
  rare-basin clips, and 30 controls. The 500 judge-track rows are excluded.
- T3 contains exactly the 80 first presentations and uses quality preference
  as the primary question, followed by overall and constraint preference.
- T4 contains exactly 24 reversed presentations and directs the rater to open
  it on a later day than T3.
- T5 contains exactly 60 SA3 calibration clips and asks voice presence plus
  confidence.

## Admin Separation

All answer-bearing active admin manifests, arm maps, prior gate/branch reports,
and scorers were moved with Git history into
`paper_prep/rater_admin_keys_20260711/`. The public bundles contain no
`expected_label`, detector expectation, bucket, arm, or set-name fields. The
tracked `ADMIN_MOVE_MAP.csv` preserves historical report resolution without
putting an admin file back in a rater-facing directory.

Each new public ID joins to its scorer ID only through a cluster-side
`T*_BUNDLE_KEY.csv`. The response loader rejects unknown, partial, duplicate,
blank, or mixed ID namespaces.

## Provenance and Scoring

The shared enum accepts only:

- `pi:<name>`;
- `human:<initials>`;
- `judge:<model>:validated:<64-character gold-set SHA-256>`.

The enum rejects empty, unknown, `qwen_unvalidated`, and `automatic_model`
sources. A validated judge additionally requires a matching model ID and gold
hash, PASS validation metadata, sensitivity, specificity, balanced accuracy,
MCC, abstention rate, a raw-response ledger, and a verified ledger SHA-256.

The A-prime merge enforces 190 pi/human core rows. Its 500 stratified rows may
be pi/human or a fully validated judge and carry the judge model, gold hash,
calibration metrics, raw-response ledger path, and raw-ledger hash into the
merged output. The pre-amendment Qwen fallback scorer is explicitly non-gating.

## Light Plan

`paper_prep/LIGHT_PLAN_ADDENDUM_20260711.md` is deliberately unsigned. It
assigns CXY as the independent primary rater for T2-T5, the PI as T1 rater and
adjudicator for every CXY unsure/detector-disagreement row, and the PI as the
only A-prime/B-prime gate caller. It discloses CXY's prior old-packet exposure.

Do not treat the addendum as approved until the PI signs and commits it.

## W2 Contingency

The retained-audio inventory contains 26,818 metadata rows:

| Cohort | Rows | Media physically available |
|---|---:|---:|
| Stage 3 | 6,144 | 6,144 |
| N2 population retry | 16,384 | 16,384 |
| Atlas keeps | 194 | 194 |
| 4,096-candidate spine | 4,096 | 1 |

The other 4,095 candidate-spine paths are dangling links. They remain recorded
as unavailable and were not regenerated.

The first bounded GPU attempt exposed this issue and failed 50/50 candidate
rows with `LibsndfileError`. Its append-only ledger is preserved under the W2
dry-run failed-attempt directory. After the manifest was fixed to require a
real file target, the current Demucs instrument scored 50 deterministic Stage
3 clips on `an12` GPU 4: 50/50 PASS rows, 50/50 frozen-label agreement, 0
relabels, and `dry_run_only=true` on every result. The diff generator emitted
six condition rows without changing `PLAN.md`.

The scaffold supports current Demucs, Demucs+PANNs with an explicit decision
rule, a human-calibrated threshold, and a held-out-validated judge. A full W2
run remains contingent on Test 1 returning `demucs_missing`.

## Test Results

1. Full suite in the required `audio-prm` environment: 233 tests collected,
   233 passed, exit code 0.
2. Post-line-ending focused rerun: 20 tests passed.
3. Provenance/scorer focused runs: all passed, including invalid-source
   rejection for A-prime and B-prime and a positive validated-judge path.
4. Five production HTML JavaScript payloads passed `node --check`.
5. Five ZIPs passed `unzip -tq`.
6. Five archive hashes passed `sha256sum -c`.
7. An initial full-suite invocation under system Python failed collection
   because that interpreter lacks PyTorch. The mandated `audio-prm` rerun is
   the authoritative result above.

## Files and Commits

- Starting PR #3 head: `7f96712a3392ae72e829c2364029421b632741fd`.
- Corrective implementation commit:
  `8e7f412e36533cd50deb20d4bfbb898d193a9e2c`.
- Implementation commit size: 68 files changed, 3,473 insertions, 95
  deletions; the apparent deletions are Git renames into the cluster-only key
  directory, not artifact deletion.

The implementation commit covers these file groups:

| File group | Purpose |
|---|---|
| `paper_prep/rater_bundles_20260711/` | Public HTML, README, audit, and local archive checksums |
| `paper_prep/rater_admin_keys_20260711/` | Hidden admins, ID maps, reports, scorers, and A-prime merge |
| `paper_prep/scripts/build_rater_bundles_20260711.py` | Deterministic fail-closed bundle construction |
| `paper_prep/scripts/rating_provenance.py` | Shared source enum and validated-judge evidence contract |
| `paper_prep/scripts/bundle_response_io.py` | Public-ID to scorer-ID remapping |
| `paper_prep/w2_contingency_20260711/` | Retained-audio inventory, instruments, relabel runner, and diff generator |
| `tests/test_*20260711.py` plus amended gate tests | Cardinality, leak, provenance, merge, W2, and no-auto-PASS coverage |
| `paper_prep/PLAN.md` | Active artifact paths only; claim status counts unchanged |

The commit containing this report is discoverable with
`git log -1 -- paper_prep/rater_bundles_20260711/BUNDLE_JOB_REPORT_20260711.md`;
embedding that commit hash in the report itself would be self-referential.
