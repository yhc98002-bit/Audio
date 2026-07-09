#!/usr/bin/env bash
# Orchestrates Phase A rungs in the order specified by COMPONENT_BUNDLE_LADDER.md
# AND the STOP-B-1 M1a/M1b split:
#
#   M0  (W1)   — D0–D5 diagnostic + UI scaffold smoke (STOP-B-1 fix #4)
#   M1a (W2.1) — R0/R1/R2/R3/R4/R9 on dev + held-out (gate-critical on held-out)
#               + reward-human spot-check (Block A.aux)
#               -> compute_headroom_gate decision
#               -> HALT if gate fails (STOP-B-1 fix #2)
#   M1b (W2.2) — R5/R6/R7/R8a/R8b on dev (only if M1a gate passed)
#
# D6/D7 are formally deferred per STOP-B-2 fix #3 (pre-Phase-B diagnostics; not gating M1a).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# Paratera env auto-activation (2026-05-19): on the sichuan/guangxi boxes the
# audio-prm env was on PATH via .bashrc; on Paratera the caller (e.g. /run-experiment)
# may invoke this script from a shell without conda activated. Source the env
# idempotently so every `python ...` below resolves to the audio-prm bin.
# 2026-05-19 Codex review: activation failure must hard-stop (silent fallback
# to /usr/bin/python3 produces a confusing import error several lines later).
if [[ "${CONDA_DEFAULT_ENV:-}" != "audio-prm" ]]; then
    if [[ ! -f /APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh ]]; then
        echo "ERROR: conda init script not found at /APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh." >&2
        echo "  Run \`module load anaconda3/2023.09\` first, or invoke this script from an interactive shell with the env already active." >&2
        exit 1
    fi
    # shellcheck disable=SC1091
    source /APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh
    if ! conda activate audio-prm; then
        echo "ERROR: failed to activate conda env audio-prm. Verify the env exists:" >&2
        echo "  \`ls /HOME/paratera_xy/pxy1289/.conda/envs/audio-prm\`" >&2
        echo "  Rebuild via the Paratera env-build recipe in CLAUDE.md §Environment activation." >&2
        exit 1
    fi
fi
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"

# Paratera reward-weight pointers (2026-05-19): use the pre-staged copies under
# ~/HDD_POOL/source/ (downloaded by tools/predownload_reward_weights.sh on a
# fast node). Existing env vars are respected — only set when unset.
_SRC="${HOME}/HDD_POOL/source"
export LAION_CLAP_BERT_DIR="${LAION_CLAP_BERT_DIR:-${_SRC}/laion_clap_tokenizers/bert-base-uncased}"
export LAION_CLAP_ROBERTA_DIR="${LAION_CLAP_ROBERTA_DIR:-${_SRC}/laion_clap_tokenizers/roberta-base}"
export LAION_CLAP_BART_DIR="${LAION_CLAP_BART_DIR:-${_SRC}/laion_clap_tokenizers/facebook--bart-base}"
export AUDIOBOX_AES_CKPT="${AUDIOBOX_AES_CKPT:-${_SRC}/audiobox_aesthetics/checkpoint.pt}"
export MERT_LOCAL_PATH="${MERT_LOCAL_PATH:-${_SRC}/mert/MERT-v1-95M}"
unset _SRC

MODE="${MODE:-production}"

# STOP-B-6 fix #3: STOP_AFTER_M1A controls whether the script proceeds into M1b
# after the M1a basic-headroom gate. Values:
#   auto (default): production → 1 (R8a/R8b are deferred scaffolds, so the M1b
#                                 loop would otherwise fail-out partway through);
#                   dev        → 0 (sampling-only call paths are exercised).
#   1            : always halt cleanly between M1a gate pass and M1b launch.
#   0            : always proceed into M1b (use only when R8a/R8b production
#                  support is enabled).
STOP_AFTER_M1A="${STOP_AFTER_M1A:-auto}"
if [[ "${STOP_AFTER_M1A}" == "auto" ]]; then
    if [[ "${MODE}" == "production" ]]; then
        STOP_AFTER_M1A=1
    else
        STOP_AFTER_M1A=0
    fi
fi

