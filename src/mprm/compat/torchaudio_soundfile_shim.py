"""Monkey-patch `torchaudio.save` and `torchaudio.load` to use `soundfile`.

STOP-B-8 Phase-2 (2026-05-18). On the new Blackwell pro6000 box we run torch
2.11.0+cu128 (required for sm_120 kernels), and torchaudio 2.11 routes
`save`/`load` through `torchcodec` by default. torchcodec's native lib
(`libtorchcodec_core4.so`) fails to load on this machine because:

  - it has no rpath/runpath for libtorch.so → c10/c10_cuda/nvrtc not found.
  - it links against libavutil.so.58 / libavcodec.so.58 (FFmpeg 4.x) which
    are absent (system FFmpeg is on a different major version).

soundfile is already a project-level REQUIRED dep (`scripts/d0_env_check.py`
REQUIRED_IMPORTS), is in active use elsewhere (e.g. ACE-Step's `save_wav_file`
explicitly passes `backend='soundfile'`), and supports WAV/FLAC/OGG, which
covers every audio format the production pipeline produces or consumes.

Importing this module installs the patch as a side effect — idempotent across
re-imports (a sentinel attribute on `torchaudio` records the install). The
patch falls back to the original `_save`/`_load` for unsupported formats, so
any caller that intentionally exercises an FFmpeg-only codec still gets a
clear error rather than a silent dropout.

Usage:
    from mprm.compat import torchaudio_soundfile_shim  # noqa: F401

Or invoke `install()` explicitly if you need to apply the patch after some
other code has already cached a reference to `torchaudio.save`.
"""
from __future__ import annotations

import numpy as np
import soundfile as sf
import torch
import torchaudio

_SHIM_ATTR = "_mprm_torchaudio_soundfile_shim_installed"


def install() -> bool:
    """Install the soundfile-backed shim on `torchaudio.save` and
    `torchaudio.load`. Returns True if installed this call, False if already
    installed OR if the torch version is < 2.6 (where the legacy backend
    works and the shim is unnecessary)."""
    if getattr(torchaudio, _SHIM_ATTR, False):
        return False
    # Version gate: torch < 2.6 still uses the legacy backend that respects
    # `backend="soundfile"`; no shim needed there.
    try:
        _major, _minor = [int(x) for x in torch.__version__.split("+")[0].split(".")[:2]]
        if (_major, _minor) < (2, 6):
            return False
    except Exception:  # noqa: BLE001
        pass

    _original_save = torchaudio.save
    _original_load = torchaudio.load

    def _shim_save(uri, src, sample_rate, *, channels_first: bool = True,
                   format=None, encoding=None, bits_per_sample=None,
                   buffer_size=4096, backend=None, compression=None):
        fmt = (format or "").lower() if isinstance(format, str) else ""
        if fmt in ("wav", "flac", "ogg", ""):
            arr = (src.detach().cpu().to(torch.float32).numpy()
                   if hasattr(src, "detach") else np.asarray(src))
            if arr.ndim == 1:
                pass  # mono (samples,)
            elif arr.ndim == 2:
                arr = arr.T if channels_first else arr  # → (samples, channels)
            else:
                raise ValueError(f"torchaudio_soundfile_shim: unsupported tensor"
                                 f" rank {arr.ndim}")
            sf_fmt = "WAV" if fmt in ("wav", "") else (
                "FLAC" if fmt == "flac" else "OGG")
            sf.write(str(uri), arr, int(sample_rate), format=sf_fmt)
            return
        return _original_save(uri, src, sample_rate, channels_first=channels_first,
                                format=format, encoding=encoding,
                                bits_per_sample=bits_per_sample,
                                buffer_size=buffer_size, backend=backend,
                                compression=compression)

    def _shim_load(uri, *args, **kwargs):
        channels_first = kwargs.pop("channels_first", True)
        try:
            arr, sr = sf.read(str(uri), dtype="float32", always_2d=False)
        except Exception:  # noqa: BLE001
            return _original_load(uri, *args, **kwargs)
        t = torch.from_numpy(np.ascontiguousarray(arr))
        if t.dim() == 1:
            t = t.unsqueeze(0)  # → (1, samples)
        elif t.dim() == 2 and channels_first:
            t = t.T.contiguous()  # (samples, channels) → (channels, samples)
        return t, int(sr)

    torchaudio.save = _shim_save  # type: ignore[assignment]
    torchaudio.load = _shim_load  # type: ignore[assignment]
    setattr(torchaudio, _SHIM_ATTR, True)
    return True


install()
