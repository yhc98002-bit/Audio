# AUTOPILOT MASTER PROTOCOL — regime_atlas_autopilot_v3 (persisted spine)

**Status: AWAITING_PI_SANITY_GATE** (no large-N until PI passes the sanity gate).

## Operating model
Claude Code = orchestrator (write specs, launch DETACHED non-LLM workers, validate, analyze,
promote per written criteria, log decisions/surprises). Never sit in the per-sample loop.
Resume protocol (Section 4): on startup re-read this dir + queue/ before launching anything.

## Neutral research questions (spine, not ceiling)
- RQ1 large-N resampling p(clean) at fixed N=256 (+512/1024 tail extension).
- RQ2 STRONG_ESCAPABLE_BASIN = near-zero p ∧ audit-real ∧ intervention escapes (joint, all three).
- RQ3 rare-but-recoverable (p>0 but huge N).
- RQ4 instrumental dissociation: ceiling / action-unavailable / detector-artifact / bad-prompt / fixable.
- RQ5 router (single early trajectory, no k-seed in headline) beats always-BoN AND always-intervene.
- RQ6 generality: 3rd music axis / 2nd backbone / T2I.
- RQ7 human eval: no perceptual harm; label validity on detector-disagreement cases.
- RQ-OPEN: emergent — keep live in SURPRISES_AND_LEADS.md, treat strong answers as candidate headlines.

## Reporting discipline
Facts + figures + auditable examples. Hypotheses allowed but LABELED (SURPRISES_AND_LEADS.md).
PI maps numbers→claims. No "this proves/confirms/challenges …" language anywhere in results.

## Critical path (land this if only one thing): §15 CORE-1 E2 vocal tail large-N BoN + paired
intervention + audit packet + instrumental dissociation. Exploration (§23A) runs concurrently on spare GPUs.

## Regime labels: see this file's companion REGIME_SCHEMA (02_failure_regime_atlas/REGIME_SCHEMA.md).
Headline-eligible row requires: detector_reliability PASS + manual_audit PASS(where required) +
fixed-N aggregation + complete source trace + not contradictory + lyric-sentinel masked.

## STANDING RULE (added 2026-06-23) — CODEX REVIEW GATE (CLAUDE.md compliance)
CLAUDE.md mandates proactive Codex collaboration on long/important/uncertain/high-impact/surprising
work; v3.1/v3.2 keep CLAUDE.md hard rules in force. This was dropped during the autonomous phase —
reinstated as a gate:
- BEFORE any result is written to STATUS_DAILY/PI_SUMMARY as a **candidate headline** or used to
  promote a regime to HEADLINE_ELIGIBLE, run an independent `codex exec` review (read-only,
  </dev/null + timeout) of (a) the measurement script(s) producing it and (b) the interpretation,
  asking for bugs + over-reach. Record it in CODEX_REVIEWS.md (artifact, prompt, verdict, fixes).
- ALSO Codex-review: every new measurement/analysis script before first large-N use; any surprising
  result; any script touching shared/frozen-adjacent behavior.
- The MCP codex tool may be down; use the **codex CLI** (`codex exec`) — it is the CLAUDE.md mechanism
  and is independent of the MCP.
