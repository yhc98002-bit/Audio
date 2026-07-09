# Doc Hygiene Forward Plan (2026-05-20)

*PI 2026-05-20 surfaced two structural improvements during a doc-cleanup discussion. Both are correct, both are large refactors that should NOT be executed impulsively. This file captures the plan.*

> **Status refresh (2026-05-23):** A medium prose-hygiene cleanup has now been
> completed separately: stale entrypoint status was refreshed and superseded dated
> prose moved under archive directories. The large P1 namespace migration and P2
> `FACTS.yaml` registry below are still future work and were not executed.

---

## P1 — Namespace collision (R-prefix and M-prefix and H-prefix overlap)

**Current collision map** (PI-identified):

| Prefix | Meaning A | Range A | Meaning B | Range B | Risk |
|--------|-----------|---------|-----------|---------|------|
| `R` | rung (architectural component) | R0–R21 | run (run-ledger entry) | R000–R800 | Cross-file ref ambiguity |
| `M` | milestone (Phase A timeline) | M0–M8 | mechanism candidate | M1–M17 | Method "M-PRM" also has M prefix |
| `H` | hypothesis | H1–H6 | analogy (in ANALOGY_TRANSFER) | H1–H13 | Both numeric, same prefix |

**Why this matters for AI workflows**: an LLM reasoning across files can confuse `R8` (deprecated rung) with `R008` (a specific run), or `M2` (mechanism) with `M2` (milestone). Human readers usually disambiguate by context; agents reasoning by token-pattern often cannot.

**Proposed namespace** (PI suggested):
- `RUNG-NN` — architectural rungs (RUNG-00 through RUNG-21)
- `RUN-NNN` — run-ledger entries (RUN-000 through RUN-800)
- `MS-N` — milestones (MS-0 through MS-8)
- `MECH-NN` — mechanism candidates (MECH-01 through MECH-17)
- `HYP-N` — pre-registered hypotheses (HYP-1 through HYP-6)
- `ANLG-NN` — analogy candidates (ANLG-01 through ANLG-13)

**Scope of refactor** (estimated):
- ~20 markdown docs in `refine-logs/` + `orbit-research/` reference at least one of these prefixes
- ~12 YAML configs in `configs/baselines/` use `R0`–`R9` rung IDs
- ~50 Python files in `src/` use rung_id strings
- ~200 entries in `orbit-research/RUN_LEDGER.jsonl` use `R000+` run-IDs
- 8+ launcher / orchestrator scripts use rung_id arguments

**Estimated effort**: 2-3 days of careful renaming + audit. CANNOT be done while Phase A M1a is running (run-ledger entries would split between old and new namespaces).

**Recommended execution window**: AFTER M1a held-out gate decision is recorded. Lock all M1a outputs under `R...` legacy names; new Phase B onward uses `RUNG-...` namespace. Migration script translates `R8` ↔ `RUNG-08` for cross-phase queries.

**Recommended migration order**:
1. Write `MIGRATION_NAMESPACE.md` documenting old↔new mapping table
2. Add backwards-compatibility shims in `src/mprm/baselines/__init__.py` (both `R8` and `RUNG-08` import OK)
3. Update `configs/baselines/` YAML filenames (rung 0-9 keep; 10+ get RUNG- prefix)
4. Update `EXPERIMENT_PLAN_EXEC.md` + `COMPONENT_BUNDLE_LADDER.md` (most touched)
5. Update `ALGORITHMIC_FORMALIZATION.md` baseline table
6. Update `RUN_LEDGER.jsonl` going forward (existing rows stay)
7. Strict mode: shim removal after Phase D
8. ANLG / MECH / HYP / MS namespaces follow same pattern, but lower priority (fewer cross-file references).

**Priority**: MEDIUM. The collision is theoretical but real; no incident yet. Not blocking M1a held-out gate.

---

## P2 — FACTS.yaml registry (atomic facts with interpolation)

**Current problem**: a single atomic fact (e.g., "M1b is not a paper-gate") is restated in:
- `refine-logs/EXPERIMENT_PLAN.md` (index)
- `refine-logs/EXPERIMENT_PLAN_EXEC.md` Block A.2
- `orbit-research/NULL_RESULT_CONTRACT.md` §1.2
- `orbit-research/COMPONENT_BUNDLE_LADDER.md` §3
- `papers/explainers/COMPUTE_TIMELINE.md` (in passing)

When any of those needs updating, all five must update in sync. **STOP-B-3 consistency-audit fix** existed BECAUSE of this O(n × m) maintenance burden — it caught a desync between EXPERIMENT_PLAN.md and EXPERIMENT_PLAN_EXEC.md.

