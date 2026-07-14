from __future__ import annotations

import importlib.util
import json
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "paper_prep/scripts/w2_evpd_liveconfirm_20260712.py"
WORKER = ROOT / "paper_prep/scripts/w2_liveconfirm_worker_20260713.py"
PREFLIGHT = ROOT / "paper_prep/scripts/preflight_w2_reward_models_20260714.py"


def load_module():
    spec = importlib.util.spec_from_file_location("w2_evpd_live", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_worker():
    spec = importlib.util.spec_from_file_location("w2_live_worker", WORKER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_preflight():
    spec = importlib.util.spec_from_file_location("w2_reward_preflight", PREFLIGHT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_manifest_contract_and_crn_formula():
    module = load_module()
    assert len(module.POLICIES) == 4
    seeds = {
        module.SEED_BASE + prompt_rank * 100 + rep
        for prompt_rank in range(64)
        for rep in range(2)
    }
    assert len(seeds) == 128
    assert min(seeds) == 2_035_000_000
    assert max(seeds) == 2_035_006_301
    registry = (ROOT / "paper_prep/SEED_REGISTRY.md").read_text(encoding="utf-8")
    assert "2035006301" in registry


def test_launch_guard_rejects_unsigned_amendment(tmp_path):
    module = load_module()
    amendment = tmp_path / "amendment.md"
    amendment.write_text("W2_AMENDMENT_STATUS = DRAFTED_AWAITING_SIGNATURE\n", encoding="utf-8")
    promotion = tmp_path / "promotion.json"
    promotion.write_text(json.dumps({"CORRECTED_INSTRUMENT_STATUS": "PASS_DUAL_PI_ADOPTED"}), encoding="utf-8")
    try:
        module.launch_guard(amendment, promotion, "not-a-real-hash")
    except ValueError as exc:
        assert "not signed" in str(exc)
    else:
        raise AssertionError("unsigned amendment passed launch guard")


def test_launch_guard_accepts_signed_amendment_and_mechanical_promotion():
    module = load_module()
    module.EVPD_MODEL = (
        ROOT
        / "paper_prep/w2_execution_20260712/evpd_liveconfirm_torch251_recovery/corrected_evpd_sigma08.joblib"
    )
    result = module.launch_guard(
        ROOT / "paper_prep/W2_AMENDMENT_20260712.md",
        ROOT / "paper_prep/autochain_20260712/T6_PROMOTION_RESULT.json",
        module.sha256_file(module.POLICY_SPEC),
    )
    assert result["status"] == "PASS_LAUNCH_AUTHORIZED"


def test_live_launch_amendment_hash_remains_bit_exact():
    amendment = ROOT / "paper_prep/W2_AMENDMENT_20260712.md"
    guard = json.loads(
        (
            ROOT
            / "paper_prep/w2_execution_20260712/live_confirmation_20260713/LIVE_LAUNCH_GUARD.json"
        ).read_text(encoding="utf-8")
    )
    assert hashlib.sha256(amendment.read_bytes()).hexdigest() == guard["amendment_sha256"]


def test_worker_runtime_guard_accepts_signed_mechanical_artifacts_and_rejects_unsigned():
    module = load_worker()
    amendment = (ROOT / "paper_prep/W2_AMENDMENT_20260712.md").read_text()
    promotion = json.loads(
        (ROOT / "paper_prep/autochain_20260712/T6_PROMOTION_RESULT.json").read_text()
    )
    evpd = {
        "training_status": "DRAFT_MECHANICAL_PROMOTION_AWAITING_DUAL_PI_ADOPTION"
    }
    module.validate_runtime_authorization(amendment, promotion, evpd)
    try:
        module.validate_runtime_authorization("unsigned", promotion, evpd)
    except ValueError as exc:
        assert "signed W2 amendment" in str(exc)
    else:
        raise AssertionError("unsigned amendment unlocked the live worker")


def test_live_launcher_is_offline_resumable_and_preserves_hard_stop():
    source = (
        ROOT / "paper_prep/scripts/run_w2_liveconfirm_20260713.sh"
    ).read_text(encoding="utf-8")
    for variable in (
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "LAION_CLAP_BERT_DIR",
        "LAION_CLAP_ROBERTA_DIR",
        "LAION_CLAP_BART_DIR",
        "MERT_LOCAL_PATH",
        "AUDIOBOX_AES_CKPT",
    ):
        assert f"export {variable}=" in source
    assert "preflight_w2_reward_models_20260714.py" in source
    assert '[[ ! -s "${OUT}/ACTUAL_LAUNCH_TIMESTAMP.txt" ]]' in source
    assert '[[ ! -s "${OUT}/HARD_STOP_DEADLINE.txt" ]]' in source
    assert 'deadline=$(date -d "$(cat "${OUT}/HARD_STOP_DEADLINE.txt")" +%s)' in source


def test_w2_heartbeat_detects_relative_worker_commands_and_live_ledgers():
    source = (
        ROOT / "paper_prep/scripts/w2_heartbeat_20260712.sh"
    ).read_text(encoding="utf-8")
    assert "ps -eo pid=,comm=,args=" in source
    assert "$2 ~ /^python([0-9.]*)?$/" in source
    assert "paper_prep\\/scripts\\/w2_[^ ]*\\.py" in source
    assert "live_confirmation_20260713/live_ledgers" in source


def test_worker_recovers_orphan_audio_instead_of_overwriting_it():
    module = load_worker()
    path = module.output_audio_path("unit", 1, 123)
    assert path.name == "slot1_seed123.flac"
    source = WORKER.read_text(encoding="utf-8")
    recovery = source.index("if audio_path.exists():")
    generation = source.index("state = generate(active_prompt")
    assert recovery < generation
    assert '"recovered_orphan": True' in source
    assert '"label_b_satisfied": int(scored["present"] == requested)' in source
    assert "refusing near-silent orphan audio" in source


def test_reward_preflight_fails_closed_on_missing_or_unset_paths(tmp_path, monkeypatch):
    module = load_preflight()
    for variable in module.ENV_PATHS:
        monkeypatch.delenv(variable, raising=False)
    try:
        module.validate_paths(tmp_path)
    except RuntimeError as exc:
        assert "is unset" in str(exc)
    else:
        raise AssertionError("unset offline model paths passed preflight")

    for variable, kind in module.ENV_PATHS.items():
        path = tmp_path / variable
        if kind == "directory":
            path.mkdir()
        else:
            path.write_bytes(b"checkpoint")
        monkeypatch.setenv(variable, str(path))
    (tmp_path / ".cache/whisper").mkdir(parents=True)
    (tmp_path / ".cache/clap").mkdir(parents=True)
    (tmp_path / ".cache/whisper/large-v3.pt").write_bytes(b"checkpoint")
    (tmp_path / ".cache/clap/630k-audioset-best.pt").write_bytes(b"checkpoint")
    assert set(module.validate_paths(tmp_path)) == {
        *module.ENV_PATHS,
        "WHISPER_LARGE_V3",
        "CLAP_630K_AUDIOSET",
    }


def test_recovery_evpd_and_spine_paths_can_be_versioned():
    module = load_module()
    relative = module.resolve_repo_path("paper_prep/recovery_evpd", "unused")
    assert relative == module.ROOT / "paper_prep/recovery_evpd"
    absolute = module.ROOT / "paper_prep/recovery_spine"
    assert module.resolve_repo_path(str(absolute), "unused") == absolute
