# ORBIT Open Questions

## Phase C1

- Is the 168.12 GPU-h projection conservative, warmup-biased, or unstable due to only 2 terminal-method steps and 6-7 process-method steps?
- Should the formal run clean-restart because no checkpoint exists and the runner refuses existing logs?
- Is one-method-per-GPU the only validated safe parallelism, or is there an already implemented DDP/rollout parallel path that preserves a single adapter per method?
- How should the updated PI cap of 240 GPU-h be enforced operationally when the checked-in config still contains the old 120 GPU-h policy?

Resolved current launch gate:

- Active GPU-h estimate is below the current `240.0` Task C cap, but early
  clean-run monitoring remains required because terminal estimates are based on
  only two observed partial-run steps.
- Clean restart is required; the partial stopped run has no checkpoints and
  unbalanced method step counts.
- Safe parallelism is one method per GPU. Prompt sharding is not scientifically
  equivalent because it would train separate adapters.

## Diagnostics

- Are early Tweedie per-candidate scores at sigma 0.9/0.8/0.7 available for BoN-8 candidates, or only final/process aggregate summaries?
- Are fixed-window reward curves per sample available in existing H3/C1 artifacts with enough samples for between-vs-within variance?

Resolved current diagnostic status:

- Exact BoN candidate-level early sigma/Tweedie scores were not found in the
  scoped cached artifacts. Early-Tweedie is therefore `preliminary` and proxy
  only, not an exact BoN pruning retrospective.
- Cached H3 local vectors were sufficient for the time-uniform diagnostic;
  current classification is `likely`.