**Proposed solution** (PI specified): atomic facts in `FACTS.yaml` or `REGISTRY.yaml`, referenced in markdown via `${facts.foo}` interpolation.

```yaml
# orbit-research/FACTS.yaml (proposed)
facts:
  m1b_not_a_gate:
    statement: "M1b failures are implementation-side, never paper pivots"
    referenced_by:
      - refine-logs/EXPERIMENT_PLAN.md
      - refine-logs/EXPERIMENT_PLAN_EXEC.md#block-a-2
      - orbit-research/NULL_RESULT_CONTRACT.md#section-1-2
      - orbit-research/COMPONENT_BUNDLE_LADDER.md#section-3
    last_updated: 2026-05-15
    locked: true                      # cannot change post-pre-registration

  threshold_headroom_min_effect:
    value: 0.25
    unit: sigma_R_lcb_holdout
    pre_registered: true
    referenced_by:
      - orbit-research/HEADROOM_GATE_PREREG.md#T1
      - refine-logs/EXPERIMENT_PLAN_EXEC.md#block-a-1
      - orbit-research/ASSUMPTION_LEDGER.md#H1
    locked: true

  cvar_beta_main:
    value: 0
    revised: 2026-05-20
    revised_from: 0.5
    revised_by: revision-C2
    referenced_by:
      - refine-logs/FINAL_PROPOSAL.md#h6
      - orbit-research/ASSUMPTION_LEDGER.md#H6
      - orbit-research/ALGORITHMIC_FORMALIZATION.md#section-3-4
      - refine-logs/EXPERIMENT_PLAN_EXEC.md#block-c
    locked: false                     # can revise pre-Phase-B
```

**Markdown reference syntax** (PI proposed):
```markdown
- M1b is not a gate (${facts.m1b_not_a_gate.statement}).
- Headroom min-effect: ${facts.threshold_headroom_min_effect.value} ${facts.threshold_headroom_min_effect.unit}.
- CVaR β default: ${facts.cvar_beta_main.value} (revised ${facts.cvar_beta_main.revised} from ${facts.cvar_beta_main.revised_from}).
```

**Required tooling**:
1. **Linter** (`tools/check_facts.py`): scans markdown for `${facts.X}` references; validates X exists in `FACTS.yaml`; validates `referenced_by` list matches actual files containing the reference.
2. **Renderer** (optional, for paper export): substitutes `${facts.X}` with the literal value when generating LaTeX or final paper. Not needed for in-project agent consumption.
3. **Migrator** (`tools/migrate_to_facts.py`): semi-automated extraction of repeated facts into FACTS.yaml + replacement in source markdown.

**Scope of refactor**:
- Phase 1 (small, high-value): extract ~15 critical facts (gate thresholds, hypothesis IDs, decision-matrix outcomes). ~3 days.
- Phase 2 (medium): extract operational facts (rung definitions, baseline composition). ~2 days.
- Phase 3 (large, optional): extract narrative-level facts. Diminishing returns — at some point the fact IS the prose.

**Estimated effort**: Phase 1 alone = 3 days for migration + tooling. Phase 1+2 = 5 days. Phase 3 = open-ended.

**Recommended execution window**: AFTER namespace migration P1 completes (avoid mixing two refactors). Phase 1 (15 critical facts) is the minimum-viable.

**Priority**: HIGH-MEDIUM. The redundancy bug already cost one STOP-B-3 consistency-audit cycle. As project grows past 38 docs, the maintenance cost grows quadratically.

---

## Combined timeline

| When | Action | Effort |
|------|--------|--------|
| Now | **DO NOTHING** — Phase A M1a held-out still running, refactoring would destabilize ledger | 0 |
| Post-M1a-gate (≤24h after held-out completes) | Write `MIGRATION_NAMESPACE.md` (mapping table only) | 1 day |
| Post-M1a-gate + 1d | Build `FACTS.yaml` Phase 1 (15 critical facts) + linter | 2 days |
| Phase B kickoff -1w | Update `EXPERIMENT_PLAN_EXEC.md` + `COMPONENT_BUNDLE_LADDER.md` to RUNG-NN + ${facts.X} for new rows | 1 day |
| Phase B kickoff | Strict-mode shim removal (old `R8` syntax errors); FACTS-linter integrated into pre-commit | 1 day |
| Phase D end | ANLG/MECH/HYP/MS namespace migration (lower priority; many cross-references touched) | 1 day |

**Total estimated**: ~6 days of focused doc-engineering work, spread over Phase A→B transition. NOT urgent (no current bug); IMPORTANT (prevents future agent drift).

**Reference**: PI feedback 2026-05-20 — `[[feedback-doc-durability]]` memory entry.