# STOP-B-7 START_AT_M1B resume path (Codex STOP-B-6 caveat). When the M1a gate
# has already passed durably in a prior run (orbit-research/HEADROOM_GATE_DECISION.json
# shows pass_gate=true), the operator can rerun ONLY M1b without redoing
# M0/M0.5/M1a. Disabled by default. Requires the gate-decision file to exist
# with pass_gate=true AND under the live gate_v1 policy hash.
START_AT_M1B="${START_AT_M1B:-0}"
_SKIP_M0_M1A=0
if [[ "${START_AT_M1B}" == "1" ]]; then
    # STOP-B-7.1 Q6: all four conditions are now strictly enforced.
    #   1. orbit-research/HEADROOM_GATE_DECISION.json must exist.
    #   2. pass_gate MUST be the boolean True (not "true" string, not 1, not truthy).
    #   3. configs/eval/gate_v1.yaml MUST exist; stamped hash MUST equal live hash.
    #   4. Corrupt JSON, YAML errors, or hash-computation errors are FATAL (no
    #      WARN-and-proceed escape).
    python <<'PY' || exit 2
import json
import sys
from pathlib import Path

decision_path = Path("orbit-research/HEADROOM_GATE_DECISION.json")
policy_path = Path("configs/eval/gate_v1.yaml")

if not decision_path.exists():
    print(f"START_AT_M1B=1 refused: {decision_path} does not exist."
          " M1a gate has not been computed yet — run launch_phase_a.sh from"
          " the top first.")
    sys.exit(2)

try:
    d = json.loads(decision_path.read_text(encoding="utf-8-sig"))
except Exception as e:  # noqa: BLE001  STOP-B-7.2: catch UnicodeDecodeError, etc.
    print(f"START_AT_M1B=1 refused: {decision_path} could not be parsed"
          f" ({type(e).__name__}: {e}).")
    sys.exit(2)
if not isinstance(d, dict):
    print(f"START_AT_M1B=1 refused: {decision_path} is not a JSON object.")
    sys.exit(2)

# STOP-B-7.1 Q6: strict identity check, not truthiness — "false" or 1 will NOT pass.
if d.get("pass_gate") is not True:
    print(f"START_AT_M1B=1 refused: {decision_path} has pass_gate="
          f"{d.get('pass_gate')!r} (must be the boolean True)."
          f" reason={d.get('reason')!r}. M1b launch would violate the M1a"
          " null-result contract.")
    sys.exit(2)

# STOP-B-7.1 Q6: gate_v1.yaml MUST exist + hash MUST be present and match.
if not policy_path.exists():
    print(f"START_AT_M1B=1 refused: gate-policy file {policy_path} does not exist.")
    sys.exit(2)
try:
    import hashlib
    import yaml
    with policy_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    policy = (raw or {}).get("eval_policy")
    if not isinstance(policy, dict):
        raise ValueError("eval_policy block missing or not a dict")
    canonical = json.dumps(policy, sort_keys=True, separators=(",", ":"))
    live_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
except Exception as e:  # noqa: BLE001
    print(f"START_AT_M1B=1 refused: could not compute live gate_v1 hash"
          f" ({type(e).__name__}: {e}).")
    sys.exit(2)

stamped = (d.get("gate_eval_policy") or {}).get("hash")
if not stamped:
    print(f"START_AT_M1B=1 refused: {decision_path} has no"
          " gate_eval_policy.hash (legacy decision predates STOP-B-7).")
    sys.exit(2)
if stamped != live_hash:
    print(f"START_AT_M1B=1 refused: decision was made under gate_v1 hash"
          f" {stamped!r}, but configs/eval/gate_v1.yaml currently hashes"
          f" to {live_hash!r}. Either revert gate_v1.yaml or rerun M1a"
          " under the new policy.")
    sys.exit(2)

print(f"START_AT_M1B=1 verified: {decision_path} pass_gate=True, hash matches.")
PY
    _SKIP_M0_M1A=1
    # M1b requires runs/M0_5_GATE_PASSED.flag (STOP-B-5 launch_baseline.py gate).
    # If the prior run cleared it (STOP-B-6 fix #4 always clears at start), recreate
    # a minimal flag so M1b can launch. We're trusting the gate-decision file as
    # the durable record of M0.5 + M1a having been satisfied.
    if [[ ! -f runs/M0_5_GATE_PASSED.flag ]]; then
        mkdir -p runs
        cat > runs/M0_5_GATE_PASSED.flag <<EOF
