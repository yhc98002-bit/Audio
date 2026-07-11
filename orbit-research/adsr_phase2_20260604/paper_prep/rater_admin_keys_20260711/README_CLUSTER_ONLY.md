# Cluster-Only Rating Keys

This directory contains answer-bearing manifests, bundle-to-scorer ID maps,
gate reports, and scoring programs. Do not distribute it with any rater bundle.

The five directories under `paper_prep/rater_bundles_20260711/` are the only
rater-facing artifacts. Scorers consume exported responses together with the
corresponding `T*_BUNDLE_KEY.csv` here and fail closed on unknown IDs or rating
provenance.

The local `.bundle_nonce` is mode 600 and ignored by Git. Its value must never
appear in reports, ledgers, bundles, commits, or release artifacts.
