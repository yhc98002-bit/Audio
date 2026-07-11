# PI Rating Package Integrity Report (2026-07-10)

`PACKAGE_INTEGRITY_STATUS = PASS`

This audit fully decoded every unique audio file, checked every media reference,
verified all recorded SHA-256 values, enforced package ID/cardinality contracts,
and opened each rating CSV through headless LibreOffice. No media were regenerated.

## Blinding Environment

- `ADSR_BLINDING_NONCE`: set for the audit from `/tmp/ADSR_PI_ONLY_KEY_20260710/ADSR_BLINDING_NONCE.env`.
- Secret value: intentionally neither printed nor written to this report.
- The tracked builders remain fail-closed when the variable is absent.

## Package Results

| Package | Admin rows | Rating rows | Media references | Unique media decoded | Checksums | Minimum duration | Template open | Status |
|---|---:|---:|---:|---:|---:|---:|---|---|
| PI decisive construct packet | DECISIVE_PACKET_ADMIN.csv=42 | 42 | 126 | 84/84 | 42/42 | 29.907 s | PASS_LIBREOFFICE_HEADLESS_OPEN | PASS |
| A-prime original-only primary package | A_PRIME_PRIMARY_ADMIN.csv=690 | 690 | 2070 | 1380/1380 | 1380/1380 | 29.907 s | PASS_LIBREOFFICE_HEADLESS_OPEN | PASS |
| B-prime solo-rater package | B_PRIME_ORDERED_ADMIN.csv=104, B_PRIME_PAIR_ADMIN.csv=80 | 104 | 416 | 208/208 | 208/208 | 30.186 s | PASS_LIBREOFFICE_HEADLESS_OPEN | PASS |

## Failures And Recovery

No missing, undecodable, short-duration, checksum-mismatched, malformed, or stale-template artifact was found. No recovery was required.

## PI Start Paths

### PI decisive construct packet

- Start path: `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion/orbit-research/adsr_phase2_20260604/paper_prep/pi_decisive_packet_20260709/DECISIVE_PACKET_RATINGS.csv`
- Launch: `libreoffice --calc "/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion/orbit-research/adsr_phase2_20260604/paper_prep/pi_decisive_packet_20260709/DECISIVE_PACKET_RATINGS.csv"`

### A-prime original-only primary package

- Start path: `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion/orbit-research/adsr_phase2_20260604/paper_prep/validation_A_prime/primary_package_20260709/A_PRIME_PRIMARY_RATINGS.csv`
- Launch: `libreoffice --calc "/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion/orbit-research/adsr_phase2_20260604/paper_prep/validation_A_prime/primary_package_20260709/A_PRIME_PRIMARY_RATINGS.csv"`

### B-prime solo-rater package

- Start path: `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion/orbit-research/adsr_phase2_20260604/paper_prep/validation_B_prime/pi_package_20260709/B_PRIME_PI_RATINGS.csv`
- Launch: `libreoffice --calc "/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion/orbit-research/adsr_phase2_20260604/paper_prep/validation_B_prime/pi_package_20260709/B_PRIME_PI_RATINGS.csv"`