# STOP-B-7 START_AT_M1B=1: recreated from durable HEADROOM_GATE_DECISION.json.
# Original M0.5 was satisfied in a prior run; this flag is a successor handle.
timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)
mode: ${MODE}
recreated_for: START_AT_M1B
host: $(hostname)
EOF
        echo "STOP-B-7: recreated runs/M0_5_GATE_PASSED.flag from durable gate decision."
    fi
    # STOP_AFTER_M1A=1 + START_AT_M1B=1 is incoherent (skip M1a then stop after
    # M1a). Force STOP_AFTER_M1A=0 so M1b actually runs.
    if [[ "${STOP_AFTER_M1A}" != "0" ]]; then
        echo "STOP-B-7: START_AT_M1B=1 overrides STOP_AFTER_M1A=${STOP_AFTER_M1A} → 0."
        STOP_AFTER_M1A=0
    fi
fi

# STOP-B-6 fix #4: clear any stale M0.5 gate flag from a previous run BEFORE the
# pipeline starts. Skipped when START_AT_M1B=1 because the resume path needs the
# flag from the prior run (or its recreated successor written above).
if [[ "${_SKIP_M0_M1A}" != "1" && -f runs/M0_5_GATE_PASSED.flag ]]; then
    echo "STOP-B-6: clearing stale runs/M0_5_GATE_PASSED.flag from a prior run."
    rm -f runs/M0_5_GATE_PASSED.flag
fi

if [[ "${_SKIP_M0_M1A}" != "1" ]]; then

# ============================================================
# M0 — diagnostic gate + UI scaffold smoke
# ============================================================

# STOP-B-8 Phase-2 (2026-05-18): on the multi-tenant pro6000 box other users
# load physical GPU 0/1/4 dynamically. Pin all M0 D-scripts that load GPU
# models to an idle physical GPU via $M0_GPU (default 2). The subprocess
# `CUDA_VISIBLE_DEVICES` env var is interpreted as ABSOLUTE physical indices
# (subprocess.Popen breaks parent CVD transitivity in Python), so set the
# physical index directly rather than relying on outer-script CVD nesting.
M0_GPU="${M0_GPU:-2}"

echo "=== M0 D0 env check (mode=${MODE}) ==="
CUDA_VISIBLE_DEVICES="${M0_GPU}" python scripts/d0_env_check.py --mode "${MODE}"

echo "=== M0 D1 model load smoke (ace_step_v15) ==="
CUDA_VISIBLE_DEVICES="${M0_GPU}" python scripts/d1_model_load.py --model ace_step_v15

echo "=== M0 D2 reward harness smoke ==="
CUDA_VISIBLE_DEVICES="${M0_GPU}" python scripts/d2_reward_harness.py --model ace_step_v15

echo "=== M0 D3 Tweedie reconstruction sanity (STOP-B-8 DEFERRED) ==="
# STOP-B-8 (Codex Q7): d3_tweedie_sanity.py calls `model.sample(return_trajectory=True)`
# and `model.tweedie_decode(...)`. The STOP-B-8 minimal ACE-Step v1 adapter raises
# NotImplementedError for both (upstream v1 public API exposes neither intermediate-
# step latents nor direct flow_head + decode access). Running D3 would therefore
# halt the script under `set -e`. D3 is a Phase B / M2 entry diagnostic, NOT an M1a
# gate dependency, so we defer it cleanly here. Phase B remains hard-blocked until
# STOP-B-9 reopens trajectory + flow-head access (and D3a STATUS = RESOLVED).
echo "  D3 is deferred to STOP-B-9 / Phase B entry (requires trajectory + tweedie_decode)."
echo "  M1a does not depend on D3 PASS; this stop is informational only."

