"""mprm — Headroom-Gated M-PRM."""

__version__ = "0.1.0"

# STOP-B-8 Phase-2 (2026-05-18): the following two patches are needed only on
# torch >= 2.6 (the version that introduced default `torch.load
# (weights_only=True)` and rerouted `torchaudio.save/load` through torchcodec
# by default). On the Blackwell pro6000 box we run torch 2.11+cu128 and BOTH
# patches must be active. On the A800 box (sm_80) we run the stable torch
# 2.5.1+cu121, and these patches are no-ops — the old torchaudio default
# backend (soundfile/sox) works directly and `torch.load(weights_only=False)`
# is already the default.
#
# Conditional auto-install keeps a single codebase that works on both boxes
# without per-machine forks. Idempotent + safe on fresh envs.
try:
    import torch as _torch_for_compat
    _t_major, _t_minor = [
        int(_x) for _x in _torch_for_compat.__version__.split("+")[0].split(".")[:2]
    ]
    _t_is_26_plus = (_t_major, _t_minor) >= (2, 6)
except Exception:  # noqa: BLE001
    _t_is_26_plus = False

if _t_is_26_plus:
    # Patch 1: route torchaudio.save/load through soundfile to bypass the
    # torchcodec backend (whose native lib is broken on this Blackwell box).
    try:
        from mprm.compat import torchaudio_soundfile_shim  # noqa: F401
    except Exception:  # noqa: BLE001
        # Don't make import-of-mprm fatal if torchaudio is somehow unavailable;
        # the underlying error will resurface at the actual save/load site.
        pass

    # Patch 2: revert torch.load default to weights_only=False. We trust every
    # weight file we load (project-controlled local paths or vetted public S3
    # mirrors), and a number of project checkpoints contain numpy globals
    # (`numpy.core.multiarray.scalar`) that the new safe-globals allowlist
    # rejects by default.
    try:
        _original_torch_load = _torch_for_compat.load
        if not getattr(_torch_for_compat.load, "_mprm_weights_only_default_patched", False):
            def _patched_torch_load(*args, **kwargs):
                kwargs.setdefault("weights_only", False)
                return _original_torch_load(*args, **kwargs)
            _patched_torch_load._mprm_weights_only_default_patched = True  # type: ignore[attr-defined]
            _torch_for_compat.load = _patched_torch_load  # type: ignore[assignment]
    except Exception:  # noqa: BLE001
        pass
