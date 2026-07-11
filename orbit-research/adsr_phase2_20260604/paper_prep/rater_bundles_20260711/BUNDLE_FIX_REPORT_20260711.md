# Bundle Request-Reveal Fix Report

BUNDLE_FIX_STATUS = READY
evidence: paper_prep/rater_bundles_20260711/BUNDLE_AUDIT.json; paper_prep/rater_bundles_20260711/SHA256SUMS; paper_prep/scripts/build_rater_bundles_20260711.py

REQUEST_METADATA_STATUS = PASS
evidence: paper_prep/rater_admin_keys_20260711/t1_decisive/T1_BUNDLE_KEY_V2.csv; paper_prep/rater_admin_keys_20260711/t3_t4_bprime/T3_BUNDLE_KEY_V2.csv; paper_prep/rater_admin_keys_20260711/t3_t4_bprime/T4_BUNDLE_KEY_V2.csv

STAGED_REVEAL_STATUS = PASS
evidence: paper_prep/scripts/build_rater_bundles_20260711.py; tests/test_rater_bundles_20260711.py

ID_SEED_PRESERVATION_STATUS = PASS
evidence: paper_prep/rater_admin_keys_20260711/t1_decisive/T1_BUNDLE_KEY_V2.csv; paper_prep/rater_admin_keys_20260711/t3_t4_bprime/T3_BUNDLE_KEY_V2.csv; paper_prep/rater_admin_keys_20260711/t3_t4_bprime/T4_BUNDLE_KEY_V2.csv; tests/test_rater_bundles_20260711.py

T2_T5_UNCHANGED_STATUS = PASS
evidence: paper_prep/rater_bundles_20260711/BUNDLE_AUDIT.json; tests/test_rater_bundles_20260711.py

ARCHIVE_CHECKSUM_STATUS = PASS
evidence: paper_prep/rater_bundles_20260711/SHA256SUMS; paper_prep/rater_bundles_20260711/BUNDLE_AUDIT.json

TEST_SUITE_STATUS = PASS
evidence: paper_prep/rater_bundles_20260711/BUNDLE_FIX_TEST_RESULTS_20260711.txt; tests/test_bundle_fix_report_20260711.py

## Corrected Behavior

### t1_decisive_v2

- Contains the same 42 rating rows, opaque IDs, positions, media, and shuffle
  seed as `t1_decisive`.
- Before reveal, only Label A, perceived vocal type, and extent are enabled.
- `Reveal request` remains disabled until all three blind fields are answered.
- Reveal displays a large `REQUEST: VOCAL` or `REQUEST: INSTRUMENTAL` banner and
  only the matching verbatim Label B rule from the signed amendment.
- Reveal locks the Label A fields. The explicit `amend Label A` control can
  unlock them and irreversibly records `label_a_amended=true` for that row.
- Export adds `request_mode`, `label_a_amended`, and `reveal_sequence`.
- `request_mode` is joined from the keys-side `requested_vocal` flag. The
  42-row composition is 29 vocal and 13 instrumental requests.

### t3_bprime_primary_v2 and t4_bprime_reverse_v2

- Preserve the v1 opaque IDs, scorer IDs, positions, media ordering, and
  shuffle seed for all 80 primary and 24 reverse presentations.
- Initially show both audio arms and the verbatim D4 quality instruction, but
  no prompt text or request mode.
- `quality_preference` must be answered before request reveal is enabled.
- Reveal locks `quality_preference`, displays prompt text and request mode, and
  unlocks `constraint_preference` plus `overall_preference`.
- Export records prompt/request context, whether reveal occurred, and event
  sequence fields for quality, reveal, constraint, and overall responses.
- Request modes come from the frozen prompt registry, cross-checked against the
  B-prime manifest. Primary composition is 51 vocal / 29 instrumental; reverse
  composition is 16 vocal / 8 instrumental.

### Unchanged Bundles