echo "=== M0 D4 segmentation + Demucs + Whisper smoke ==="
D4_AUDIO="${D4_AUDIO:-papers/diagnostic/d4_reference.wav}"
D4_LYRICS_FILE="${D4_LYRICS_FILE:-papers/diagnostic/d4_reference.lyrics.txt}"
D4_FLAG="papers/diagnostic/MISSING_D4_REFERENCE.flag"
# STOP-B-8 Phase-1 (Codex Q5 fix): the MISSING flag is now authoritative in
# production. Files present + flag still there would be confusing — refuse and
# tell the operator to delete the flag once they've validated D4.
if [[ "${MODE}" == "production" && -f "${D4_FLAG}" ]]; then
    echo "D4 BLOCK (production): ${D4_FLAG} is present."
    echo "  Stage real D4 reference per ${D4_AUDIO/.wav/_INSTRUCTIONS.md},"
    echo "  validate it, then: rm ${D4_FLAG}"
    exit 2
fi
if [[ -f "${D4_AUDIO}" && -f "${D4_LYRICS_FILE}" ]]; then
    D4_LYRICS="$(cat "${D4_LYRICS_FILE}")"
    CUDA_VISIBLE_DEVICES="${M0_GPU}" python scripts/d4_segmentation.py --audio "${D4_AUDIO}" --lyrics "${D4_LYRICS}"
else
    if [[ "${MODE}" == "production" ]]; then
        echo "D4 BLOCK: ${D4_AUDIO} and/or ${D4_LYRICS_FILE} not found."
        echo "  Stage a real vocal reference + lyrics before Wave W2 production launch."
        echo "  See papers/diagnostic/D4_REFERENCE_INSTRUCTIONS.md for acceptance criteria."
        echo "  To run the scaffold in dev mode anyway: MODE=dev bash scripts/launch_phase_a.sh"
        exit 2
    fi
    echo "D4 WARN (dev mode): ${D4_AUDIO}/${D4_LYRICS_FILE} not found; running on D2"
    echo "         instrumental sample without WER check. Stage real reference before W2."
    CUDA_VISIBLE_DEVICES="${M0_GPU}" python scripts/d4_segmentation.py --audio papers/diagnostic/d2/d2_test.wav
fi

echo "=== M0 D5 mini Flow-GRPO sampling smoke (STOP-B-8 DEFERRED) ==="
# STOP-B-8 (Codex Q7): d5_mini_flow_grpo.py calls `model.sample(sde_mode=True,`
# `eta_schedule=…, return_trajectory=True)`. STOP-B-8 minimal adapter raises
# NotImplementedError for all three. D5 is the mini Flow-GRPO sampling smoke and
# is a pre-Phase-B sanity check (advantage spread / trajectory variance), NOT an
# M1a gate dependency. Defer to STOP-B-9 / Phase B entry alongside D3.
echo "  D5 is deferred to STOP-B-9 / Phase B entry (requires sde_mode + trajectory)."
echo "  M1a does not depend on D5 PASS; this stop is informational only."

echo "=== M0 D6/D7 deferred-stub notice (STOP-B-2 fix #3) ==="
echo "  These are pre-Phase-B diagnostics; they do not gate M1a."
python scripts/d6_locality_probe.py
python scripts/d7_mini_m_prm.py

echo "=== M0 UI smoke (STOP-B-1 fix #4 — UI built in M0, used by M6) ==="
if [[ "${SKIP_UI_SMOKE:-0}" == "1" ]]; then
    echo "  SKIP_UI_SMOKE=1 — skipping UI smoke."
else
    python -c "from mprm.ui.server import smoke_check; smoke_check()" || {
        echo "M0 UI smoke FAIL. The UI scaffold under src/mprm/ui/ is not ready."
        echo "  Build the UI or set SKIP_UI_SMOKE=1 to defer it (M6 will block if unbuilt)."
        if [[ "${MODE}" == "production" ]]; then
            exit 2
        fi
    }
fi

# ============================================================
# M0.5 — pre-M1a checks (STOP-B-4)
#
#   D3a Tweedie code-level derivation: hard gate on Phase B / M2 (NOT on M1a).
#                                       M1a may proceed in parallel if D3a is
#                                       not yet RESOLVED — Phase B blocks instead.
#   R050 informal mini-headroom probe:  pause-and-report; M1a's 256-prompt audit
#                                       is the authoritative gate, so production
#                                       can still proceed at PI discretion.
# ============================================================

