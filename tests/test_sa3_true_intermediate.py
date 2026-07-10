import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "paper_prep/sao/stable_audio_3_medium/run_sa3_true_intermediate.py"
SPEC = importlib.util.spec_from_file_location("run_sa3_true_intermediate", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _rows():
    manifest = []
    full = []
    low = []
    for request in ("instrumental", "vocal"):
        for prompt_index in range(5):
            prompt_id = f"{request}_{prompt_index}"
            for seed_idx in range(2):
                manifest.append(
                    {
                        "prompt_id": prompt_id,
                        "seed_idx": seed_idx,
                        "seed": 1000 + prompt_index * 10 + seed_idx,
                        "prompt": prompt_id,
                        "duration_s": 8,
                        "vocal_stratum": request,
                        "stratum": "test",
                    }
                )
                common = {
                    "ok": True,
                    "prompt_id": prompt_id,
                    "seed_idx": seed_idx,
                    "seed": 1000 + prompt_index * 10 + seed_idx,
                    "vocal_stratum": request,
                    "stratum": "test",
                    "present": seed_idx,
                    "vocal_energy_ratio": seed_idx * 0.5,
                    "audio_path": f"/{prompt_id}_{seed_idx}.wav",
                }
                full.append(common)
                low.append({**common, "audio_path": f"/low_{prompt_id}_{seed_idx}.wav"})
    return manifest, full, low


def test_selection_is_deterministic_unique_and_split_balanced():
    manifest, full, low = _rows()
    first = MODULE.select_manifest_rows(manifest, full, low, per_request_stratum=4, seed=7)
    second = MODULE.select_manifest_rows(manifest, full, low, per_request_stratum=4, seed=7)
    assert first == second
    assert len(first) == 8
    assert len({row["prompt_id"] for row in first}) == 8
    assert {(row["vocal_stratum"], row["split"]) for row in first} == {
        ("instrumental", "development"),
        ("instrumental", "test"),
        ("vocal", "development"),
        ("vocal", "test"),
    }