`t2_aprime_core` and `t5_sa3_calibration` were not rebuilt. Their tracked HTML
files have no diff, their ZIP SHA-256 values are unchanged, their public rows
contain only `rating_id` plus media, and their payload modes remain `label`.
Neither payload contains Label B wording, request mode, prompt text, or the old
`request_text` field.

## Bundle Paths And SHA-256

| Bundle | Rows | SHA-256 | Download path |
|---|---:|---|---|
| `t1_decisive_v2` | 42 | `b08cd03a839e0fc2c0de977c5116a35afcceda0559c59bd4838836baaf388941` | `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion/orbit-research/adsr_phase2_20260604/paper_prep/rater_bundles_20260711/t1_decisive_v2.zip` |
| `t3_bprime_primary_v2` | 80 | `74fdf9257209ccfc6354f61685f548b40cd416080b29a659f42c9da7a1a55c5e` | `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion/orbit-research/adsr_phase2_20260604/paper_prep/rater_bundles_20260711/t3_bprime_primary_v2.zip` |
| `t4_bprime_reverse_v2` | 24 | `67a095181eab812703bf2acec2270a9bf78940ae51aac456a2b4899860302c2c` | `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion/orbit-research/adsr_phase2_20260604/paper_prep/rater_bundles_20260711/t4_bprime_reverse_v2.zip` |

`SHA256SUMS` lists these three replacements together with the unchanged t2 and
t5 archives. All five entries verify against their local files.

## Preserved Archives

The superseded v1 archives were moved, not deleted, to:

- `paper_prep/rater_bundles_20260711/legacy_v1_archives/t1_decisive.zip`
- `paper_prep/rater_bundles_20260711/legacy_v1_archives/t3_bprime_primary.zip`
- `paper_prep/rater_bundles_20260711/legacy_v1_archives/t4_bprime_reverse.zip`

ZIP files are intentionally ignored generated binaries and were never Git
objects, so `git mv` cannot operate on them. They were preserved with an atomic
filesystem rename; the tracked archive README records their superseded state.
Two pre-release v2 build attempts were also retained without deletion under
`/tmp/AudioDiffusion_bundle_fix_20260711/`.

## Leak And Identity Checks

- Public-field auditing is now allowlist-based, not only denylist-based.
- `request_mode` is allowed for t1/t3/t4 v2; `prompt_text` is allowed only for
  t3/t4 v2.
- `expected_label`, `expected_demucs_label`, `bucket`, `arm`, `set_name`, and
  `set-name` remain forbidden.
- Production key tests compare every v1/v2 bundle ID, scorer ID, position, and
  shuffle seed one-to-one.
- No rater export existed before this rebuild. No evidence labels, ratings,
  scorer outcomes, or A-prime/B-prime gate states changed.

## Test Results

- Focused bundle/remapping/report-compatibility tests: 26 passed, 0 failed.
- Implementation full suite: 243 collected tests reached 100%, exit code 0.
- Final full suite including this report's contract tests: 245 collected tests
  reached 100%, exit code 0, zero failures.
- Active archive checksums: 5/5 matched.
- Replacement archive integrity: 3/3 passed `unzip -t`.
- Generated JavaScript syntax: 3/3 passed `node --check`.
- Python bytecode compilation and `git diff --check`: passed.
- `ruff` was unavailable in the `audio-prm` environment; this is not counted as
  a test pass.

## Files And Commits

- Base commit: `b093462f4a12f5dec68de93098393e8e6fb68128`.
- Implementation commit: `7ebf6443b3a5f4d7d4907f6d4872968dfc7afb23`.
- Report and contract test: the commit containing this report.

Changed tracked files comprise the bundle builder, bundle tests, three v2
key maps, three v2 HTML/README pairs, active audit/checksum metadata, the
legacy-archive README, the append-only recovery ledger, this report, its test
record, and the report-contract regression test. Existing v1 HTML, t2/t5 HTML,
frozen evidence, media, and historical reports were not modified.