echo "=== M0.5 D3a Tweedie code-level derivation (STOP-B-4 + STOP-B-5 fix) ==="
# STOP-B-5 fix #2: when D3A_BLOCK_M1A=1, call d3a_tweedie_derivation.py with
# --require-resolved so AMBIGUOUS/TBD actually triggers a non-zero exit. Without the
# flag, d3a returns 0 for AMBIGUOUS/TBD (informational mode), so the block never fires.
D3A_FLAGS=""
if [[ "${D3A_BLOCK_M1A:-0}" == "1" ]]; then
    D3A_FLAGS="--require-resolved"
    echo "  D3A_BLOCK_M1A=1 → calling d3a with --require-resolved (AMBIGUOUS/TBD will halt)."
fi
set +e
python scripts/d3a_tweedie_derivation.py ${D3A_FLAGS}
D3A_EXIT=$?
set -e
if [[ "${D3A_EXIT}" -ne 0 ]]; then
    if [[ "${D3A_BLOCK_M1A:-0}" == "1" ]]; then
        echo
        echo "==============================================================="
        echo "M0.5 D3a HARD HALT (STOP-B-5): STATUS is not RESOLVED and"
        echo "D3A_BLOCK_M1A=1. Fill orbit-research/TWEEDIE_DERIVATION_NOTE.md"
        echo "and set STATUS: RESOLVED, or unset D3A_BLOCK_M1A to proceed"
        echo "informationally (Phase B / M2 will still be hard-blocked)."
        echo "==============================================================="
        exit "${D3A_EXIT}"
    fi
    echo "  D3a STATUS is not RESOLVED (informational mode; D3A_BLOCK_M1A is unset)."
    echo "  M1a may proceed; Phase B / M2 will be HARD-BLOCKED until RESOLVED."
fi

echo "=== M0.5 R050 informal mini-headroom probe (STOP-B-4 + STOP-B-5 fix) ==="
# STOP-B-5 fix #5a: SKIP_R050 alone is no longer enough to bypass R050. The PI must
# also set SKIP_R050_PI_ACK=1 to acknowledge the bypass. This prevents accidental
# silent skipping in production.
if [[ "${SKIP_R050:-0}" == "1" ]]; then
    if [[ "${SKIP_R050_PI_ACK:-0}" != "1" ]]; then
        echo
        echo "==============================================================="
        echo "R050 SKIP REQUESTED but missing PI acknowledgement (STOP-B-5)."
        echo "SKIP_R050=1 alone is not sufficient. To actually skip R050, set:"
        echo "  SKIP_R050=1"
        echo "  SKIP_R050_PI_ACK=1"
        echo "Both env vars are required so the bypass is explicit and audit-traceable."
        echo "==============================================================="
        exit 2
    fi
    echo "  SKIP_R050=1 + SKIP_R050_PI_ACK=1 → PI acknowledged; skipping R050."
    R050_BYPASSED=1
else
    R050_BYPASSED=0
    # STOP-B-8 Phase-1 (2026-05-17): default to 8-GPU sharded R050 via the new
    # orchestrator. Opt out with R050_SHARD=0 for single-process behavior. Per-run
    # overrides: R050_GPUS (default "0,1,2,3,4,5,6,7") and R050_N_SHARDS (default 8).
    set +e
    if [[ "${R050_SHARD:-1}" == "1" ]]; then
        python scripts/r050_run_sharded.py --mode "${MODE}" \
            --gpus "${R050_GPUS:-0,1,2,3,4,5,6,7}" \
            --n-shards "${R050_N_SHARDS:-8}"
    else
        python scripts/r050_mini_headroom_probe.py --mode "${MODE}"
    fi
    R050_EXIT=$?
    set -e
    if [[ "${R050_EXIT}" -ne 0 ]]; then
        echo
        echo "==============================================================="
        echo "R050 PAUSE-AND-REPORT: the informal probe did NOT show a positive"
        echo "trend (median Δ ≤ 0 or < 50% positive prompts)."
        echo "See orbit-research/R050_SUMMARY.md."
        echo
        echo "M1a's 256-prompt audit is the authoritative gate; this is informal."
        echo "PI must explicitly acknowledge before M1a launches:"
        echo "  - Set R050_PI_ACK=1 to override and continue to M1a."
        echo "  - Otherwise launch_phase_a.sh halts here."
        echo "==============================================================="
        if [[ "${R050_PI_ACK:-0}" != "1" ]]; then
            exit "${R050_EXIT}"
        fi
        echo "  R050_PI_ACK=1 → PI acknowledged; continuing to M1a."
    fi
