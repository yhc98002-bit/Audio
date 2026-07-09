"""D6 — locality probe smoke (DIAGNOSTIC_EXPERIMENT_PLAN §2 D6).

**Status: DEFERRED.** Phase A audit scaffold does not exercise latent-span perturbation;
locality probe machinery lives in Phase B/C and will be implemented in the next
`/experiment-bridge` call. This script exists as a placeholder so the diagnostic launcher
can call it explicitly and produce a clear deferred message rather than a missing-file error.
"""
from __future__ import annotations

import sys


def main() -> int:
    print("D6 DEFERRED")
    print("  reason: locality probe requires latent-span perturbation logic that is part of"
          " Phase B/C scaffolding.")
    print("  route:  this script will be implemented in the NEXT /experiment-bridge call,")
    print("          alongside Phase B Tweedie reliability + locality probe.")
    print("  Wave W2 gate: D6 is NOT required for Wave W2 Phase A launch per the scoped audit"
          " (see orbit-research/PLAN_CODE_AUDIT.md §4).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
