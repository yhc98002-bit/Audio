"""D0 — CPU / GPU environment + dependency smoke (DIAGNOSTIC_EXPERIMENT_PLAN §2 D0).

STOP-B-8 Phase-2 (2026-05-17): `laion_clap` does module-level `from_pretrained`
loads of bert/roberta/bart at import time. Those fail on this box because the
HF Python lib's hf-mirror.com redirect chain is unreliable. The compat shim
at `mprm.compat.laion_clap_local_tokenizers` monkey-patches `from_pretrained`
to route those magic strings to pre-cached local directories. Import the
shim BEFORE attempting `laion_clap` so the optional-import check actually
exercises the path the production pipeline uses (rather than reporting a
spurious FAIL that the rest of the launcher would have worked around anyway).

STOP-B-8 Phase-2 also fixes the optional name `"ace_step"` → `"acestep"`. The
pip package distribution is `ace_step` (with underscore), but the importable
Python module name installed by that package is `acestep` (no underscore).
"""
from __future__ import annotations

import argparse
import importlib
import sys
import tempfile
from pathlib import Path

# STOP-B-8 Phase-2: install the laion_clap local-tokenizer shim before the
# optional-import check tries to import laion_clap. The shim is a no-op if
# the local tokenizer dirs are absent (it falls back to network), so this
# remains safe on a fresh box where the dirs haven't been staged yet — the
# import will still FAIL there, just for the underlying network reason, not
# because the shim was skipped.
#
# Also install the torchaudio→soundfile shim (Blackwell + torch 2.11 makes
# torchaudio's default torchcodec backend unusable on this box; see
# mprm.compat.torchaudio_soundfile_shim for the full reason). This must run
# BEFORE `check_audio_io` exercises `torchaudio.save`/`torchaudio.load`.
try:
    from mprm.compat import laion_clap_local_tokenizers  # noqa: F401
except Exception:  # noqa: BLE001
    # If mprm is not on PYTHONPATH (e.g. someone runs this script in raw
    # production mode without setting PYTHONPATH=src), the shim is skipped
    # but the rest of the smoke is unaffected; the laion_clap line will
    # then surface as FAIL which is informationally correct.
    pass
try:
    # mprm/__init__.py installs this conditionally on torch >= 2.6; the import
    # here is a defense-in-depth so D0 still applies the shim if someone runs
    # this script with PYTHONPATH=src but without importing other mprm.* first.
    # On torch 2.5.1 (A800) the shim is a no-op (see version check inside
    # mprm.__init__).
    import mprm  # noqa: F401
except Exception:  # noqa: BLE001
    # Same fallback semantics as above — if mprm isn't importable, the audio_io
    # check will surface its own underlying torchcodec error.
    pass


REQUIRED_IMPORTS = [
    "torch",
    "torchaudio",
    "transformers",
    "accelerate",
    "peft",
    "diffusers",
    "librosa",
    "numpy",
    "pandas",
    "pydantic",
    "yaml",
    "jsonlines",
    "tqdm",
    "soundfile",
    "einops",
    "mir_eval",
    "demucs",
    "whisper",
]


OPTIONAL_IMPORTS = [
    "laion_clap",
    "audiobox_aesthetics",
    "acestep",  # STOP-B-8 Phase-2: pip package "ace_step" exposes module "acestep".
    "stable_audio_tools",
]

# Paratera migration (2026-05-19): stable_audio_tools pulls `pypesq` whose
# old-style setup.py is incompatible with numpy>=1.26 / setuptools 80+. SAO is
# audit-only per FINAL_PROPOSAL §3.2 and is not required for Phase A M0 /
# M0.5 / M1a (which train + audit on ACE-Step). Treat its absence as deferred
# in --mode production until SAO audit pass actually needs it.
DEFERRED_OPTIONALS: set[str] = {"stable_audio_tools"}


def check_imports(modules: list[str]) -> dict[str, str]:
    status: dict[str, str] = {}
    for mod in modules:
        try:
            m = importlib.import_module(mod)
            status[mod] = getattr(m, "__version__", "ok")
        except Exception as e:  # noqa: BLE001
            status[mod] = f"FAIL: {type(e).__name__}: {e}"
    return status


def check_gpu(require_cuda: bool) -> tuple[str, bool]:
    try:
        import torch
        if torch.cuda.is_available():
            return f"cuda:0 = {torch.cuda.get_device_name(0)}", True
        msg = "cuda_unavailable"
        return msg, not require_cuda
    except Exception as e:  # noqa: BLE001
        return f"FAIL: {type(e).__name__}: {e}", False


def check_audio_io() -> str:
    try:
        import torch
        import torchaudio
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "smoke.wav"
            wav = torch.zeros(1, 16000)
            torchaudio.save(str(path), wav, 16000)
            loaded, sr = torchaudio.load(str(path))
            assert loaded.shape == wav.shape, "shape mismatch"
            assert sr == 16000, "sr mismatch"
        return "ok"
    except Exception as e:  # noqa: BLE001
        return f"FAIL: {type(e).__name__}: {e}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["dev", "production"], default="dev",
                        help="production requires CUDA; dev allows CPU-only env smoke")
    args = parser.parse_args()

    print(f"D0 — env smoke (mode={args.mode})")
    required = check_imports(REQUIRED_IMPORTS)
    optional = check_imports(OPTIONAL_IMPORTS)
    gpu_msg, gpu_ok = check_gpu(require_cuda=args.mode == "production")
    audio = check_audio_io()

    bad_required = [k for k, v in required.items() if v.startswith("FAIL")]
    bad_optional = [k for k, v in optional.items() if v.startswith("FAIL")]

    print("\nRequired imports:")
    for k, v in required.items():
        print(f"  {k}: {v}")
    print("\nOptional imports (model wrappers; install before Wave W2):")
    for k, v in optional.items():
        print(f"  {k}: {v}")
    print(f"\nGPU: {gpu_msg}")
    print(f"Audio I/O: {audio}")

    failures = bad_required.copy()
    if audio.startswith("FAIL"):
        failures.append("audio_io")
    if args.mode == "production" and not gpu_ok:
        failures.append("cuda_required_in_production")
    if args.mode == "production" and bad_optional:
        blocking_optional = [k for k in bad_optional if k not in DEFERRED_OPTIONALS]
        if blocking_optional:
            failures.extend(
                f"optional_required_in_production:{k}" for k in blocking_optional
            )
        deferred_missing = [k for k in bad_optional if k in DEFERRED_OPTIONALS]
        if deferred_missing:
            print(f"\nNOTE: deferred optionals missing (informational only,"
                  f" not Phase A blocking): {deferred_missing}")

    if failures:
        print(f"\nD0 FAIL: {failures}")
        return 1
    if bad_optional and args.mode == "dev":
        print(f"\nD0 PASS (dev mode); optional missing: {bad_optional}. Install before Wave W2.")
    else:
        print("\nD0 PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