fi

# STOP-B-5 fix #5b: write the M0.5 gate-passed flag so launch_baseline.py can verify
# direct invocations are downstream of a successful M0.5. This is the gate that
# launch_baseline.py reads when refusing direct M1a/M1b rung launches in production.
mkdir -p runs
cat > runs/M0_5_GATE_PASSED.flag <<EOF
# STOP-B-5: M0.5 gate-passed flag.
# Written by scripts/launch_phase_a.sh after D0-D5 + UI smoke + D3a + R050 all completed
# (D3a may be informational; R050 may be PI-ack'd; SKIP_R050 path requires SKIP_R050_PI_ACK).
# launch_baseline.py refuses production M1a/M1b rung launches unless this flag exists
# or M0_5_PI_ACK=1 is set.
timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)
mode: ${MODE}
d3a_block_m1a: ${D3A_BLOCK_M1A:-0}
r050_bypassed: ${R050_BYPASSED}
r050_pi_ack: ${R050_PI_ACK:-0}
skip_r050_pi_ack: ${SKIP_R050_PI_ACK:-0}
host: $(hostname)
EOF
echo
echo "M0.5 gate satisfied. Wrote runs/M0_5_GATE_PASSED.flag."

# ============================================================
# M1a — Phase A.1 basic-headroom audit (gates M1b)
#
# STOP-B-7 rung-role taxonomy (matches scripts/launch_baseline.py and
# scripts/compute_headroom_gate.py):
#
#   M1A_GATE_CRITICAL  — R0/R1/R2/R4/R9. Run on dev AND held-out. Each
#                        result gets `gate_r_lcb` under the uniform gate_v1
#                        evaluator (configs/eval/gate_v1.yaml). The H1
#                        headroom gate is decided on the held-out
#                        `gate_r_lcb` arrays of these five rungs.
#   M1A_DIAGNOSTIC_ONLY — R3 (Robust BoN). Diagnostic for reward-hackability
#                        only. Run on dev; NOT held-out replayed; its
#                        `r_lcb` (per-rung config) is NOT consumed by
#                        compute_headroom_gate.py. Codex flagged this role
#                        mismatch in the STOP-B-6 audit.
# ============================================================

# All M1a rungs run on dev (gate-critical + diagnostic). R3 stays in this
# list for reward-hackability diagnostic visibility on dev.
M1A_DEV_RUNGS=(r0_base r1_cfg_sweep r2_bon r3_robust_bon r4_bon_cfg r9_s7_sampler_control)
M1A_DIAGNOSTIC_ONLY=(r3_robust_bon)

# Gate-critical rungs MUST run on held-out for compute_headroom_gate to evaluate.
# R3 is intentionally excluded — diagnostic-only per STOP-B-7 taxonomy.
M1A_GATE_CRITICAL=(r0_base r1_cfg_sweep r2_bon r4_bon_cfg r9_s7_sampler_control)

