from __future__ import annotations

import hashlib
import importlib.util
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from mprm.common.provenance import collect_run_provenance
from mprm.common.thresholds import VOCAL_PRESENCE_THRESHOLD, is_vocal_present


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_per_seed_config_copy_does_not_alias_nested_state() -> None:
    module = load_script("launch_baseline_t11", "scripts/launch_baseline.py")
    original = SimpleNamespace(
        baseline=SimpleNamespace(seed=1, extras={"seeds": [1, 2]}),
        model=SimpleNamespace(options={"nested": ["a"]}),
    )
    copied = module._copy_config_for_seed(original)
    copied.baseline.seed = 9
    copied.baseline.extras["seeds"].append(3)
    copied.model.options["nested"].append("b")
    assert original.baseline.seed == 1
    assert original.baseline.extras == {"seeds": [1, 2]}
    assert original.model.options == {"nested": ["a"]}


def test_only_arm_two_fails_without_arm_four_yoke() -> None:
    module = load_script("batch3_online_t11", "scripts/batch3_online_harness.py")
    with pytest.raises(ValueError, match="yoked"):
        module._validate_only_arm(2)
    module._validate_only_arm(4)
    module._validate_only_arm(None)


def test_demucs_docstring_does_not_claim_silent_fallback() -> None:
    source = (ROOT / "src/mprm/rewards/demucs.py").read_text()
    assert "does not substitute" in source
    assert "Falls back to no-separation" not in source


def test_run_provenance_hashes_config_and_accepts_validated_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("value: 1\n")
    monkeypatch.setenv("MPRM_GIT_SHA", "1a2b3c4")
    monkeypatch.setenv("MPRM_MODEL_SHA256", "a" * 64)
    result = collect_run_provenance(
        config,
        SimpleNamespace(cache_dir=None),
        tmp_path,
    )
    assert result["config_hash"] == hashlib.sha256(config.read_bytes()).hexdigest()
    assert result["git_sha"] == "1a2b3c4"
    assert result["model_sha"] == "a" * 64


def test_run_provenance_rejects_non_sha_model_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("value: 1\n")
    monkeypatch.setenv("MPRM_MODEL_SHA256", "not-a-sha")
    with pytest.raises(ValueError, match="SHA256"):
        collect_run_provenance(config, SimpleNamespace(cache_dir=None), tmp_path)


def test_canonical_vocal_threshold_boundary() -> None:
    assert VOCAL_PRESENCE_THRESHOLD == pytest.approx(0.1791)
    assert not is_vocal_present(VOCAL_PRESENCE_THRESHOLD - 1e-8, False)
    assert is_vocal_present(VOCAL_PRESENCE_THRESHOLD, False)
    assert not is_vocal_present(1.0, True)


def test_no_duplicate_numeric_vocal_threshold_constants() -> None:
    allowed = ROOT / "src/mprm/common/thresholds.py"
    search_roots = [
        ROOT / "src",
        ROOT / "scripts",
        ROOT / "orbit-research/adsr_phase2_20260604/paper_prep",
        ROOT / "batch3/exploratory_auto",
    ]
    offenders = []
    for search_root in search_roots:
        for path in search_root.rglob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, float)
                    and node.value in {0.179, 0.1791}
                    and path != allowed
                ):
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert offenders == []


def test_threshold_gap_audit_detects_boundary_rows(tmp_path: Path) -> None:
    module = load_script(
        "threshold_gap_t11",
        "orbit-research/adsr_phase2_20260604/paper_prep/scripts/audit_vocal_threshold_gap.py",
    )
    clean = tmp_path / "clean.jsonl"
    clean.write_text('{"vocal_energy_ratio": 0.1789}\n{"gate_ratio": 0.1791}\n')
    assert module.audit([clean])["status"] == "PASS"
    gap = tmp_path / "gap.csv"
    gap.write_text("demucs_ratio\n0.17905\n")
    result = module.audit([gap])
    assert result["status"] == "FAIL"
    assert result["gap_hit_count"] == 1


def test_labeler_agreement_selection_is_deterministic_and_stratified() -> None:
    module = load_script(
        "labeler_agreement_t11",
        "orbit-research/adsr_phase2_20260604/paper_prep/scripts/audit_canonical_labeler_agreement.py",
    )
    rows = [
        {
            "rating_id": f"r{index}",
            "media_class": "original",
            "set_bucket": f"set{index % 2}",
            "expected_demucs_label": str(index % 2),
        }
        for index in range(20)
    ]
    first = module.select_rows(rows, 12)
    second = module.select_rows(rows, 12)
    assert [row["rating_id"] for row in first] == [row["rating_id"] for row in second]
    assert {row["set_bucket"] for row in first} == {"set0", "set1"}


def test_release_scripts_contain_no_machine_specific_repository_paths() -> None:
    search_roots = [
        ROOT / "src",
        ROOT / "scripts",
        ROOT / "orbit-research/adsr_phase2_20260604/paper_prep/scripts",
        ROOT / "batch3/exploratory_auto",
    ]
    forbidden = ("/HOME/", "/XYFS02/", "/APP/")
    offenders = []
    for search_root in search_roots:
        for path in search_root.rglob("*.py"):
            text = path.read_text()
            if any(token in text for token in forbidden):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
