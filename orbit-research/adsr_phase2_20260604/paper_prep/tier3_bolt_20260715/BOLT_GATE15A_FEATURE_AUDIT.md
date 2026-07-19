# BOLT Gate 1.5A State-Feature Audit

STATE_FEATURE_STATUS = PASS
EXPECTED_STATE_FEATURES = 288
STATE_FEATURES = 288
MISSING_STATE_FEATURES = 0
DUPLICATE_STATE_FEATURES = 0
FEATURE_ERRORS = 0
INVALID_PREVIEWS = 0

Promoted-instrument hashes: `['2ec9f12fd9008dae0e32675fcdaaf9e7a22fe0ed7006dd310b665b1e82be2ff2']`. Calibration hashes: `['d9c5bed5b709ac56c7c812fb0e5a04265cd16aba3395510783a4e34be9de4896']`. Scoring protocols: `['bolt_scoring_v2_hash_scoped_deterministic_clap']`.

Every feature row is bound to the persisted state-file and latent hashes and to a decoded-preview SHA-256. The feature extractor did not import or read the action-outcome ledger. Preview common-quality values are retained for audit but excluded from both cross-fitted policy models.