# STOP-B-8 Phase-2 (2026-05-17): default to per-rung CVD-pinned parallel
# orchestration via scripts/m1a_run_parallel_rungs.py.
# Paratera A800 oversubscription (2026-05-19): defaults expand (rungs × seeds)
# Cartesian — 6 rungs × 3 seeds = 18 dev tasks on 8 GPUs × 3 slots/GPU = 24
# slots → all 18 concurrent. Each task uses ~20 GB (ACE-Step + reward harness)
# so 3/GPU fits the A800 80 GB budget. Held-out: 5 × 3 = 15 tasks.
# Overrides: M1A_OVERSUBSCRIBE=0 disables (then m1a runs the legacy one-process-
# per-rung mode, with each subprocess iterating its config seeds internally).
# M1A_SEEDS (default "0,1,2"), M1A_CONCURRENCY_PER_GPU (default "3"),
# M1A_GPUS (default "0,1,2,3,4,5,6,7"). M1A_PARALLEL=0 falls back to the legacy
# sequential bash loop kept below.
M1A_SEEDS_ARGS=""
if [[ "${M1A_OVERSUBSCRIBE:-1}" == "1" ]]; then
    M1A_SEEDS_ARGS="--seeds ${M1A_SEEDS:-0,1,2} --concurrency-per-gpu ${M1A_CONCURRENCY_PER_GPU:-3}"
fi
if [[ "${M1A_PARALLEL:-1}" == "1" ]]; then
    DEV_RUNGS_CSV="$(IFS=,; echo "${M1A_DEV_RUNGS[*]}")"
    GATE_RUNGS_CSV="$(IFS=,; echo "${M1A_GATE_CRITICAL[*]}")"

    echo "=== M1a (W2.1) — Phase A.1 basic-headroom audit on DEV (parallel, GPUs=${M1A_GPUS:-0,1,2,3,4,5,6,7}, seeds=${M1A_SEEDS:-0,1,2}, slots/GPU=${M1A_CONCURRENCY_PER_GPU:-3}) ==="
    python scripts/m1a_run_parallel_rungs.py \
        --split dev \
        --rungs "${DEV_RUNGS_CSV}" \
        --gpus "${M1A_GPUS:-0,1,2,3,4,5,6,7}" \
        ${M1A_SEEDS_ARGS} \
        --mode "${MODE}"

    # 2026-05-19: oversubscription per-seed→aggregate concurrent-write fixup.
    # The orchestrator spawns one launch_baseline.py subprocess per (rung, seed)
    # via --seeds <single>; each subprocess overwrites <rung>/<split>/results.jsonl
    # with only its own seed's data (last-writer-wins). The per-seed dirs are
    # intact; this script rebuilds the rung aggregate from them.
    bash tools/merge_perseed_results.sh dev

    echo "=== M1a (W2.1) — Held-out replay for gate-critical methods (parallel, GPUs=${M1A_GPUS:-0,1,2,3,4,5,6,7}, seeds=${M1A_SEEDS:-0,1,2}, slots/GPU=${M1A_CONCURRENCY_PER_GPU:-3}) ==="
    python scripts/m1a_run_parallel_rungs.py \
        --split held_out \
        --rungs "${GATE_RUNGS_CSV}" \
        --gpus "${M1A_GPUS:-0,1,2,3,4,5,6,7}" \
        ${M1A_SEEDS_ARGS} \
        --mode "${MODE}" \
        --prompts configs/prompts/held_out.jsonl

    # Same per-seed→aggregate fixup for the held-out split — runs BEFORE
    # compute_headroom_gate.py so the gate consumes the full aggregate.
    bash tools/merge_perseed_results.sh held_out
else
    echo "=== M1a (W2.1) — Phase A.1 basic-headroom audit on DEV (sequential, M1A_PARALLEL=0) ==="
    for rung in "${M1A_DEV_RUNGS[@]}"; do
        cfg="configs/baselines/${rung}.yaml"
        role="gate-critical"
        for diag in "${M1A_DIAGNOSTIC_ONLY[@]}"; do
            if [[ "${rung}" == "${diag}" ]]; then role="diagnostic-only"; fi
        done
        echo "--- M1a ${rung} on dev (role=${role}) ---"
        python scripts/launch_baseline.py --config "${cfg}" --split dev --mode "${MODE}"
    done

    echo "=== M1a (W2.1) — Held-out replay for gate-critical methods (sequential) ==="
    for rung in "${M1A_GATE_CRITICAL[@]}"; do
        cfg="configs/baselines/${rung}.yaml"
        echo "--- M1a ${rung} on held_out (role=gate-critical) ---"
        python scripts/launch_baseline.py --config "${cfg}" --split held_out \
            --prompts configs/prompts/held_out.jsonl --mode "${MODE}"
    done
fi

echo "=== M1a (W2.1) — Reward-human calibration (Block A.aux) ==="
# This is a manual / human-rater step; the script just notes the requirement.
echo "  TODO (human, blocking M1a gate): collect 32 ACE-Step + 32 SAO samples × 5 raters × 5 axes."
echo "  Until that data is staged, compute_headroom_gate will be invoked with --human-spot-check pending."
HUMAN_SPOT="${HUMAN_SPOT:-pending}"

# ============================================================
# M1a gate — basic-headroom decision
# ============================================================

echo "=== M1a gate — basic-headroom decision on held-out ==="
set +e
python scripts/compute_headroom_gate.py --split held_out --human-spot-check "${HUMAN_SPOT}"
GATE_EXIT=$?
set -e

if [[ "${GATE_EXIT}" -ne 0 ]]; then
    echo
    echo "==============================================================="
    echo "M1a basic-headroom gate did NOT pass. EXIT=${GATE_EXIT}."
    echo "STOP-B-1 contract: M1b is HALTED. See NULL_RESULT_CONTRACT.md §1"
    echo "Block A.1 for the failure-mode pivot table."
    echo "==============================================================="
    exit "${GATE_EXIT}"
fi

fi  # end STOP-B-7 _SKIP_M0_M1A guard — M0/M0.5/M1a + gate-decision skipped when START_AT_M1B=1.

if [[ "${_SKIP_M0_M1A}" == "1" ]]; then
    echo
    echo "==============================================================="
    echo "STOP-B-7 START_AT_M1B=1: skipped M0/M0.5/M1a; resuming at M1b."
    echo "  Gate decision was read from orbit-research/HEADROOM_GATE_DECISION.json."
    echo "==============================================================="
fi

# STOP-B-6 fix #3: M1a gate has PASSED. Decide whether to proceed into M1b.
# In production mode the default is to STOP here because the M1b rungs R8a/R8b
# are registered as deferred scaffolds in launch_baseline.py (they return BLOCK
# in production until the full GRPO loss/ratio path lands in the next
# /experiment-bridge call). Letting the script march on would just cause the
# whole bash run to fail partway through M1b — losing the M1a record in the
# process. Halt cleanly so the M1a results are durably recorded.
if [[ "${STOP_AFTER_M1A}" == "1" ]]; then
    echo
    echo "==============================================================="
    echo "STOP-B-6 STOP_AFTER_M1A=1 → halting cleanly before M1b."
    echo "  M1a basic-headroom gate has PASSED. Results are persisted."
    echo "  Reason (default): M1b R8a/R8b are deferred scaffolds in production."
    echo "  To resume M1b once R8a/R8b production support lands, rerun with"
    echo "  STOP_AFTER_M1A=0 (and optionally MODE=dev to exercise the"
    echo "  sampling-only call paths)."
    echo "==============================================================="
    exit 0
fi

# ============================================================
# M1b — Phase A.2 post-training baseline corpus (only if M1a passed)
# ============================================================

# M1b rungs: post-training (per Block A.2). R8 is deprecated; use R8a and R8b.
M1B_RUNGS=(r5_sft_on_best r6_robust_elite_sft r7_flow_dpo
           r8a_outcome_grpo_plain r8b_outcome_grpo_guarded)

echo "=== M1b (W2.2) — Phase A.2 post-training baseline corpus (M1a gate passed) ==="
for rung in "${M1B_RUNGS[@]}"; do
    cfg="configs/baselines/${rung}.yaml"
    echo "--- M1b ${rung} on dev ---"
    python scripts/launch_baseline.py --config "${cfg}" --split dev --mode "${MODE}"
done

# R6 (Robust Elite SFT) also runs on held-out for the Phase D matched-compute set.
echo "=== M1b — Held-out replay for R6 Robust Elite SFT ==="
python scripts/launch_baseline.py --config configs/baselines/r6_robust_elite_sft.yaml \
    --split held_out --prompts configs/prompts/held_out.jsonl --mode "${MODE}"

echo
echo "==============================================================="
echo "M1a + M1b complete. Phase A baseline corpus is ready."
echo "Next gate: /diagnostic-to-review for the Phase A audit interpretation."
echo "==============================================================="
